from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .phase1 import (
    DEFAULT_LOCAL_ENDPOINT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    Config,
    build_repair_message,
    call_model,
    condition_refs,
    ensure_credentials,
    load_json,
    write_json,
)


PHASE2_TASK_IDS = ("t06", "t15", "t09")
WORKER_PROMPT = """You are a worker agent in a shared-memory multi-agent run.
Complete the assigned task using the relevant memory provided. Return strict JSON only:
{
  "outputs": [
    {"path": "<declared path>", "value": "<artifact text>"}
  ]
}
Write every declared output path exactly. Keep artifact text concise but useful."""


@dataclass
class AgentSpec:
    task_id: str
    root_goal: str
    task: str
    capsule: str
    budget: int
    depth: int
    parent: str | None
    expected_outputs: list[dict[str, str]]
    condition: str | None = None


@dataclass
class RunMetrics:
    run_id: str
    task_id: str
    converged: bool
    root_outputs: list[str]
    root_outputs_done: list[str]
    llm_calls: int
    max_depth: int
    agent_count: int
    conflict_count: int
    budget_violations: int
    schema_mismatches: int
    trigger_refs: int
    schema_agreements: int
    trigger_fire_errors: int
    trigger_never_fired_ready: int
    defer_count: int
    cross_branch_reads: int
    rail_hit: str
    qualitative: str


class ConditionParser:
    def __init__(self, text: str, done: set[str]):
        self.tokens = self._scan(text)
        self.done = done
        self.i = 0

    def parse(self) -> bool:
        value = self._expr()
        if self.i != len(self.tokens):
            raise ValueError(f"unexpected token {self.tokens[self.i]}")
        return value

    def _expr(self) -> bool:
        value = self._term()
        while self._peek() == "OR":
            self.i += 1
            rhs = self._term()
            value = value or rhs
        return value

    def _term(self) -> bool:
        value = self._factor()
        while self._peek() == "AND":
            self.i += 1
            rhs = self._factor()
            value = value and rhs
        return value

    def _factor(self) -> bool:
        token = self._peek()
        if token == "(":
            self.i += 1
            value = self._expr()
            self._expect(")")
            return value
        if isinstance(token, tuple) and token[0] == "DONE":
            self.i += 1
            return token[1] in self.done
        raise ValueError(f"expected factor, got {token}")

    def _peek(self) -> Any:
        if self.i >= len(self.tokens):
            return None
        return self.tokens[self.i]

    def _expect(self, token: str) -> None:
        if self._peek() != token:
            raise ValueError(f"expected {token}, got {self._peek()}")
        self.i += 1

    @staticmethod
    def _scan(text: str) -> list[Any]:
        tokens: list[Any] = []
        i = 0
        while i < len(text):
            if text[i].isspace():
                i += 1
            elif text.startswith("AND", i):
                tokens.append("AND")
                i += 3
            elif text.startswith("OR", i):
                tokens.append("OR")
                i += 2
            elif text[i] in "()":
                tokens.append(text[i])
                i += 1
            elif text.startswith('done("', i):
                j = text.find('")', i + 6)
                if j < 0:
                    raise ValueError("unterminated done()")
                tokens.append(("DONE", text[i + 6 : j]))
                i = j + 2
            else:
                raise ValueError(f"cannot tokenize condition near {text[i:i+20]!r}")
        return tokens


