"""ET §3 metrics + emergence inventory, computed from traces alone.

Mechanical definitions (pre-registered in ET_PREREGISTRATION.md):

- **Adaptation event** — a structure-changing action taken by an agent
  that has already observed in-run information:
  Arms R/S: a `spawn`/`circuit.add_rule`/`circuit.update_rule` tool call
  (or spawn via rule authored by such a call) issued by an agent at
  round/activation > 1. Arm P: a `spawn` issued by the planner at round
  > 1 (the planner's structural replanning proxy — v2 planners hold no
  explicit plan object).
- **Chain (Arm S continuity)** — a maximal sequence of consecutive
  activations of the same agent linked by self-resume rules
  (continue/wait-self).
- **Externalized state** — total chars written to the agent's own
  workspace over the run.
- **Cross-activation handoff** — a read (workspace.read / global.read)
  whose target path was last written/committed by a different agent;
  delivered chars = result size.

    python3 -m src.ratd_v2.analyze --runs-dir results/et
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from .client import write_json

STRUCTURE_TOOLS = {"spawn", "circuit.add_rule", "circuit.update_rule"}


def load_trace(run_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in
            (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]


def analyze_run(run_dir: Path) -> dict[str, Any]:
    trace = load_trace(run_dir)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    arm = meta["arm"]

    # last writer per path (for handoff detection), in event order
    last_writer: dict[str, str] = {}
    adaptation: list[dict[str, Any]] = []
    handoffs: list[dict[str, Any]] = []
    externalized: dict[str, int] = {}
    rule_edits_nonauthor = 0
    cross_ws_writes = 0
    divergences = 0
    rule_fired = 0
    rule_eval_errors = 0
    resumes: dict[str, int] = {}
    prompt_chars: list[int] = []
    rounds: dict[str, int] = {}
    rule_authors: dict[str, str] = {}

    for e in trace:
        ev = e["event"]
        if ev == "llm_call":
            prompt_chars.append(e["prompt_chars"])
            rounds[e["agent"]] = max(rounds.get(e["agent"], 0), e["round"])
        elif ev == "ws_write":
            path = e["path"]
            if not e.get("cross_workspace"):
                if path.startswith(f"agents/{e['agent']}/"):
                    externalized[e["agent"]] = (externalized.get(e["agent"], 0)
                                                + e["chars"])
            last_writer[path] = e["agent"]
        elif ev == "cross_workspace_write":
            cross_ws_writes += 1
        elif ev == "g_commit":
            last_writer[e["path"]] = e["agent"]
        elif ev == "divergence_flagged":
            divergences += 1
        elif ev == "rule_add":
            rule_authors[e["rule"]["id"]] = e["agent"]
        elif ev == "rule_update":
            if rule_authors.get(e["rule_id"]) not in (None, e["agent"]):
                rule_edits_nonauthor += 1
        elif ev == "rule_fired":
            rule_fired += 1
        elif ev == "rule_eval_error":
            rule_eval_errors += 1
        elif ev == "lifecycle" and e.get("to") == "running" and \
                str(e.get("reason", "")).startswith("resumed by"):
            resumes[e["agent"]] = resumes.get(e["agent"], 0) + 1
        elif ev == "tool_call" and not e.get("error"):
            tool = e["tool"]
            agent, rnd = e["agent"], e["round"]
            if tool in STRUCTURE_TOOLS and rnd > 1:
                if arm in ("r", "s") or (arm == "p" and agent == "root"
                                         and tool == "spawn"):
                    adaptation.append({"agent": agent, "round": rnd,
                                       "tool": tool, "seq": e["seq"]})
            if tool in ("workspace.read", "global.read"):
                path = e["args"].get("path", "")
                if isinstance(path, str):
                    norm = path if path.startswith(("agents/", "global/")) \
                        else (f"global/{path}" if tool == "global.read"
                              else f"agents/{agent}/{path}")
                    writer = last_writer.get(norm)
                    if writer and writer != agent:
                        handoffs.append({"reader": agent, "round": rnd,
                                         "path": norm, "writer": writer,
                                         "chars": e["result_chars"],
                                         "truncated": e.get("truncated_return",
                                                            False)})

    # duplicate-work heuristic: same global path committed by >1 agent
    commit_authors: dict[str, set[str]] = {}
    for e in trace:
        if e["event"] == "g_commit":
            commit_authors.setdefault(e["path"], set()).add(e["agent"])
    duplicate_paths = {p: sorted(a) for p, a in commit_authors.items()
                       if len(a) > 1}

    health = next((e for e in reversed(trace)
                   if e["event"] == "health_verdict"), {})
    tokens = sum(e.get("prompt_tokens", 0) + e.get("completion_tokens", 0)
                 for e in trace if e["event"] == "llm_reply")
    return {
        "run_id": meta["run_id"],
        "arm": arm,
        "level": meta["task"]["id"],
        "llm_calls": len(prompt_chars),
        "total_tokens": tokens,
        "prompt_chars_mean": statistics.mean(prompt_chars) if prompt_chars else 0,
        "prompt_chars_max": max(prompt_chars, default=0),
        "prompt_chars_p90": (sorted(prompt_chars)[int(0.9 * (len(prompt_chars) - 1))]
                             if prompt_chars else 0),
        "rounds_per_agent": rounds,
        "adaptation_events": adaptation,
        "adaptation_count": len(adaptation),
        "handoffs": handoffs,
        "handoff_count": len(handoffs),
        "handoff_truncated": sum(1 for h in handoffs if h["truncated"]),
        "externalized_chars_per_agent": externalized,
        "resumes_per_agent": resumes,
        "rules_fired": rule_fired,
        "rule_eval_errors": rule_eval_errors,
        "rule_edits_by_nonauthor": rule_edits_nonauthor,
        "cross_workspace_writes": cross_ws_writes,
        "divergences": divergences,
        "duplicate_commit_paths": duplicate_paths,
        "health": {k: health.get(k) for k in
                   ("quiescent", "rail_hit", "root_state", "waiting_at_end",
                    "failed_agents", "systemic_failure")},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ET trace analysis")
    parser.add_argument("--runs-dir", default="results/et")
    parser.add_argument("--out", default=None,
                        help="default: <runs-dir>/analysis.json")
    args = parser.parse_args(argv)
    runs_dir = Path(args.runs_dir)
    results = []
    for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        if not (run_dir / "trace.jsonl").exists() or \
                not (run_dir / "run_meta.json").exists():
            continue
        try:
            results.append(analyze_run(run_dir))
            print(f"analyzed {run_dir.name}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {run_dir.name}: {exc}", flush=True)
    out = Path(args.out) if args.out else runs_dir / "analysis.json"
    write_json(out, results)
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
