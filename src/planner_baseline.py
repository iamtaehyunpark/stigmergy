"""E1 baseline: replanning central planner (spec 2.2).

One planner loop: after every completed task, ONE planner call receives
the ROOT GOAL + the ENTIRE accumulated state (all done entries, full
values, truncated only by a configurable context budget - truncation
events are themselves a measurement) + the remaining plan, and emits
the updated remaining plan as strict JSON (same task/output/condition
schema as the tree baseline, no capsules). The RATD worker prompt
executes leaves under the same visibility rule as every other system.
No triggers - the planner is the scheduler. Same rails.

Logged per planner call: context chars in (the O(n) curve's y-axis),
plan churn (tasks added/removed/modified vs the previous plan), and
state truncation events.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
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
from .phase2 import ConditionParser, WORKER_PROMPT, valid_outputs
from .tree_baseline import ancestor_prefixes

REPLAN_PROMPT = """You are the central planner of a multi-agent system.
You are called after every completed task with the ROOT GOAL, the full
current shared memory (all completed entries and their contents), and
your previous remaining plan. Emit the UPDATED plan: the complete list
of REMAINING tasks only. You may add, remove, or modify remaining
tasks freely as the state evolves - that is your job as a replanning
planner.

Return strict JSON only. The first character must be { and the last }.
Do not wrap the JSON in Markdown fences.

{
  "tasks": [
    {
      "id": "root.<n>" (or "root.<n>.<m>"),
      "goal": "<one-sentence task goal>",
      "outputs": [ {"path": "<namespace/key>", "description": "..."} ],
      "condition": null | "<boolean expr over done(\\"path\\") terms, AND/OR>"
    }
  ]
}

Rules:
- Do not include completed tasks and do not reuse their ids.
- A task's output paths must start with its own id followed by "/",
  EXCEPT the final integrated deliverable, which must be under "root/".
- condition null starts immediately; a condition may reference paths
  already in memory or declared by other remaining tasks.
- VISIBILITY: a worker sees only memory entries under its own and
  ancestor namespaces PLUS every path named in its condition. If a
  task needs an existing entry as input, name that path in its
  condition or the worker will not see it.
- Keys are short snake_case nouns.
- When the ROOT GOAL is fully delivered under "root/" and nothing
  remains to do, return {"tasks": []}.
