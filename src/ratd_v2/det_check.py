"""Determinism check for adaptive replication (prereg deviation 2026-07-21).

For each (arm, level) cell, compares rep pairs on: llm_calls,
total_tokens, n_agents, and the sha256 of the judge-artifact content
(global/final/* heads, fallback all global heads — same extraction as
the judge). Cells whose executed reps all match are `deterministic`
(effective n=1); any mismatch lists the cell for a full n=4 rerun.

    python3 -m src.ratd_v2.det_check --runs-dir results/et
"""
from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path

from .client import load_json
from .judge import final_artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", default="results/et")
    args = parser.parse_args(argv)
    cells: dict[tuple[str, str], list[tuple[str, tuple]]] = defaultdict(list)
    for run_dir in sorted(Path(args.runs_dir).iterdir()):
        if not (run_dir / "metrics.json").exists():
            continue
        bits = run_dir.name.split("_")
        if len(bits) != 3:
            continue
        m = load_json(run_dir / "metrics.json")
        artifact, fallback = final_artifact(load_json(run_dir / "state.json"))
        sig = (m["llm_calls"], m["total_tokens"], m["n_agents"],
               hashlib.sha256(artifact.encode()).hexdigest()[:16], fallback)
        cells[(bits[0], bits[1])].append((bits[2], sig))
    divergent = []
    for (arm, level), reps in sorted(cells.items()):
        sigs = {s for _, s in reps}
        status = "deterministic" if len(sigs) == 1 else "DIVERGENT"
        if len(reps) < 2:
            status = "single-rep (rep 2 pending)"
        print(f"{arm}_{level}: {len(reps)} reps, {len(sigs)} distinct outcome(s) "
              f"-> {status}")
        if len(sigs) > 1:
            divergent.append(f"{arm}_{level}")
            for rep, s in reps:
                print(f"   {rep}: calls={s[0]} tokens={s[1]} agents={s[2]} "
                      f"artifact={s[3]}{' fallback' if s[4] else ''}")
    print()
    if divergent:
        print("cells needing full n=4:", ", ".join(divergent))
        return 1
    print("all multi-rep cells deterministic — adaptive replication holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
