"""EM2 A5-symmetric planner baseline.

The E1 quality result was confounded: RATD workers got A5's assembly
mechanics (numeric families + a 12k single-emission cap + visible
truncation) that close the assembly-stub failure, while the planner
baseline did not. EM2 requires symmetry — the planner receives the
identical mechanics — or the crossover cannot be attributed to depth.

This subclasses the frozen E1 planner, swapping in A5-aware replan and
worker prompts and enforcing the same 12k emission cap with a visible
truncation marker. The E1 planner's scheduling, replanning, context
accounting, and rails are inherited unchanged, so the only difference
from the E1 baseline is the A5 mechanic — exactly the symmetry the spec
demands.
"""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Any

from ..phase1 import (
    DEFAULT_LOCAL_ENDPOINT, DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_PROVIDER,
    Config, build_repair_message, call_model, condition_refs, ensure_credentials,
    load_json, write_json,
)
from ..planner_baseline import REPLAN_PROMPT, PlannerRun
from ..tree_baseline import ancestor_prefixes

SINGLE_EMISSION_MAX = 12_000  # identical to store.SINGLE_EMISSION_MAX (A5)

A5_RULES = """

A5 ASSEMBLY RULES (large-artifact discipline — identical to every other system):
- No single output value may exceed 12,000 characters. An artifact that
  would be larger MUST be split across multiple numbered member tasks
  (e.g. root.3.1 writes root.3/chapter_1, root.3.2 writes root.3/chapter_2,
  ...) plus a short index/assembly task that lists the members and, if
  needed, an integrated root/ deliverable that references them.
- Do not emit a stub or placeholder to "hold a slot": every declared
  output must carry real content. A missing member is a defect.
"""

A5_WORKER_PROMPT = """You are a worker agent in a shared-memory multi-agent run.
Complete the assigned task using the relevant memory provided. Return strict JSON only:
{
  "outputs": [
    {"path": "<declared path>", "value": "<artifact text>"}
  ]
}
Write every declared output path exactly. Keep artifact text concise but useful.

A5 EMISSION RULE: no single "value" may exceed 12,000 characters. If your
artifact would be larger, it was mis-scoped as one output — write the
portion that belongs to THIS declared path only, condensed to fit. Never
emit a placeholder or stub; real content only.
"""


class A5PlannerRun(PlannerRun):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.replan_prompt = REPLAN_PROMPT + A5_RULES
        self.worker_prompt = A5_WORKER_PROMPT
        self.provenance: dict[str, str] = {}   # path -> a5 provenance flag
        self.oversize_events = 0

    def run_worker(self, t: dict[str, Any]) -> None:
        """Mirror of the base worker loop plus the A5 cap: an over-cap value
        is marked and made visibly truncated (never a silent slice), exactly
        as the RATD store's oversize_fallback path does."""
        declared = list(t.get("outputs", []))
        prefixes = ancestor_prefixes(str(t["id"]))
        named = set(condition_refs(str(t.get("condition") or "")))
        memory = [(k, v) for k, v in sorted(self.entries.items())
                  if any(k.startswith(p) for p in prefixes) or k in named]
        prompt = "\n".join([
            f"ROOT GOAL: {self.root_task['task']}",
            f"YOUR TASK ID: {t['id']}",
            f"YOUR TASK: {t['goal']}",
            f"DECLARED OUTPUTS: {__import__('json').dumps(declared, ensure_ascii=False)}",
            "RELEVANT MEMORY:",
            "\n".join(f"- {k}: {v[:4000]}" for k, v in memory) or "(empty)",
        ])
        import json as _json
        raw = ""
        worker: dict[str, Any] = {"outputs": []}
        for attempt in range(3):
            self.llm_calls += 1
            raw = call_model(self.worker_prompt, prompt, self.config)
            try:
                parsed = _json.loads(raw)
            except _json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and isinstance(parsed.get("outputs"), list):
                worker = parsed
                break
            prompt = build_repair_message(prompt, raw, ["worker output must be a JSON object with an outputs list"])
        by_path = {o.get("path"): o.get("value", "") for o in worker.get("outputs", []) if isinstance(o, dict)}
        for output in declared:
            path = str(output["path"])
            value = str(by_path.get(path, ""))
            prov = "worker"
            if path not in by_path:
                self.log("schema_mismatch", agent=t["id"], declared=path)
                value = _json.dumps(worker, ensure_ascii=False)[:4000]
                prov = "fallback"
            elif len(value) > SINGLE_EMISSION_MAX:
                self.oversize_events += 1
                head = SINGLE_EMISSION_MAX * 2 // 3
                value = value[:head] + f"\n[truncated: full length {len(value)}]\n" + value[-(SINGLE_EMISSION_MAX - head):]
                prov = "oversize_fallback"
                self.log("oversize_truncation", agent=t["id"], path=path)
            self.entries[path] = value
            self.provenance[path] = prov
            self.log("write", path=path, author=t["id"], chars=len(value), provenance=prov)

    def run(self) -> dict[str, Any]:
        metrics = super().run()
        metrics["a5"] = {"oversize_events": self.oversize_events, "provenance": self.provenance}
        write_json(self.out_dir / "metrics.json", metrics)
        write_json(self.out_dir / "provenance.json", self.provenance)
        return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EM2 A5-symmetric replanning planner")
    parser.add_argument("--tasks", default="tasks/e1_ladder.json")
    parser.add_argument("--task-ids", default="L3,L4")
    parser.add_argument("--out-dir", default="results/em2/planner")
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
                print(f"skipping {run_id} (done)", flush=True)
                all_metrics.append(load_json(run_dir / "metrics.json"))
                continue
            if run_dir.exists():
                shutil.rmtree(run_dir)
            print(f"running {run_id}...", flush=True)
            all_metrics.append(A5PlannerRun(run_id, task, config, run_dir, args.max_state_chars).run())
    write_json(base / "summary.json", all_metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
