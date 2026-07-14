"""The sequential RATD runtime over the rebuilt memory/circuit layer.

Semantics per RATD_Memory_Circuit_Spec.md v1.0. The execution loop is
still a serial interleaving (parallel runtime is Part D), but every
concurrency-sensitive semantic is already pinned: snapshot-at-dequeue
(A'1), CAS exactly-once firing (B1), race-safe quiescence definition
(B5), and the interleaving record (A'3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..phase1 import (
    DEFAULT_LOCAL_ENDPOINT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    Config,
    build_repair_message,
    call_model,
    ensure_credentials,
    load_json,
    write_json,
)
from . import addresses
from .circuit import Circuit, gate_refs
from .doctor import DOCTOR_K, build_dossier, dossier_text, validate_repair
from .induction import Induction
from .store import (
    DEFAULT_LIST_K,
    ROUTING_FETCH_BUDGET,
    SINGLE_EMISSION_MAX,
    SUMMARY_MAX,
    WORKER_FETCH_BUDGET,
    Store,
)
from .validate import validate_action

import sqlite3

MAX_ROUTE_CALLS = 6      # LLM calls per routing step (reads + repairs + final)
WORKER_ATTEMPTS = 3
DOCTOR_ATTEMPTS = 3
CATALOG_CONTEXT_K = 20   # catalog lines provisioned into a context block


@dataclass
class AgentSpec:
    task_id: str
    root_goal: str
    task: str
    capsule: str
    depth: int
    parent: str | None
    expected_outputs: list[dict[str, str]]
    condition: str | None = None
    worker_only: bool = False
    system: bool = False


@dataclass
class RunMetrics:
    run_id: str
    task_id: str
    outcome: str                 # converged | converged-with-repair | failed
    converged: bool
    termination: str             # natural | rail
    rail_hit: str
    llm_calls: int
    agent_count: int
    max_depth: int
    doctor_cycles: int
    root_pins: list[str]
    root_pins_done: list[str]
    pins_total: int
    pins_done: int
    pins_failed: int
    pins_abandoned: int
    gates_total: int
    gates_fired: int
    gates_dead: int
    conflict_count: int
    fallback_writes: int
    entry_count: int
    fetch_count: int
    defer_count: int
    promotion_count: int
    starved_agents: list[str]
    failure: dict[str, Any]
    interleaving: list[str]
    qualitative: str
    doctor_calls: int = 0        # LLM calls spent inside doctor cycles (EM3 repair economy)
    induction: dict[str, Any] | None = None  # EM3: mechanized-failure provenance


class Runtime:
    def __init__(self, run_id: str, root_task: dict[str, Any], prompts: dict[str, str],
                 config: Config, out_dir: Path, *, list_enabled: bool = True,
                 induction: "Induction | None" = None):
        self.run_id = run_id
        self.root_task = root_task
        self.harness = prompts["harness"]
        self.worker_prompt = prompts["worker"]
        self.doctor_prompt = prompts["doctor"]
        self.config = config
        # EM knobs: Arm B removes LIST from the action space (EM1); the
        # induction mechanizes a systemic failure (EM3). Both default off,
        # so an ordinary run is byte-identical to the spec runtime.
        self.list_enabled = list_enabled
        self.induction = induction
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.out_dir / "trace.jsonl"
        self.db = sqlite3.connect(self.out_dir / "state.sqlite")
        self.circuit = Circuit(self.db, self.log)
        self.store = Store(self.db, self.log)
        self.queue: list[AgentSpec] = []
        self.llm_calls = 0
        self.defer_seq = 0
        self.promotions = 0
        self.doctor_cycles = 0
        self.doctor_calls = 0
        self.repair_index = 1
        self.prior_cycles: list[dict[str, Any]] = []
        self.interleaving: list[str] = []
        self.rail_hit = ""
        self.started = time.time()
        self.max_calls = 120
        self.max_depth = 8
        self.wall_clock = 40 * 60

    # ---- logging ------------------------------------------------------

    def log(self, event: str, **data: Any) -> None:
        rec = {"ts": time.time(), "event": event, **data}
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---- main loop ------------------------------------------------------

    def run(self) -> RunMetrics:
        root = AgentSpec("root", self.root_task["task"], self.root_task["task"],
                         "(you are the root agent)", 0, None, [])
        self.circuit.create_agent("root", "queued", 0, None, json.dumps(asdict(root)))
        self.queue.append(root)
        self.log("enqueue", agent=asdict(root))

        while True:
            railed = self._drain_queue()
            if railed:
                for spec in self.queue:
                    self.circuit.set_agent_state(spec.task_id, "dropped")
                self.queue.clear()
                break
            # queue empty; in the sequential runtime nothing is in-flight,
            # so B5 quiescence reduces to "no fireable gates" — checked by
            # _drain_queue's trailing fire_ready. Now consume quiescence:
            starved = self.circuit.mark_starved()
            self.circuit.refresh_liveness(trigger="quiescence")
            report = self.circuit.failure_report(self.store.fallback_writes())
            self.log("quiescence", failing=report["failing"],
                     unmet_root=len(report["unmet_root_pins"]),
                     dead_gates=len(report["dead_gates"]),
                     abandoned=len(report["abandoned_pins"]),
                     fallback=len(report["fallback_writes"]), starved=starved)
            if not report["failing"]:
                break
            if self.doctor_cycles >= DOCTOR_K:
                self.log("doctor_exhausted", cycles=self.doctor_cycles)
                break
            if self.llm_calls >= self.max_calls:
                self.log("doctor_exhausted", reason="call rail")
                break
            repaired = self.doctor_cycle(report)
            if not repaired and not self.queue and not self.circuit.fireable_exists():
                break
        metrics = self.metrics()
        write_json(self.out_dir / "metrics.json", asdict(metrics))
        return metrics

    def _drain_queue(self) -> bool:
        """Run agents until the queue drains or a global rail hits.
        Returns True if a rail ended the run."""
        while True:
            self.circuit.fire_ready(self._enqueue_consequence)
            if not self.queue:
                return False
            if self._global_rails_hit():
                return True
            agent = self.queue.pop(0)
            self.step(agent)

    def _global_rails_hit(self) -> bool:
        if self.llm_calls >= self.max_calls:
            self.rail_hit = "max_llm_calls"
        elif time.time() - self.started > self.wall_clock:
            self.rail_hit = "wall_clock"
        if self.rail_hit:
            self.log("rail_hit", rail=self.rail_hit)
            return True
        return False

    def enqueue(self, spec: AgentSpec) -> None:
        if spec.depth > self.max_depth:
            # per-agent depth rail: the child is dropped (B7), which runs
            # the A2 abandonment chain over its pins — an honest failure
            # state, not a silent global stop.
            self.log("depth_drop", agent=spec.task_id, depth=spec.depth)
            self.circuit.set_agent_state(spec.task_id, "dropped")
            return
        self.queue.append(spec)
        self.circuit.set_agent_state(spec.task_id, "queued")
        self.log("enqueue", agent=asdict(spec))

    def _enqueue_consequence(self, consequence: dict[str, Any], gate_id: str) -> None:
        spec = AgentSpec(**consequence["agent"])
        self.enqueue(spec)

    # ---- one agent step -------------------------------------------------

    def step(self, agent: AgentSpec) -> None:
        self.interleaving.append(f"start:{agent.task_id}")
        self._log_snapshot(agent)
        if agent.worker_only:
            self.log("self_role_start", agent=agent.task_id, condition=agent.condition)
            self.execute(agent, {})
        else:
            self.circuit.set_agent_state(agent.task_id, "routing")
            self.log("agent_start", agent=asdict(agent))
            action = self.route(agent)
            if action is None:
                # routing exhausted: terminal failure -> abandonment chain
                self.circuit.set_agent_state(agent.task_id, "failed")
            elif action["action"] == "EXECUTE":
                self.execute(agent, action)
            elif action["action"] == "SPAWN":
                self.spawn(agent, action)
                if self.induction and self.induction.drop_after_spawn(agent):
                    # EM3 H2: the spawn side-effects stand; the agent's own
                    # continuation is dropped, abandoning its interface pins.
                    self.queue = [s for s in self.queue if s.task_id != agent.task_id]
                    self.log("induction_drop", mode=self.induction.mode, agent=agent.task_id)
                    self.circuit.set_agent_state(agent.task_id, "dropped")
            elif action["action"] == "DEFER":
                self.defer(agent, action)
        self.interleaving.append(f"end:{agent.task_id}")

    def _log_snapshot(self, agent: AgentSpec) -> None:
        """A'1: the step's decision is attributable to a definite D-state.
        Sequentially the snapshot equals the live state; the digest makes
        the attribution mechanical (R2) and replay-checkable."""
        rows = self.db.execute("SELECT address, status FROM pins ORDER BY address").fetchall()
        digest = hashlib.sha1(json.dumps(rows).encode("utf-8")).hexdigest()[:12]
        self.log("snapshot", agent=agent.task_id, pins=len(rows),
                 done=sum(1 for _, s in rows if s == "done"), digest=digest)

    # ---- routing (with bounded reads) ------------------------------------

    def context_catalog(self, agent: AgentSpec) -> list[str]:
        """Default catalog slice: ancestor namespaces, the agent's gate
        refs, and capsule-mentioned addresses — k-capped lines, never
        bodies (R1). Anything else is reachable via LIST."""
        lines: list[str] = []
        seen: set[str] = set()
        for ns in addresses.ancestor_namespaces(agent.task_id):
            for line in self.store.catalog_lines(self.circuit, ns, CATALOG_CONTEXT_K):
                if line not in seen:
                    seen.add(line)
                    lines.append(line)
        named = set(gate_refs(agent.condition or "")[0]) | addresses.scan_addresses(agent.capsule)
        for address in sorted(named):
            pin = self.circuit.pin(address)
            if pin is None:
                continue
            entry = self.store.entry(address)
            summary = entry["summary"] if entry else f"({pin['status']} by {pin['owner']})"
            line = f"{address} · {pin['status']} · {summary}"
            if line not in seen:
                seen.add(line)
                lines.append(line)
        return lines[: CATALOG_CONTEXT_K * 2]

    def routing_context(self, agent: AgentSpec) -> str:
        catalog = self.context_catalog(agent)
        return "\n".join([
            f"ROOT GOAL: {agent.root_goal}",
            f"YOUR TASK ID: {agent.task_id}",
            f"YOUR TASK: {agent.task}",
            f"YOUR CAPSULE (why you exist): {agent.capsule}",
            f"GLOBAL CALLS REMAINING: {max(0, self.max_calls - self.llm_calls)}",
            f"YOUR ASSIGNED INTERFACE PINS: {json.dumps(agent.expected_outputs, ensure_ascii=False)}",
            "CATALOG (address · status · summary; snapshot at your dequeue):",
            "\n".join(catalog) if catalog else "(no pins yet)",
            f"ROUTING FETCH BUDGET: {ROUTING_FETCH_BUDGET} chars",
        ])

    def route(self, agent: AgentSpec) -> dict[str, Any] | None:
        base = self.routing_context(agent)
        observations: list[str] = []
        fetch_budget = ROUTING_FETCH_BUDGET
        raw, notes = "", []
        for call_index in range(MAX_ROUTE_CALLS):
            message = base
            if observations:
                message = base + "\n\nREAD RESULTS SO FAR:\n" + "\n\n".join(observations) + \
                    "\n\nEmit your next action document (EXECUTE/SPAWN/DEFER, or another LIST/FETCH)."
            prompt = message if not notes else build_repair_message(message, raw, notes)
            self.log("route_context", agent=agent.task_id, call=call_index + 1,
                     chars=len(self.harness) + len(prompt))
            self.llm_calls += 1
            raw = call_model(self.harness, prompt, self.config)
            parsed, notes = validate_action(raw, agent, self.circuit)
            if parsed is None or notes:
                self.log("route_repair", agent=agent.task_id, attempt=call_index + 1, notes=notes)
                continue
            kind = parsed["action"]
            if kind == "LIST" and not self.list_enabled:
                # EM1 Arm B: discovery is removed from the action space.
                notes = ["LIST is not available in this configuration; decide from the "
                         "catalog already in your context, or DEFER on an EXISTING pin"]
                self.log("route_repair", agent=agent.task_id, attempt=call_index + 1, notes=notes)
                continue
            if kind == "LIST":
                prefix = parsed.get("namespace_prefix")
                k = parsed.get("k") or DEFAULT_LIST_K
                lines = self.store.catalog_lines(self.circuit, prefix, k)
                self.log("list", agent=agent.task_id, prefix=prefix, k=k, returned=len(lines))
                observations.append(
                    f"LIST {prefix or '(all)'} (k={k}):\n" + ("\n".join(lines) if lines else "(no pins)")
                )
                continue
            if kind == "FETCH":
                chunks = []
                for address in parsed["addresses"]:
                    text, used = self.store.fetch(address, agent.task_id, fetch_budget)
                    fetch_budget -= used
                    chunks.append(f"### {address}\n{text}")
                observations.append(
                    f"FETCH results (routing fetch budget remaining: {fetch_budget} chars):\n"
                    + "\n\n".join(chunks)
                )
                continue
            (self.out_dir / "raw").mkdir(exist_ok=True)
            (self.out_dir / "raw" / f"{agent.task_id.replace('/', '_')}.txt").write_text(
                raw + "\n", encoding="utf-8")
            self.log("route", agent=agent.task_id, action=parsed)
            return parsed
        self.log("route_invalid", agent=agent.task_id, notes=notes, raw=raw)
        return None

    # ---- SPAWN ------------------------------------------------------------

    @staticmethod
    def _expand_outputs(outputs: list[dict[str, Any]]) -> list[dict[str, str]]:
        expanded: list[dict[str, str]] = []
        for output in outputs:
            for concrete in addresses.expand_family(str(output["path"])):
                expanded.append({"path": concrete, "description": str(output["description"])})
        return expanded

    def _materialize_pins(self, outputs: list[dict[str, str]], owner: str, owed: set[str], act: str) -> None:
        """A2 uniform rule: pins exist from the authoring act onward.
        An owed (inherited-interface) pin already exists — delegation
        re-owns it; everything else is a fresh pin."""
        for output in outputs:
            path = output["path"]
            existing = self.circuit.pin(path)
            if existing is None:
                self.circuit.create_pin(path, owner, act=act, note=output["description"])
            elif path in owed and existing["owner"] != owner and existing["status"] != "done":
                self.circuit.reassign_pin(path, owner, mechanism="delegation")

    def spawn(self, agent: AgentSpec, action: dict[str, Any]) -> None:
        owed = {o["path"] for o in agent.expected_outputs if isinstance(o, dict) and "path" in o}
        mechanism = "root-spawn" if agent.task_id == "root" else "deep-spawn"
        for subtask in action["subtasks"]:
            child_outputs = self._expand_outputs(subtask["outputs"])
            child = AgentSpec(
                task_id=str(subtask["id"]),
                root_goal=agent.root_goal,
                task=str(subtask["goal"]),
                capsule=str(subtask["capsule"]),
                depth=agent.depth + 1,
                parent=agent.task_id,
                expected_outputs=child_outputs,
                condition=subtask.get("condition"),
                system=agent.system,
            )
            state = "promised" if child.condition else "queued"
            self.circuit.create_agent(child.task_id, state, child.depth, agent.task_id,
                                      json.dumps(asdict(child)))
            self._materialize_pins(child_outputs, child.task_id, owed, act="spawn")
            self.log("spawn", parent=agent.task_id, child=asdict(child))
            if child.condition:
                self.circuit.add_gate(
                    f"{self.run_id}:{child.task_id}", child.condition,
                    {"kind": "enqueue", "agent": asdict(child)},
                    author=agent.task_id, mechanism=mechanism,
                )
            else:
                self.enqueue(child)

        role = action["self_role"]
        role_outputs = self._expand_outputs(role["outputs"])
        condition = role.get("condition")
        condition = condition if isinstance(condition, str) and condition.strip() else None
        continuation = AgentSpec(
            task_id=agent.task_id,
            root_goal=agent.root_goal,
            task=str(role.get("goal", "")),
            capsule=agent.capsule,
            depth=agent.depth,
            parent=agent.parent,
            expected_outputs=role_outputs,
            condition=condition,
            worker_only=True,
            system=agent.system,
        )
        self._materialize_pins(role_outputs, agent.task_id, owed, act="self_role")
        self.circuit.set_agent_spec(agent.task_id, json.dumps(asdict(continuation)))
        self.log("self_role", agent=agent.task_id, kind="gated" if condition else "parallel",
                 condition=condition, outputs=[o["path"] for o in role_outputs])
        if condition:
            # gate first, then sleep: a sleeping agent without an installed
            # wake gate is unrepresentable (B7).
            self.circuit.add_gate(
                f"{self.run_id}:{agent.task_id}:self", condition,
                {"kind": "enqueue", "agent": asdict(continuation)},
                author=agent.task_id, mechanism="self_role-gate",
            )
            self.circuit.set_agent_state(agent.task_id, "sleeping")
        else:
            self.enqueue(continuation)

    # ---- DEFER --------------------------------------------------------------

    def defer(self, agent: AgentSpec, action: dict[str, Any]) -> None:
        wake = str(action["wake_condition"])
        self.defer_seq += 1
        sleeper = AgentSpec(**{**asdict(agent), "condition": wake})
        self.circuit.set_agent_spec(agent.task_id, json.dumps(asdict(sleeper)))
        self.log("defer", agent=agent.task_id, wake_condition=wake)
        self.circuit.add_gate(
            f"{self.run_id}:{agent.task_id}:defer{self.defer_seq}", wake,
            {"kind": "enqueue", "agent": asdict(sleeper)},
            author=agent.task_id, mechanism="defer-wake",
        )
        self.circuit.set_agent_state(agent.task_id, "sleeping")

    # ---- EXECUTE --------------------------------------------------------------

    def worker_context(self, agent: AgentSpec, declared: list[dict[str, str]]) -> str:
        catalog: list[str] = []
        for ns in addresses.ancestor_namespaces(agent.task_id):
            catalog.extend(self.store.catalog_lines(self.circuit, ns, CATALOG_CONTEXT_K))
        catalog = list(dict.fromkeys(catalog))[:CATALOG_CONTEXT_K * 2]
        # provisioned fetches, priority-ordered, within the worker budget
        budget = WORKER_FETCH_BUDGET
        wanted: list[str] = []
        wanted += gate_refs(agent.condition or "")[0]
        wanted += sorted(addresses.scan_addresses(agent.capsule))
        for ns in reversed(addresses.ancestor_namespaces(agent.task_id)):
            wanted += [p["address"] for p in self.circuit.pins_in_namespace(ns) if p["status"] == "done"]
        fetched: list[str] = []
        seen: set[str] = set()
        for address in wanted:
            if address in seen or budget < 200:
                continue
            seen.add(address)
            if not self.store.exists(address):
                continue
            text, used = self.store.fetch(address, agent.task_id, budget)
            budget -= used
            fetched.append(f"### {address}\n{text}")
        return "\n".join([
            f"ROOT GOAL: {agent.root_goal}",
            f"YOUR TASK ID: {agent.task_id}",
            f"YOUR TASK: {agent.task}",
            f"DECLARED OUTPUT PINS: {json.dumps(declared, ensure_ascii=False)}",
            "CATALOG (address · status · summary):",
            "\n".join(catalog) if catalog else "(no pins)",
            "FETCHED MEMORY:",
            "\n\n".join(fetched) if fetched else "(nothing fetched)",
        ])

    def execute(self, agent: AgentSpec, action: dict[str, Any]) -> None:
        declared = agent.expected_outputs or self._expand_outputs(action.get("result_outputs", []))
        owed = {o["path"] for o in agent.expected_outputs if isinstance(o, dict) and "path" in o}
        # A2 act 3: pins exist during the worker call — the leaf's
        # in-flight work is visible and reservable.
        self._materialize_pins(declared, agent.task_id, owed, act="execute")
        self.circuit.set_agent_state(agent.task_id, "executing")
        worker = self.induction.worker_result(self.circuit, agent, declared) if self.induction else None
        if worker is not None:
            # EM3 H1/H3: mechanized worker outcome; the model is not called.
            self.log("induction_worker", mode=self.induction.mode, agent=agent.task_id,
                     detail=self.induction.detail)
        else:
            prompt = self.worker_context(agent, declared)
            worker = self.call_worker(prompt, [o["path"] for o in declared])
        returned: dict[str, dict[str, Any]] = {}
        if isinstance(worker, dict):
            for item in worker.get("outputs", []):
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    returned[item["path"]] = item

        for output in declared:
            path = output["path"]
            item = returned.get(path)
            if item is None:
                self.log("schema_mismatch", agent=agent.task_id, declared=path,
                         returned=sorted(returned))
                body = json.dumps(worker, ensure_ascii=False)[:4000] if worker else "(worker returned nothing usable)"
                self.store.write(path, "(fallback: worker omitted this pin)", body,
                                 agent.task_id, "worker_invalid" if worker is None else "fallback")
                self.circuit.fulfill(path)
            elif item.get("failed"):
                reason = str(item.get("reason", "(no reason given)"))
                self.store.record_failure(path, reason, agent.task_id)
                self.circuit.fulfill(path, failed=True)
            else:
                value = str(item.get("value", ""))
                provenance = "worker"
                if len(value) > SINGLE_EMISSION_MAX:
                    # A5 output rule survived repair attempts: mark it.
                    provenance = "oversize_fallback"
                self.store.write(path, str(item.get("summary", "")), value,
                                 agent.task_id, provenance)
                self.circuit.fulfill(path)
            self.circuit.fire_ready(self._enqueue_consequence)  # B1: re-eval after every fulfillment

        # promotion (A2 act 4): declare-and-write in one act, own namespace only
        for path, item in returned.items():
            if path in {o["path"] for o in declared}:
                continue
            if (addresses.valid_address(path, system=agent.system)
                    and path.startswith(f"{agent.task_id}/")
                    and self.circuit.pin(path) is None
                    and not item.get("failed")):
                self.circuit.create_pin(path, agent.task_id, act="promotion",
                                        note=str(item.get("summary", ""))[:160])
                self.store.write(path, str(item.get("summary", "")), str(item.get("value", "")),
                                 agent.task_id, "promotion")
                self.circuit.fulfill(path)
                self.promotions += 1
                self.log("promotion", agent=agent.task_id, path=path)
                self.circuit.fire_ready(self._enqueue_consequence)
            else:
                self.log("write_rejected", agent=agent.task_id, path=path)
        self.circuit.set_agent_state(agent.task_id, "done")

    def call_worker(self, prompt: str, declared_paths: list[str]) -> dict[str, Any] | None:
        raw = ""
        message = prompt
        for attempt in range(WORKER_ATTEMPTS):
            self.llm_calls += 1
            raw = call_model(self.worker_prompt, message, self.config)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            notes = self._worker_notes(parsed, declared_paths)
            if parsed is not None and not notes:
                return parsed
            if attempt == WORKER_ATTEMPTS - 1 and isinstance(parsed, dict):
                # last attempt: accept what exists; missing/oversize paths
                # get fallback-marked in execute() — mechanical, never silent
                self.log("worker_accepted_with_notes", notes=notes)
                return parsed
            message = build_repair_message(prompt, raw, notes or ["worker output must be a JSON object with an outputs list"])
        self.log("worker_invalid", raw=raw[:2000])
        return None

    @staticmethod
    def _worker_notes(parsed: Any, declared_paths: list[str]) -> list[str]:
        if not isinstance(parsed, dict) or not isinstance(parsed.get("outputs"), list):
            return ["worker output must be a JSON object with an outputs list"]
        notes: list[str] = []
        seen: set[str] = set()
        for item in parsed["outputs"]:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                notes.append("every outputs item needs a string path")
                continue
            path = item["path"]
            seen.add(path)
            if item.get("failed"):
                if not isinstance(item.get("reason"), str) or not item["reason"].strip():
                    notes.append(f"{path}: failed output needs a non-empty reason")
                continue
            if not isinstance(item.get("summary"), str) or not item["summary"].strip():
                notes.append(f"{path}: missing non-empty summary (<= {SUMMARY_MAX} chars)")
            elif len(item["summary"]) > SUMMARY_MAX:
                notes.append(f"{path}: summary is {len(item['summary'])} chars; cap is {SUMMARY_MAX}")
            value = item.get("value")
            if not isinstance(value, str):
                notes.append(f"{path}: missing string value")
            elif len(value) > SINGLE_EMISSION_MAX:
                notes.append(
                    f"{path}: value is {len(value)} chars — over the {SINGLE_EMISSION_MAX} single-emission cap; "
                    "condense it, or report failed:true with a reason if the artifact cannot fit"
                )
        missing = [p for p in declared_paths if p not in seen]
        if missing:
            notes.append("missing declared output pins: " + ", ".join(missing))
        return notes

    # ---- the doctor -------------------------------------------------------------

    def doctor_cycle(self, report: dict[str, Any]) -> bool:
        self.doctor_cycles += 1
        cycle = self.doctor_cycles
        dossier = build_dossier(self.circuit, self.store, self.prior_cycles)
        text = dossier_text(dossier)
        # B6: system facts are runtime-written (open-read lets agents see them)
        address = f"_system/dossier_{cycle}"
        self.circuit.create_pin(address, "_system", act="system", note=f"doctor cycle {cycle} dossier")
        self.store.write(address, f"doctor cycle {cycle} dossier", text, "_system", "system")
        self.circuit.fulfill(address)
        self.log("doctor_start", cycle=cycle, dossier_chars=len(text))

        prompt = "\n".join([
            f"ROOT GOAL: {self.root_task['task']}",
            f"DOCTOR CYCLE: {cycle} of {DOCTOR_K}",
            f"GLOBAL CALLS REMAINING: {max(0, self.max_calls - self.llm_calls)}",
            f"NEXT REPAIR AGENT INDEX: {self.repair_index} (ids must be _doctor.{self.repair_index}, _doctor.{self.repair_index + 1}, ...)",
            "DOSSIER (mechanically derived):",
            text,
        ])
        raw, doc, notes = "", None, []
        for attempt in range(DOCTOR_ATTEMPTS):
            message = prompt if attempt == 0 else build_repair_message(prompt, raw, notes)
            self.llm_calls += 1
            self.doctor_calls += 1
            raw = call_model(self.doctor_prompt, message, self.config)
            doc, notes = validate_repair(raw, self.circuit, self.repair_index)
            if doc is not None and not notes:
                break
            self.log("doctor_repair", cycle=cycle, attempt=attempt + 1, notes=notes)
        if doc is None or notes:
            self.log("doctor_invalid", cycle=cycle, notes=notes, raw=raw[:2000])
            self.prior_cycles.append({"cycle": cycle, "valid": False, "notes": notes})
            return False

        applied = {"repair_agents": [], "wake_overrides": []}
        for spec_doc in doc.get("repair_agents") or []:
            repair_id = str(spec_doc["id"])
            outputs = self._expand_outputs(spec_doc["outputs"])
            condition = spec_doc.get("condition")
            condition = condition if isinstance(condition, str) and condition.strip() else None
            spec = AgentSpec(
                task_id=repair_id, root_goal=self.root_task["task"],
                task=str(spec_doc["goal"]), capsule=str(spec_doc["capsule"]),
                depth=1, parent="_doctor", expected_outputs=outputs,
                condition=condition, system=True,
            )
            state = "promised" if condition else "queued"
            self.circuit.create_agent(repair_id, state, 1, "_doctor", json.dumps(asdict(spec)))
            for output in outputs:
                existing = self.circuit.pin(output["path"])
                if existing is None:
                    self.circuit.create_pin(output["path"], repair_id, act="spawn",
                                            note=output["description"])
                elif existing["status"] != "done":
                    # corrective: re-own the unfulfilled pin (C3)
                    self.circuit.reassign_pin(output["path"], repair_id, mechanism="doctor-repair")
            if condition:
                self.circuit.add_gate(f"{self.run_id}:{repair_id}", condition,
                                      {"kind": "enqueue", "agent": asdict(spec)},
                                      author="_doctor", mechanism="doctor-repair")
            else:
                self.enqueue(spec)
            applied["repair_agents"].append(repair_id)
            self.repair_index += 1

        for override in doc.get("wake_overrides") or []:
            agent_id = str(override["agent_id"])
            row = self.circuit.agent_row(agent_id)
            sleeper = AgentSpec(**json.loads(row["spec"]))
            condition = override.get("condition")
            if isinstance(condition, str) and condition.strip():
                # additive: the original wake gate is never retired (B3);
                # a corrected doctor-repair gate is installed beside it.
                self.circuit.add_gate(f"{self.run_id}:{agent_id}:doctor{cycle}", condition,
                                      {"kind": "enqueue", "agent": asdict(sleeper)},
                                      author="_doctor", mechanism="doctor-repair")
                if row["state"] == "starved":
                    self.circuit.set_agent_state(agent_id, "sleeping")
            else:
                self.enqueue(sleeper)  # the DEFER re-enqueue pattern
            applied["wake_overrides"].append(agent_id)

        self.prior_cycles.append({"cycle": cycle, "valid": True,
                                  "reasoning": str(doc.get("reasoning", "")), **applied})
        self.log("doctor_action", cycle=cycle, **applied)
        self.circuit.refresh_liveness(trigger="doctor-repair")
        return True

    # ---- metrics (C4 accounting) -----------------------------------------------

    def metrics(self) -> RunMetrics:
        final = self.circuit.failure_report(self.store.fallback_writes())
        counts = self.circuit.counts()
        store_counts = self.store.counts()
        root_pins = sorted(r[0] for r in self.db.execute("SELECT address FROM pins WHERE address LIKE 'root/%'"))
        done = self.circuit.done_addresses()
        root_done = [p for p in root_pins if p in done]
        clean = bool(root_pins) and not final["failing"] and not self.rail_hit
        if clean:
            outcome = "converged-with-repair" if self.doctor_cycles else "converged"
        else:
            outcome = "failed"
        starved = [a["agent_id"] for a in self.circuit.agents_in_state("starved")]
        max_depth = self.db.execute("SELECT COALESCE(MAX(depth), 0) FROM agents").fetchone()[0]
        agent_count = self.db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        defer_count = self.defer_seq
        qualitative = self._qualitative(outcome, final)
        return RunMetrics(
            run_id=self.run_id,
            task_id=self.root_task["id"],
            outcome=outcome,
            converged=clean,
            termination="rail" if self.rail_hit else "natural",
            rail_hit=self.rail_hit,
            llm_calls=self.llm_calls,
            agent_count=agent_count,
            max_depth=int(max_depth),
            doctor_cycles=self.doctor_cycles,
            root_pins=root_pins,
            root_pins_done=root_done,
            pins_total=counts["pins_total"],
            pins_done=counts["pins_done"],
            pins_failed=counts["pins_failed"],
            pins_abandoned=counts["pins_abandoned"],
            gates_total=counts["gates_total"],
            gates_fired=counts["gates_fired"],
            gates_dead=counts["gates_dead"],
            conflict_count=store_counts["conflicts"],
            fallback_writes=len(final["fallback_writes"]),
            entry_count=store_counts["entries"],
            fetch_count=store_counts["fetches"],
            defer_count=defer_count,
            promotion_count=self.promotions,
            starved_agents=starved,
            failure=final,
            interleaving=self.interleaving,
            qualitative=qualitative,
            doctor_calls=self.doctor_calls,
            induction=({"mode": self.induction.mode, "target": self.induction.target,
                        "fired": self.induction.fired, "detail": self.induction.detail}
                       if self.induction else None),
        )

    def _qualitative(self, outcome: str, final: dict[str, Any]) -> str:
        if outcome == "converged":
            return "Quiesced clean on the first pass: all root pins fulfilled, no dead gates, no fallback writes."
        if outcome == "converged-with-repair":
            return f"Systemic failure at first quiescence repaired by the doctor in {self.doctor_cycles} cycle(s); final predicate clean."
        parts = []
        if self.rail_hit:
            parts.append(f"rail hit ({self.rail_hit})")
        if final["unmet_root_pins"]:
            parts.append(f"{len(final['unmet_root_pins'])} unmet root pins")
        if final["dead_gates"]:
            parts.append(f"{len(final['dead_gates'])} dead gates")
        if final["abandoned_pins"]:
            parts.append(f"{len(final['abandoned_pins'])} abandoned pins")
        if final["fallback_writes"]:
            parts.append(f"{len(final['fallback_writes'])} fallback-marked writes")
        return "Failed: " + (", ".join(parts) if parts else "predicate failing at exhaustion") + "."


# ---- CLI ----------------------------------------------------------------------

def select_tasks(path: Path, task_ids: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    tasks = load_json(path)
    if not task_ids:
        return tasks
    by_id = {task["id"]: task for task in tasks}
    return [by_id[tid] for tid in task_ids]


def run_cli(args: argparse.Namespace) -> int:
    config = Config(args.provider, args.model, args.temperature, args.max_tokens, args.local_endpoint)
    ensure_credentials(config)
    prompts = {
        "harness": Path(args.harness).read_text(encoding="utf-8"),
        "worker": Path(args.worker_prompt).read_text(encoding="utf-8"),
        "doctor": Path(args.doctor_prompt).read_text(encoding="utf-8"),
    }
    base = Path(args.out_dir)
    task_ids = tuple(t for t in args.task_ids.split(",") if t)
    all_metrics: list[RunMetrics] = []
    for task in select_tasks(Path(args.tasks), task_ids):
        for rep in range(1, args.repetitions + 1):
            run_id = f"{task['id']}_r{rep}"
            run_dir = base / run_id
            metrics_path = run_dir / "metrics.json"
            if metrics_path.exists():
                print(f"skipping {run_id} (completed; metrics.json exists — delete the dir to rerun)", flush=True)
                all_metrics.append(RunMetrics(**load_json(metrics_path)))
                continue
            if run_dir.exists():
                print(f"clearing partial {run_id} (no metrics.json; stale trace/state would corrupt the rerun)", flush=True)
                shutil.rmtree(run_dir)
            print(f"running {run_id}...", flush=True)
            runtime = Runtime(run_id, task, prompts, config, run_dir,
                              list_enabled=not args.no_list)
            metrics = runtime.run()
            all_metrics.append(metrics)
            print(f"  {run_id}: {metrics.outcome} ({metrics.llm_calls} calls, "
                  f"{metrics.pins_done}/{metrics.pins_total} pins done, "
                  f"doctor cycles {metrics.doctor_cycles})", flush=True)
    write_summary(base, all_metrics)
    return 0


def write_summary(base: Path, metrics: list[RunMetrics]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    write_json(base / "summary.json", [asdict(m) for m in metrics])
    lines = [
        "# Memory/Circuit runtime summary",
        "",
        f"- Runs: {len(metrics)}",
        f"- converged: {sum(1 for m in metrics if m.outcome == 'converged')}",
        f"- converged-with-repair: {sum(1 for m in metrics if m.outcome == 'converged-with-repair')}",
        f"- failed: {sum(1 for m in metrics if m.outcome == 'failed')}",
        f"- Dead gates (total): {sum(m.gates_dead for m in metrics)}",
        f"- Abandoned pins (total): {sum(m.pins_abandoned for m in metrics)}",
        f"- Fallback writes (total): {sum(m.fallback_writes for m in metrics)}",
        f"- Conflicts (total): {sum(m.conflict_count for m in metrics)}",
        f"- Promotions (total): {sum(m.promotion_count for m in metrics)}",
        "",
        "## Runs",
        "",
    ]
    for m in metrics:
        lines.extend([
            f"### {m.run_id}",
            "",
            f"- Outcome: {m.outcome} ({m.termination}{f', {m.rail_hit}' if m.rail_hit else ''})",
            f"- Root pins done: {len(m.root_pins_done)}/{len(m.root_pins)}",
            f"- Pins: {m.pins_done} done / {m.pins_failed} failed / {m.pins_abandoned} abandoned of {m.pins_total}",
            f"- Gates: {m.gates_fired} fired / {m.gates_dead} dead of {m.gates_total}",
            f"- LLM calls: {m.llm_calls}; agents: {m.agent_count}; depth: {m.max_depth}",
            f"- Doctor cycles: {m.doctor_cycles}; defers: {m.defer_count}; promotions: {m.promotion_count}",
            f"- Qualitative: {m.qualitative}",
            "",
        ])
    (base / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="RATD runtime on the rebuilt memory/circuit layer (spec v1.0)")
    parser.add_argument("--harness", default="prompts/harness_v7.md")
    parser.add_argument("--worker-prompt", default="prompts/worker_v7.md")
    parser.add_argument("--doctor-prompt", default="prompts/doctor_v1.md")
    parser.add_argument("--tasks", default="tasks/e1_ladder.json")
    parser.add_argument("--task-ids", default="", help="comma-separated; empty = all")
    parser.add_argument("--out-dir", default="results/mc0")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--no-list", action="store_true",
                        help="EM1 Arm B: remove LIST from the action space")
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint", default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_cli(args)
    except RuntimeError as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