class Runtime:
    def __init__(self, run_id: str, root_task: dict[str, Any], harness: str, config: Config, out_dir: Path):
        self.run_id = run_id
        self.root_task = root_task
        self.harness = harness
        self.config = config
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.out_dir / "trace.jsonl"
        self.db = sqlite3.connect(self.out_dir / "state.sqlite")
        self.queue: list[AgentSpec] = []
        self.llm_calls = 0
        self.defer_seq = 0
        self.agent_count = 0
        self.root_outputs: list[str] = []
        self.rail_hit = ""
        self.started = time.time()
        self.max_calls = 60
        self.max_depth = 6
        self.wall_clock = 20 * 60
        self._init_db()

    def _init_db(self) -> None:
        cur = self.db.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS entries(namespace_key TEXT PRIMARY KEY, value TEXT, status TEXT, author TEXT, created_at REAL)")
        cur.execute("CREATE TABLE IF NOT EXISTS conflicts(namespace_key TEXT, attempted_value TEXT, author TEXT, created_at REAL)")
        cur.execute("CREATE TABLE IF NOT EXISTS triggers(id TEXT PRIMARY KEY, condition TEXT, agent_spec TEXT, fired INTEGER DEFAULT 0)")
        self.db.commit()

    def run(self) -> RunMetrics:
        root = AgentSpec("root", self.root_task["task"], self.root_task["task"], "(you are the root agent)", 20, 0, None, [])
        self.enqueue(root)
        while self.queue:
            if self._rails_hit():
                break
            agent = self.queue.pop(0)
            self.agent_count += 1
            self.log("agent_start", agent=asdict(agent))
            action = self.route(agent)
            if action is None:
                continue
            kind = action.get("action")
            if kind == "EXECUTE":
                self.execute(agent, action)
            elif kind == "SPAWN":
                self.spawn(agent, action)
            elif kind == "DEFER":
                wake = action.get("wake_condition")
                self.log("defer", agent=agent.task_id, wake_condition=wake)
                if isinstance(wake, str) and wake.strip():
                    self.defer_seq += 1
                    sleeper = AgentSpec(**{**asdict(agent), "condition": wake})
                    self.add_trigger(f"{self.run_id}:{agent.task_id}:defer{self.defer_seq}", wake, sleeper)
            self.fire_ready_triggers()
        self.render_graph()
        metrics = self.metrics()
        write_json(self.out_dir / "metrics.json", asdict(metrics))
        return metrics

    def _rails_hit(self) -> bool:
        if self.llm_calls >= self.max_calls:
            self.rail_hit = "max_llm_calls"
        elif time.time() - self.started > self.wall_clock:
            self.rail_hit = "wall_clock"
        elif any(agent.depth > self.max_depth for agent in self.queue):
            self.rail_hit = "max_depth"
        if self.rail_hit:
            self.log("rail_hit", rail=self.rail_hit)
            return True
        return False

    def enqueue(self, agent: AgentSpec) -> None:
        self.queue.append(agent)
        self.log("enqueue", agent=asdict(agent))

    def route(self, agent: AgentSpec) -> dict[str, Any] | None:
        message = self.context(agent)
        raw = ""
        notes: list[str] = []
        parsed: dict[str, Any] | None = None
        for attempt in range(3):
            prompt = message if attempt == 0 else build_repair_message(message, raw, notes)
            self.llm_calls += 1
            raw = call_model(self.harness, prompt, self.config)
            parsed, notes = parse_and_validate_action_for_agent(raw, agent)
            if parsed is not None and not notes:
                break
            self.log("route_repair", agent=agent.task_id, attempt=attempt + 1, notes=notes)
        (self.out_dir / "raw").mkdir(exist_ok=True)
        (self.out_dir / "raw" / f"{agent.task_id}.txt").write_text(raw + "\n", encoding="utf-8")
        if parsed is None or notes:
            self.log("route_invalid", agent=agent.task_id, notes=notes, raw=raw)
            return None
        self.log("route", agent=agent.task_id, action=parsed)
        return parsed

    def context(self, agent: AgentSpec) -> str:
        entries = self.visible_entries(agent)
        if entries:
            memory = "\n".join(f"- {k}: {v[:700]}" for k, v in entries)
        else:
            memory = "(empty)"
        expected = json.dumps(agent.expected_outputs, ensure_ascii=False)
        return "\n".join(
            [
                f"ROOT GOAL: {agent.root_goal}",
                f"YOUR TASK ID: {agent.task_id}",
                f"YOUR TASK: {agent.task}",
                f"YOUR CAPSULE (why you exist): {agent.capsule}",
                f"REMAINING BUDGET: {agent.budget}",
                f"EXPECTED OUTPUTS FROM PARENT: {expected}",
                f"RELEVANT MEMORY (exact namespace/context listing): {memory}",
            ]
        )

    def visible_entries(self, agent: AgentSpec) -> list[tuple[str, str]]:
        cur = self.db.execute("SELECT namespace_key, value FROM entries WHERE status='done' ORDER BY namespace_key")
        rows = [(str(k), str(v)) for k, v in cur.fetchall()]
        prefixes = {f"{ns}/" for ns in self.ancestor_namespaces(agent.task_id)}
        named = set(condition_refs(agent.condition or ""))
        named.update(extract_paths(agent.capsule))
        visible = [(k, v) for k, v in rows if any(k.startswith(p) for p in prefixes) or k in named]
        for path, _ in visible:
            if self.is_cross_branch(agent.task_id, path):
                self.log("cross_branch_read", agent=agent.task_id, path=path)
        return visible

    @staticmethod
    def ancestor_namespaces(task_id: str) -> list[str]:
        parts = task_id.split(".")
        return [".".join(parts[:i]) for i in range(1, len(parts) + 1)]

    @staticmethod
    def is_cross_branch(task_id: str, path: str) -> bool:
        task_parts = task_id.split(".")
        path_ns = path.split("/")[0].split(".")
        return len(task_parts) > 1 and len(path_ns) > 1 and task_parts[1] != path_ns[1]

    def spawn(self, agent: AgentSpec, action: dict[str, Any]) -> None:
        subtasks = action.get("subtasks", [])
        if not isinstance(subtasks, list):
            return
        allowed = max(0, agent.budget - len(subtasks))
        allocated = sum(int(s.get("budget", 0)) for s in subtasks if isinstance(s, dict))
        if allocated > allowed:
            self.log("budget_violation", agent=agent.task_id, allocated=allocated, allowed=allowed)
        for idx, subtask in enumerate(subtasks, start=1):
            if not isinstance(subtask, dict):
                continue
            budget = int(subtask.get("budget", 0))
            if allocated > allowed:
                budget = max(0, min(budget, allowed // max(1, len(subtasks))))
            child = AgentSpec(
                task_id=str(subtask["id"]),
                root_goal=agent.root_goal,
                task=str(subtask["goal"]),
                capsule=str(subtask["capsule"]),
                budget=budget,
                depth=agent.depth + 1,
                parent=agent.task_id,
                expected_outputs=list(subtask.get("outputs", [])),
                condition=subtask.get("condition"),
            )
            self.log("spawn", parent=agent.task_id, child=asdict(child))
            if agent.task_id == "root" and child.condition:
                self.root_outputs.extend(out["path"] for out in child.expected_outputs if isinstance(out, dict) and "path" in out)
            if child.condition:
                self.add_trigger(f"{self.run_id}:{child.task_id}", child.condition, child)
            else:
                self.enqueue(child)

    def add_trigger(self, trigger_id: str, condition: str, agent: AgentSpec) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO triggers(id, condition, agent_spec, fired) VALUES (?, ?, ?, 0)",
            (trigger_id, condition, json.dumps(asdict(agent))),
        )
        self.db.commit()
        self.log("trigger_add", id=trigger_id, condition=condition, agent=agent.task_id)

    def fire_ready_triggers(self) -> None:
        rows = self.db.execute("SELECT id, condition, agent_spec FROM triggers WHERE fired=0").fetchall()
        done = self.done_paths()
        for trigger_id, condition, agent_json in rows:
            try:
                ready = ConditionParser(str(condition), done).parse()
            except ValueError as exc:
                self.log("trigger_error", id=trigger_id, condition=condition, error=str(exc))
                continue
            if not ready:
                continue
            cur = self.db.execute("UPDATE triggers SET fired=1 WHERE id=? AND fired=0", (trigger_id,))
            self.db.commit()
            if cur.rowcount == 1:
                agent = AgentSpec(**json.loads(agent_json))
                self.log("trigger_fire", id=trigger_id, condition=condition, agent=agent.task_id)
                self.enqueue(agent)

    def execute(self, agent: AgentSpec, action: dict[str, Any]) -> None:
        declared = agent.expected_outputs or list(action.get("result_outputs", []))
        prompt = "\n".join(
            [
                f"ROOT GOAL: {agent.root_goal}",
                f"YOUR TASK ID: {agent.task_id}",
                f"YOUR TASK: {agent.task}",
                f"DECLARED OUTPUTS: {json.dumps(declared, ensure_ascii=False)}",
                "RELEVANT MEMORY:",
                "\n".join(f"- {k}: {v[:1000]}" for k, v in self.visible_entries(agent)) or "(empty)",
            ]
        )
        worker = self.call_worker(prompt)
        returned = worker.get("outputs", []) if isinstance(worker, dict) else []
        by_path = {o.get("path"): o.get("value", "") for o in returned if isinstance(o, dict)}
        for output in declared:
            if not isinstance(output, dict) or "path" not in output:
                continue
            path = str(output["path"])
            value = str(by_path.get(path, ""))
            if path not in by_path:
                self.log("schema_mismatch", agent=agent.task_id, declared=path, returned=[o.get("path") for o in returned if isinstance(o, dict)])
                value = json.dumps(worker, ensure_ascii=False)[:4000]
            self.write_entry(path, value, agent.task_id)

    def call_worker(self, prompt: str) -> dict[str, Any]:
        raw = ""
        for attempt in range(3):
            self.llm_calls += 1
            raw = call_model(WORKER_PROMPT, prompt, self.config)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and isinstance(parsed.get("outputs"), list):
                return parsed
            prompt = build_repair_message(prompt, raw, ["worker output must be a JSON object with an outputs list"])
        self.log("worker_invalid", raw=raw)
        return {"outputs": []}

    def write_entry(self, path: str, value: str, author: str) -> None:
        now = time.time()
        try:
            self.db.execute("INSERT INTO entries(namespace_key, value, status, author, created_at) VALUES (?, ?, 'done', ?, ?)", (path, value, author, now))
            self.log("write", path=path, author=author, chars=len(value))
        except sqlite3.IntegrityError:
            self.db.execute("INSERT INTO conflicts(namespace_key, attempted_value, author, created_at) VALUES (?, ?, ?, ?)", (path, value, author, now))
            self.log("conflict", path=path, author=author)
        self.db.commit()
        self.fire_ready_triggers()

    def done_paths(self) -> set[str]:
        return {str(row[0]) for row in self.db.execute("SELECT namespace_key FROM entries WHERE status='done'")}

    def log(self, event: str, **data: Any) -> None:
        rec = {"ts": time.time(), "event": event, **data}
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def render_graph(self) -> None:
        edges: list[tuple[str, str, str]] = []
        nodes = {"root"}
        if self.trace_path.exists():
            for line in self.trace_path.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if rec.get("event") == "spawn":
                    parent = rec["parent"]
                    child = rec["child"]["task_id"]
                    nodes.update([parent, child])
                    edges.append((parent, child, "solid"))
                elif rec.get("event") == "trigger_add":
                    agent = rec["agent"]
                    nodes.add(agent)
                    for ref in condition_refs(rec["condition"]):
                        owner = ref.split("/")[0]
                        nodes.add(owner)
                        edges.append((owner, agent, "dashed"))
        dot = ["digraph G {", "rankdir=LR;"]
        for node in sorted(nodes):
            dot.append(f'"{node}" [shape=box];')
        for src, dst, style in edges:
            dot.append(f'"{src}" -> "{dst}" [style={style}];')
        dot.append("}")
        dot_path = self.out_dir / "graph.dot"
        dot_path.write_text("\n".join(dot) + "\n", encoding="utf-8")
        if shutil.which("dot"):
            subprocess.run(["dot", "-Tpng", str(dot_path), "-o", str(self.out_dir / "graph.png")], check=False)

    def metrics(self) -> RunMetrics:
        done = self.done_paths()
        root_done = [p for p in self.root_outputs if p in done]
        trigger_rows = self.db.execute("SELECT condition, fired FROM triggers").fetchall()
        refs = [ref for condition, _ in trigger_rows for ref in condition_refs(str(condition))]
        ready_unfired = 0
        for condition, fired in trigger_rows:
            if not fired and ConditionParser(str(condition), done).parse():
                ready_unfired += 1
        events = [json.loads(line) for line in self.trace_path.read_text(encoding="utf-8").splitlines()] if self.trace_path.exists() else []
        max_depth = max((rec.get("child", {}).get("depth", 0) for rec in events if rec.get("event") == "spawn"), default=0)
        conflicts = self.db.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0]
        schema_mismatch = sum(1 for rec in events if rec.get("event") == "schema_mismatch")
        budget_violations = sum(1 for rec in events if rec.get("event") == "budget_violation")
        trigger_errors = sum(1 for rec in events if rec.get("event") == "trigger_error")
        defers = sum(1 for rec in events if rec.get("event") == "defer")
        cross_reads = sum(1 for rec in events if rec.get("event") == "cross_branch_read")
        converged = bool(self.root_outputs) and set(self.root_outputs).issubset(done) and not self.rail_hit
        qualitative = self.qualitative_assessment(converged, max_depth, budget_violations, schema_mismatch)
        return RunMetrics(
            self.run_id,
            self.root_task["id"],
            converged,
            self.root_outputs,
            root_done,
            self.llm_calls,
            max_depth,
            self.agent_count,
            int(conflicts),
            budget_violations,
            schema_mismatch,
            len(refs),
            sum(1 for ref in refs if ref in done),
            trigger_errors,
            ready_unfired,
            defers,
            cross_reads,
            self.rail_hit,
            qualitative,
        )

    def qualitative_assessment(self, converged: bool, max_depth: int, budget_violations: int, schema_mismatch: int) -> str:
        if not converged:
            return "Did not converge to the declared root output within rails."
        issues = []
        if budget_violations:
            issues.append("budget repairs were needed")
        if schema_mismatch:
            issues.append("worker path mismatches occurred")
        if max_depth >= 2:
            shape = "recursive multi-level graph"
        else:
            shape = "shallow graph"
        suffix = f"; {', '.join(issues)}" if issues else ""
        return f"Converged with a {shape} matching the broad human decomposition{suffix}."