"""


def parse_and_validate_replan(raw: str, done: set[str], completed_ids: set[str]) -> tuple[list[dict[str, Any]] | None, list[str]]:
    try:
        maybe = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"raw strict JSON parse failed: {exc.msg}"]
    if not isinstance(maybe, dict) or not isinstance(maybe.get("tasks"), list):
        return None, ["plan must be a JSON object with a tasks list (empty list = done)"]
    tasks = maybe["tasks"]
    notes: list[str] = []
    declared: set[str] = set()
    seen_ids: set[str] = set()
    for t in tasks:
        if not isinstance(t, dict):
            notes.append("every task must be an object")
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not tid.startswith("root."):
            notes.append(f"task id must be root.<n>[.<m>], got {tid}")
            continue
        if tid in seen_ids:
            notes.append(f"duplicate task id {tid}")
        if tid in completed_ids:
            notes.append(f"task id {tid} was already completed; do not reuse ids")
        seen_ids.add(tid)
        if not isinstance(t.get("goal"), str) or not t["goal"].strip():
            notes.append(f"task {tid} missing goal")
        outputs = t.get("outputs")
        if not valid_outputs(outputs):
            notes.append(f"task {tid} requires outputs with path/description")
        else:
            for o in outputs:
                path = o["path"]
                declared.add(path)
                if not path.startswith(f"{tid}/") and not path.startswith("root/"):
                    notes.append(f"task {tid} output {path} must be under {tid}/ (or root/ for the final deliverable)")
                if path in done:
                    notes.append(f"task {tid} output {path} already exists in memory")
        if t.get("condition") is not None and not isinstance(t["condition"], str):
            notes.append(f"task {tid} condition must be null or string")
    if tasks and not any(p.startswith("root/") for p in declared | done):
        notes.append('no remaining task produces the final deliverable under "root/" and none exists yet')
    referencable = declared | done
    for t in tasks:
        if isinstance(t, dict) and isinstance(t.get("condition"), str):
            for ref in condition_refs(t["condition"]):
                if ref not in referencable:
                    notes.append(f"task {t.get('id')} condition references unknown path {ref}")
            try:
                ConditionParser(t["condition"], set()).parse()
            except ValueError as exc:
                notes.append(f"task {t.get('id')} condition uses unsupported syntax: {exc}")
    return tasks, notes


def plan_churn(prev: list[dict[str, Any]], new: list[dict[str, Any]]) -> dict[str, int]:
    prev_by_id = {t["id"]: t for t in prev if isinstance(t, dict) and "id" in t}
    new_by_id = {t["id"]: t for t in new if isinstance(t, dict) and "id" in t}
    added = [i for i in new_by_id if i not in prev_by_id]
    removed = [i for i in prev_by_id if i not in new_by_id]
    modified = [
        i for i in new_by_id
        if i in prev_by_id and json.dumps(new_by_id[i], sort_keys=True) != json.dumps(prev_by_id[i], sort_keys=True)
    ]
    return {"added": len(added), "removed": len(removed), "modified": len(modified)}


class PlannerRun:
    def __init__(self, run_id: str, root_task: dict[str, Any], config: Config, out_dir: Path, max_state_chars: int):
        self.run_id = run_id
        self.root_task = root_task
        self.config = config
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.out_dir / "trace.jsonl"
        self.entries: dict[str, str] = {}
        # Prompts are instance attributes so a subclass (EM2's A5-symmetric
        # planner) can swap them without altering this frozen E1 baseline;
        # defaults reproduce the E1 behavior exactly.
        self.replan_prompt = REPLAN_PROMPT
        self.worker_prompt = WORKER_PROMPT
        self.llm_calls = 0
        self.planner_calls = 0
        self.truncation_events = 0
        self.context_chars: list[int] = []
        self.churn_totals = {"added": 0, "removed": 0, "modified": 0}
        self.rail_hit = ""
        self.started = time.time()
        self.max_calls = 120
        self.wall_clock = 40 * 60
        self.max_state_chars = max_state_chars

    def log(self, event: str, **data: Any) -> None:
        rec = {"ts": time.time(), "event": event, **data}
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _rails_hit(self) -> bool:
        if self.llm_calls >= self.max_calls:
            self.rail_hit = "max_llm_calls"
        elif time.time() - self.started > self.wall_clock:
            self.rail_hit = "wall_clock"
        if self.rail_hit:
            self.log("rail_hit", rail=self.rail_hit)
            return True
        return False

    def state_block(self) -> str:
        lines = [f"- {k}: {v}" for k, v in self.entries.items()]
        total = sum(len(line) for line in lines)
        dropped = 0
        while lines and total > self.max_state_chars:
            dropped_line = lines.pop(0)  # drop oldest entries first
            total -= len(dropped_line)
            dropped += 1
        if dropped:
            self.truncation_events += 1
            self.log("state_truncation", dropped_entries=dropped, kept_entries=len(lines))
            lines.insert(0, f"[TRUNCATED: {dropped} oldest entries omitted to fit context]")
        return "\n".join(lines) or "(empty)"

    def replan(self, remaining: list[dict[str, Any]], completed_ids: set[str]) -> list[dict[str, Any]] | None:
        message = "\n".join(
            [
                f"ROOT GOAL: {self.root_task['task']}",
                "CURRENT SHARED MEMORY (all completed entries):",
                self.state_block(),
                f"COMPLETED TASK IDS: {sorted(completed_ids) or '(none)'}",
                f"PREVIOUS REMAINING PLAN: {json.dumps(remaining, ensure_ascii=False)}",
                "Emit the updated remaining plan now.",
            ]
        )
        chars = len(REPLAN_PROMPT) + len(message)
        raw = ""
        notes: list[str] = []
        tasks: list[dict[str, Any]] | None = None
        for attempt in range(3):
            prompt = message if attempt == 0 else build_repair_message(message, raw, notes)
            self.llm_calls += 1
            raw = call_model(self.replan_prompt, prompt, self.config)
            tasks, notes = parse_and_validate_replan(raw, set(self.entries), completed_ids)
            if tasks is not None and not notes:
                break
            self.log("replan_repair", attempt=attempt + 1, notes=notes[:6])
        self.planner_calls += 1
        self.context_chars.append(chars)
        if tasks is None or notes:
            self.log("replan_invalid", notes=notes, raw=raw[:2000])
            return None
        churn = plan_churn(remaining, tasks)
        for k in self.churn_totals:
            self.churn_totals[k] += churn[k]
        self.log("planner_call", n=self.planner_calls, context_chars=chars, churn=churn, remaining=len(tasks))
        return tasks

    def run_worker(self, t: dict[str, Any]) -> None:
        declared = list(t.get("outputs", []))
        prefixes = ancestor_prefixes(str(t["id"]))
        named = set(condition_refs(str(t.get("condition") or "")))
        memory = [(k, v) for k, v in sorted(self.entries.items()) if any(k.startswith(p) for p in prefixes) or k in named]
        prompt = "\n".join(
            [
                f"ROOT GOAL: {self.root_task['task']}",
                f"YOUR TASK ID: {t['id']}",
                f"YOUR TASK: {t['goal']}",
                f"DECLARED OUTPUTS: {json.dumps(declared, ensure_ascii=False)}",
                "RELEVANT MEMORY:",
                "\n".join(f"- {k}: {v[:4000]}" for k, v in memory) or "(empty)",
            ]
        )
        raw = ""
        worker: dict[str, Any] = {"outputs": []}
        for attempt in range(3):
            self.llm_calls += 1
            raw = call_model(self.worker_prompt, prompt, self.config)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and isinstance(parsed.get("outputs"), list):
                worker = parsed
                break
            prompt = build_repair_message(prompt, raw, ["worker output must be a JSON object with an outputs list"])
        by_path = {o.get("path"): o.get("value", "") for o in worker.get("outputs", []) if isinstance(o, dict)}
        for output in declared:
            path = str(output["path"])
            value = str(by_path.get(path, ""))
            if path not in by_path:
                self.log("schema_mismatch", agent=t["id"], declared=path)
                value = json.dumps(worker, ensure_ascii=False)[:4000]
            self.entries[path] = value
            self.log("write", path=path, author=t["id"], chars=len(value))

    def run(self) -> dict[str, Any]:
        remaining: list[dict[str, Any]] = []
        completed_ids: set[str] = set()
        planner_done = False
        planner_failed = False
        stalled = False
        last_stall_sig = None
        while not self._rails_hit():
            plan = self.replan(remaining, completed_ids)
            if plan is None:
                planner_failed = True
                break
            remaining = plan
            if not remaining:
                planner_done = True
                break
            done = set(self.entries)
            runnable = [
                t for t in remaining
                if t.get("condition") is None or ConditionParser(str(t["condition"]), done).parse()
            ]
            if not runnable:
                sig = json.dumps(remaining, sort_keys=True)
                if sig == last_stall_sig:
                    stalled = True
                    self.log("stall", remaining=[t["id"] for t in remaining])
                    break
                last_stall_sig = sig
                continue
            last_stall_sig = None
            t = sorted(runnable, key=lambda x: str(x["id"]))[0]
            self.run_worker(t)
            completed_ids.add(str(t["id"]))
            remaining = [x for x in remaining if x["id"] != t["id"]]
        root_paths = sorted(p for p in self.entries if p.startswith("root/"))
        converged = planner_done and bool(root_paths) and not self.rail_hit and not stalled and not planner_failed
        metrics = {
            "run_id": self.run_id,
            "task_id": self.root_task["id"],
            "system": "planner",
            "converged": converged,
            "planner_done": planner_done,
            "planner_failed": planner_failed,
            "stalled": stalled,
            "root_outputs": root_paths,
            "llm_calls": self.llm_calls,
            "planner_calls": self.planner_calls,
            "worker_tasks_completed": len(completed_ids),
            "mean_context_chars_per_decision": (sum(self.context_chars) / len(self.context_chars)) if self.context_chars else 0,
            "max_context_chars": max(self.context_chars, default=0),
            "truncation_events": self.truncation_events,
            "plan_churn": self.churn_totals,
            "rail_hit": self.rail_hit,
            "termination": "rail" if self.rail_hit else "natural",
        }
        write_json(self.out_dir / "entries.json", self.entries)
        write_json(self.out_dir / "metrics.json", metrics)
        return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E1 replanning central-planner baseline")
    parser.add_argument("--tasks", default="tasks/e1_ladder.json")
    parser.add_argument("--task-ids", default="", help="comma-separated task ids; empty = all")
    parser.add_argument("--out-dir", default="results/e1/planner")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-state-chars", type=int, default=60000)
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint", default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args(argv)
    config = Config(args.provider, args.model, args.temperature, args.max_tokens, args.local_endpoint)
    ensure_credentials(config)
    wanted = tuple(t for t in args.task_ids.split(",") if t)
    base = Path(args.out_dir)
    all_metrics = []
    for task in load_json(Path(args.tasks)):
        if wanted and task["id"] not in wanted:
            continue
        for rep in range(1, args.repetitions + 1):
            run_id = f"{task['id']}_r{rep}"
            run_dir = base / run_id
            if (run_dir / "metrics.json").exists():
                print(f"skipping {run_id} (completed)", flush=True)
                all_metrics.append(load_json(run_dir / "metrics.json"))
                continue
            if run_dir.exists():
                print(f"clearing partial {run_id}", flush=True)
                shutil.rmtree(run_dir)
            print(f"running {run_id}...", flush=True)
            all_metrics.append(PlannerRun(run_id, task, config, run_dir, args.max_state_chars).run())
    write_json(base / "summary.json", all_metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
