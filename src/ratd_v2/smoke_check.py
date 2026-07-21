"""Mechanical verification of the smoke checklist (handoff rule 3).

Checks, across a directory of smoke runs:
  1. multi-round continuity — some agent issued a tool call at round >= 2
     (its round-2+ prompt necessarily contained round-1 results)
  2. a circuit rule AUTHORED BY AN AGENT fired correctly
  3. Arm S revive — an S agent ran >= 2 activations via resume
  4. workspace persistence — a file written in one round was read back in
     a later round (any agent)
  5. catalog queries used
  6. bounded returns — a truncation marker was returned
  7. health verdict logged in every run

    python3 -m src.ratd_v2.smoke_check --runs-dir results/et_smoke
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", default="results/et_smoke")
    args = parser.parse_args(argv)
    runs = sorted(p for p in Path(args.runs_dir).iterdir()
                  if (p / "trace.jsonl").exists())
    checks = {k: [] for k in
              ("continuity", "agent_rule_fired", "s_revive", "ws_persist",
               "catalog", "truncation", "verdict")}
    summary = []
    for run in runs:
        trace = [json.loads(l) for l in
                 (run / "trace.jsonl").read_text().splitlines()]
        arm = run.name.split("_")[0]
        writes: dict[tuple[str, str], int] = {}
        agent_rules = set()
        for e in trace:
            ev = e["event"]
            if ev == "tool_call" and not e["error"]:
                if e["round"] >= 2:
                    checks["continuity"].append(run.name)
                if e["tool"] == "catalog.search":
                    checks["catalog"].append(run.name)
                if e.get("truncated_return"):
                    checks["truncation"].append(run.name)
                if e["tool"] == "workspace.read":
                    p = str(e["args"].get("path", ""))
                    key = (e["agent"], p)
                    if key in writes and e["round"] > writes[key]:
                        checks["ws_persist"].append(run.name)
                if e["tool"] == "workspace.write":
                    writes[(e["agent"], str(e["args"].get("path", "")))] = e["round"]
            elif ev == "rule_add":
                agent_rules.add(e["rule"]["id"])
            elif ev == "rule_fired":
                if e["rule_id"] in agent_rules:
                    checks["agent_rule_fired"].append(run.name)
            elif ev == "lifecycle" and arm == "s" and e.get("to") == "running" \
                    and str(e.get("reason", "")).startswith("resumed"):
                checks["s_revive"].append(run.name)
            elif ev == "health_verdict":
                checks["verdict"].append(run.name)
        h = [e for e in trace if e["event"] == "health_verdict"]
        m = json.loads((run / "metrics.json").read_text()) \
            if (run / "metrics.json").exists() else {}
        summary.append(
            f"  {run.name}: calls={m.get('llm_calls')} agents={m.get('n_agents')} "
            f"tokens={m.get('total_tokens')} root={h[0]['root_state'] if h else '?'} "
            f"failure={h[0]['systemic_failure'] if h else '?'} "
            f"rail={h[0]['rail_hit'] or '-' if h else '?'}")
    print(f"{len(runs)} smoke runs:")
    print("\n".join(summary))
    print()
    ok = True
    labels = {
        "continuity": "1. multi-round continuity (round-2+ tool call)",
        "agent_rule_fired": "2. agent-authored circuit rule fired",
        "s_revive": "3. Arm S revive (resume into new activation)",
        "ws_persist": "4. workspace persistence (write then later read)",
        "catalog": "5. catalog queries used",
        "truncation": "6. bounded return with truncation marker",
        "verdict": "7. health verdict logged (every run)",
    }
    for key, label in labels.items():
        seen = sorted(set(checks[key]))
        if key == "verdict":
            passed = len(seen) == len(runs)
        else:
            passed = bool(seen)
        ok &= passed
        print(f"{'PASS' if passed else 'FAIL'} {label} "
              f"[{', '.join(seen) if seen else 'none'}]")
    print("\nSMOKE CHECKLIST:", "ALL PASS" if ok else "INCOMPLETE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