def extract_paths(text: str) -> set[str]:
    return set(re.findall(r"root(?:\.\d+)*/[a-z][a-z0-9_]*", text))


def parse_and_validate_action_for_agent(raw: str, agent: AgentSpec) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        maybe = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"raw strict JSON parse failed: {exc.msg}"]
    if not isinstance(maybe, dict):
        return None, ["raw strict JSON is not an object"]

    notes: list[str] = []
    owed = {o["path"] for o in agent.expected_outputs if isinstance(o, dict) and "path" in o}
    if maybe.get("task_id") != agent.task_id:
        notes.append(f"task_id must be {agent.task_id}")
    reasoning = maybe.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        notes.append("missing non-empty reasoning")
    action = maybe.get("action")
    if action not in {"EXECUTE", "SPAWN", "DEFER"}:
        notes.append("action must be EXECUTE, SPAWN, or DEFER")
        return maybe, notes

    if action == "EXECUTE":
        outputs = maybe.get("result_outputs")
        if not valid_outputs(outputs):
            notes.append("EXECUTE requires result_outputs with path/description")
        else:
            for output in outputs:
                path = output["path"]
                if not path.startswith(f"{agent.task_id}/") and path not in owed:
                    notes.append(f"EXECUTE output {path} must be under {agent.task_id}/ or one of your assigned output paths")
    elif action == "SPAWN":
        subtasks = maybe.get("subtasks")
        if not isinstance(subtasks, list) or not subtasks:
            notes.append("SPAWN requires non-empty subtasks")
        else:
            expected_ids = [f"{agent.task_id}.{i}" for i in range(1, len(subtasks) + 1)]
            seen: set[str] = set()
            child_budgets: list[int] = []
            declared_outputs: set[str] = set()
            for idx, subtask in enumerate(subtasks):
                if not isinstance(subtask, dict):
                    notes.append("subtask must be object")
                    continue
                sid = subtask.get("id")
                if sid != expected_ids[idx]:
                    notes.append(f"subtask id must be {expected_ids[idx]}, got {sid}")
                if isinstance(sid, str) and sid in seen:
                    notes.append(f"duplicate subtask id: {sid}")
                if isinstance(sid, str):
                    seen.add(sid)
                for key in ("goal", "capsule"):
                    if not isinstance(subtask.get(key), str) or not subtask[key].strip():
                        notes.append(f"subtask {sid} missing {key}")
                outputs = subtask.get("outputs")
                if not valid_outputs(outputs):
                    notes.append(f"subtask {sid} requires outputs with path/description")
                elif isinstance(sid, str):
                    for output in outputs:
                        path = output["path"]
                        declared_outputs.add(path)
                        if not path.startswith(f"{sid}/") and path not in owed:
                            notes.append(f"output {path} must be under {sid}/ or one of your own assigned output paths")
                condition = subtask.get("condition")
                if condition is not None and not isinstance(condition, str):
                    notes.append(f"subtask {sid} condition must be null or string")
                budget = subtask.get("budget")
                if not isinstance(budget, int):
                    notes.append(f"subtask {sid} budget must be int")
                else:
                    child_budgets.append(budget)
            missing_interface = owed - declared_outputs
            if missing_interface:
                notes.append(
                    "your assigned output paths "
                    + ", ".join(sorted(missing_interface))
                    + " are not produced by any subtask; assign each to the subtask that completes your task (usually the final integrating subtask)"
                )
            if sum(child_budgets) > agent.budget - len(subtasks):
                notes.append(f"child budget sum {sum(child_budgets)} exceeds {agent.budget - len(subtasks)}")
            if any(b < 0 for b in child_budgets):
                notes.append("negative child budget")
            for subtask in subtasks:
                if not isinstance(subtask, dict) or not isinstance(subtask.get("condition"), str):
                    continue
                for ref in condition_refs(subtask["condition"]):
                    if ref not in declared_outputs:
                        notes.append(f"condition references undeclared sibling output {ref}")
                try:
                    ConditionParser(subtask["condition"], set()).parse()
                except ValueError as exc:
                    notes.append(f"condition uses unsupported syntax: {exc}")
    elif action == "DEFER":
        if not isinstance(maybe.get("wake_condition"), str) or not maybe["wake_condition"].strip():
            notes.append("DEFER requires wake_condition")
    return maybe, notes


