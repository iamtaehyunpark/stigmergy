"""Figure-1 baseline: one-shot pre-planned tree (spec 1.3).

A single planner call decomposes the task into a fixed tree with fixed
conditions; the same worker prompt as the RATD runtime executes each
task when its condition is met. No DEFER, no re-decomposition, no new
edges after the plan - structure is frozen at t=0 by construction.
Worker visibility matches the RATD runtime (ancestor namespaces +
condition-named refs) so the comparison isolates emergent structure,
not read permissions.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
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

PLANNER_PROMPT = """You are the central planner of a multi-agent system.
Decompose the given task, in ONE shot, into a fixed tree of worker tasks.
Workers cannot re-plan, decompose further, or wait on anything beyond the
condition you write for them - plan the entire structure now.

Return strict JSON only. The first character must be { and the last }.
Do not wrap the JSON in Markdown fences.

{
  "tasks": [
    {
      "id": "root.<n>" (or "root.<n>.<m>" for a subtask of root.<n>),
      "goal": "<one-sentence task goal>",
      "outputs": [ {"path": "<namespace/key>", "description": "..."} ],
      "condition": null | "<boolean expr over done(\\"path\\") terms, AND/OR>"
    }
  ]
}

Rules:
- A task's output paths must start with its own id followed by "/"
  (e.g. task root.2 writes root.2/...), EXCEPT that at least one task
  must produce the final integrated deliverable under "root/".
- condition null means the task starts immediately (parallel).
  A condition may only reference paths declared in other tasks' outputs.
- Keys are short snake_case nouns.
"""


def parse_and_validate_plan(raw: str) -> tuple[list[dict[str, Any]] | None, list[str]]:
    try:
        maybe = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"raw strict JSON parse failed: {exc.msg}"]
    if not isinstance(maybe, dict) or not isinstance(maybe.get("tasks"), list) or not maybe["tasks"]:
        return None, ["plan must be a JSON object with a non-empty tasks list"]
    notes: list[str] = []
    tasks = maybe["tasks"]
    declared: set[str] = set()
    seen_ids: set[str] = set()
    for t in tasks:
        if not isinstance(t, dict):
            notes.append("every task must be an object")
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not tid.startswith("root.") or tid in seen_ids:
            notes.append(f"task id must be a unique root.<n>[.<m>] string, got {tid}")
            continue
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
        if t.get("condition") is not None and not isinstance(t["condition"], str):
            notes.append(f"task {tid} condition must be null or string")
    if not any(p.startswith("root/") for p in declared):
        notes.append('no task produces the final deliverable under "root/"')
    for t in tasks:
        if isinstance(t, dict) and isinstance(t.get("condition"), str):
            for ref in condition_refs(t["condition"]):
                if ref not in declared:
                    notes.append(f"task {t.get('id')} condition references undeclared output {ref}")
            try:
                ConditionParser(t["condition"], set()).parse()
            except ValueError as exc:
                notes.append(f"task {t.get('id')} condition uses unsupported syntax: {exc}")
    return tasks, notes


def ancestor_prefixes(task_id: str) -> list[str]:
    parts = task_id.split(".")
    return [".".join(parts[:i]) + "/" for i in range(1, len(parts) + 1)]


class BaselineRun:
    def __init__(self, run_id: str, root_task: dict[str, Any], config: Config, out_dir: Path):
        self.run_id = run_id
        self.root_task = root_task
        self.config = config
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.out_dir / "trace.jsonl"
        self.entries: dict[str, str] = {}
        self.llm_calls = 0
        self.rail_hit = ""
        self.started = time.time()
        self.max_calls = 120
        self.wall_clock = 40 * 60

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

    def plan(self) -> list[dict[str, Any]] | None:
        message = f"TASK: {self.root_task['task']}"
        raw = ""
        notes: list[str] = []
        tasks: list[dict[str, Any]] | None = None
        for attempt in range(3):
            prompt = message if attempt == 0 else build_repair_message(message, raw, notes)
            self.llm_calls += 1
            raw = call_model(PLANNER_PROMPT, prompt, self.config)
            tasks, notes = parse_and_validate_plan(raw)
            if tasks is not None and not notes:
                break
            self.log("plan_repair", attempt=attempt + 1, notes=notes)
        (self.out_dir / "planner_raw.txt").write_text(raw + "\n", encoding="utf-8")
        if tasks is None or notes:
            self.log("plan_invalid", notes=notes)
            return None
        self.log("plan", tasks=tasks)
        write_json(self.out_dir / "plan.json", tasks)
        return tasks

    def visible(self, task_id: str, condition: str | None) -> list[tuple[str, str]]:
        prefixes = ancestor_prefixes(task_id)
        named = set(condition_refs(condition or ""))
        rows = []
        for path in sorted(self.entries):
            if any(path.startswith(p) for p in prefixes) or path in named:
                rows.append((path, self.entries[path]))
                agent_branch = task_id.split(".")[:2]
                path_branch = path.split("/")[0].split(".")[:2]
                if len(agent_branch) > 1 and len(path_branch) > 1 and agent_branch[1] != path_branch[1]:
                    self.log("cross_branch_read", agent=task_id, path=path)
        return rows

    def run_worker(self, t: dict[str, Any]) -> None:
        declared = list(t.get("outputs", []))
        memory = self.visible(t["id"], t.get("condition"))
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
            raw = call_model(WORKER_PROMPT, prompt, self.config)
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
                self.log("schema_mismatch", agent=t["id"], declared=path, returned=[o.get("path") for o in worker.get("outputs", []) if isinstance(o, dict)])
                value = json.dumps(worker, ensure_ascii=False)[:4000]
            self.entries[path] = value
            self.log("write", path=path, author=t["id"], chars=len(value))

    def run(self) -> dict[str, Any]:
        tasks = self.plan()
        stalled = False
        if tasks:
            remaining = {t["id"]: t for t in tasks}
            while remaining and not self._rails_hit():
                done = set(self.entries)
                runnable = [
                    t for t in remaining.values()
                    if t.get("condition") is None or ConditionParser(str(t["condition"]), done).parse()
                ]
                if not runnable:
                    stalled = True
                    self.log("stall", remaining=sorted(remaining))
                    break
                for t in sorted(runnable, key=lambda x: str(x["id"])):
                    self.run_worker(t)
                    del remaining[t["id"]]
        root_outputs = sorted(p for t in (tasks or []) for p in (o["path"] for o in t.get("outputs", [])) if p.startswith("root/"))
        converged = bool(tasks) and not stalled and not self.rail_hit and all(p in self.entries for p in root_outputs)
        cross_pairs = set()
        if self.trace_path.exists():
            for line in self.trace_path.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if rec.get("event") == "cross_branch_read":
                    cross_pairs.add((rec["agent"], rec["path"]))
        metrics = {
            "run_id": self.run_id,
            "task_id": self.root_task["id"],
            "system": "baseline_tree",
            "converged": converged,
            "planned": tasks is not None,
            "stalled": stalled,
            "task_count": len(tasks or []),
            "root_outputs": root_outputs,
            "llm_calls": self.llm_calls,
            "defer_count": 0,
            "emergent_cross_edges": 0,
            "planned_cross_branch_unique_pairs": len(cross_pairs),
            "rail_hit": self.rail_hit,
            "termination": "rail" if self.rail_hit else "natural",
        }
        write_json(self.out_dir / "entries.json", self.entries)
        write_json(self.out_dir / "metrics.json", metrics)
        self.render_graph(tasks or [])
        return metrics

    def render_graph(self, tasks: list[dict[str, Any]]) -> None:
        dot = ["digraph G {", "rankdir=LR;", '"root" [shape=box];']
        for t in tasks:
            tid = str(t["id"])
            parent = ".".join(tid.split(".")[:-1]) or "root"
            dot.append(f'"{tid}" [shape=box];')
            dot.append(f'"{parent}" -> "{tid}" [style=solid];')
            if isinstance(t.get("condition"), str):
                for ref in condition_refs(t["condition"]):
                    dot.append(f'"{ref.split("/")[0]}" -> "{tid}" [style=dashed];')
        dot.append("}")
        dot_path = self.out_dir / "graph.dot"
        dot_path.write_text("\n".join(dot) + "\n", encoding="utf-8")
        if shutil.which("dot"):
            subprocess.run(["dot", "-Tpng", str(dot_path), "-o", str(self.out_dir / "graph.png")], check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Figure-1 one-shot pre-planned tree baseline")
    parser.add_argument("--tasks", default="tasks/figure1_v1.json")
    parser.add_argument("--out-dir", default="results/figure1/baseline")
    parser.add_argument("--repetitions", type=int, default=4)
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint", default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args(argv)
    config = Config(args.provider, args.model, args.temperature, args.max_tokens, args.local_endpoint)
    ensure_credentials(config)
    base = Path(args.out_dir)
    all_metrics = []
    for task in load_json(Path(args.tasks)):
        for rep in range(1, args.repetitions + 1):
            run_id = f"{task['id']}_r{rep}"
            run_dir = base / run_id
            if (run_dir / "metrics.json").exists():
                print(f"skipping {run_id} (completed; metrics.json exists - delete the dir to rerun)", flush=True)
                all_metrics.append(load_json(run_dir / "metrics.json"))
                continue
            if run_dir.exists():
                print(f"clearing partial {run_id}", flush=True)
                shutil.rmtree(run_dir)
            print(f"running {run_id}...", flush=True)
            all_metrics.append(BaselineRun(run_id, task, config, run_dir).run())
    write_json(base / "summary.json", all_metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