def valid_outputs(outputs: Any) -> bool:
    if not isinstance(outputs, list) or not outputs:
        return False
    for output in outputs:
        if not isinstance(output, dict):
            return False
        if not isinstance(output.get("path"), str) or not output["path"].strip():
            return False
        if not isinstance(output.get("description"), str) or not output["description"].strip():
            return False
    return True


def select_tasks(path: Path) -> list[dict[str, Any]]:
    tasks = load_json(path)
    by_id = {task["id"]: task for task in tasks}
    return [by_id[tid] for tid in PHASE2_TASK_IDS]


def run_phase2(args: argparse.Namespace) -> int:
    config = Config(args.provider, args.model, args.temperature, args.max_tokens, args.local_endpoint)
    ensure_credentials(config)
    harness = Path(args.harness).read_text(encoding="utf-8")
    base = Path(args.out_dir)
    all_metrics: list[RunMetrics] = []
    for task in select_tasks(Path(args.tasks)):
        for rep in range(1, args.repetitions + 1):
            run_id = f"{task['id']}_r{rep}"
            print(f"running {run_id}...", flush=True)
            runtime = Runtime(run_id, task, harness, config, base / run_id)
            all_metrics.append(runtime.run())
    write_summary(base, all_metrics)
    return 0


def write_summary(base: Path, metrics: list[RunMetrics]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    rows = [asdict(m) for m in metrics]
    write_json(base / "summary.json", rows)
    converged = sum(1 for m in metrics if m.converged)
    trigger_refs = sum(m.trigger_refs for m in metrics)
    agreements = sum(m.schema_agreements for m in metrics)
    lines = [
        "# Phase 2 Summary",
        "",
        f"- Runs: {len(metrics)}",
        f"- Convergence: {converged}/{len(metrics)}",
        f"- Schema agreement rate: {(agreements / trigger_refs if trigger_refs else 0):.2%} ({agreements}/{trigger_refs})",
        f"- Trigger fire errors: {sum(m.trigger_fire_errors for m in metrics)}",
        f"- Ready-but-unfired triggers: {sum(m.trigger_never_fired_ready for m in metrics)}",
        f"- Conflicts: {sum(m.conflict_count for m in metrics)}",
        f"- Budget violations attempted: {sum(m.budget_violations for m in metrics)}",
        f"- Worker schema mismatches: {sum(m.schema_mismatches for m in metrics)}",
        f"- Rail hits: {sum(1 for m in metrics if m.rail_hit)}",
        f"- Cross-branch reads: {sum(m.cross_branch_reads for m in metrics)}",
        "",
        "## Runs",
        "",
    ]
    for m in metrics:
        lines.extend(
            [
                f"### {m.run_id}",
                "",
                f"- Task: {m.task_id}",
                f"- Converged: {m.converged}",
                f"- Root outputs: {', '.join(m.root_outputs) or '(none)'}",
                f"- Root outputs done: {', '.join(m.root_outputs_done) or '(none)'}",
                f"- LLM calls: {m.llm_calls}",
                f"- Graph depth: {m.max_depth}",
                f"- Agent count: {m.agent_count}",
                f"- Defer count: {m.defer_count}",
                f"- Qualitative: {m.qualitative}",
                "",
            ]
        )
    (base / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RATD Phase 2 sequential runtime")
    parser.add_argument("--harness", default="prompts/harness_v1.md")
    parser.add_argument("--tasks", default="tasks/phase1_tasks.json")
    parser.add_argument("--out-dir", default="results/phase2")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint", default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_phase2(args)
    except RuntimeError as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
