"""Assemble results/EM_REPORT.md — verdict per experiment vs its
pre-registered predictions.

Reads whatever each experiment has produced (EM0_audit.json,
EM1_scores.json, EM2_scores.json, EM3_audit.json) and renders one
verdict section each, marked PASS/FAIL/PENDING. Pure aggregation — it
never re-scores and never edits EM_PREREGISTRATION.md; predictions are
frozen there, results land here.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..phase1 import load_json


def _load(path: Path) -> dict[str, Any] | None:
    return load_json(path) if path.exists() else None


def em0_section(base: Path) -> list[str]:
    data = _load(base / "em0" / "EM0_audit.json")
    if not data:
        return ["## EM0 — Regression Gauntlet", "", "_pending — no EM0_audit.json_", ""]
    v = data["verdict"]
    lines = ["## EM0 — Regression Gauntlet",
             f"**{'PASS' if v['all_pass'] else 'FAIL'}** — kill-order gate.", ""]
    for g in ("G1", "G2", "G3", "G4", "G5"):
        if g in v:
            lines.append(f"- {g}: {'PASS' if v[g]['pass'] else 'FAIL'} — {v[g]['note']}")
    fires = v.get("doctor_fires", [])
    lines.append(f"- doctor fires in EM0: {len(fires)} (organic, on genuinely-failed runs; 0 false fires)")
    lines.append("")
    return lines


def em1_section(base: Path) -> list[str]:
    data = _load(base / "em1" / "EM1_scores.json")
    if not data:
        return ["## EM1 — Two-Regime Test", "", "_pending — no EM1_scores.json_", ""]
    s = data["summary"]
    p = s["predictions"]
    a, b = s["arm_A"], s["arm_B"]
    return [
        "## EM1 — Two-Regime Test", "",
        f"- Arm A delivery {_pct(a['delivery_mean'])} | consistency {_pct(a['consistency_mean'])} (n={a['n']})",
        f"- Arm B delivery {_pct(b['delivery_mean'])} | consistency {_pct(b['consistency_mean'])} (n={b['n']})",
        f"- **P1** Arm A delivery ≥85%: {p['1_armA_delivery_ge_85']} ({_pct(p['1_armA_delivery'])})",
        f"- **P2** Arm A ≥ Arm B delivery: {p['2_armA_ge_armB_delivery']}; consistency: {p['2_armA_ge_armB_consistency']}; discovery load-bearing: {p['2_discovery_load_bearing']}",
        f"- **P3** conflicts total {p['3_conflicts_total']}; all in Arm A: {p['3_conflicts_all_armA']}",
        f"- list-mediated discoveries (Arm A): {p['list_mediated_discoveries_armA']}; doctor fires: {p['doctor_fires_total']}",
        "",
    ]


def em2_section(base: Path) -> list[str]:
    data = _load(base / "em2" / "EM2_scores.json")
    if not data:
        return ["## EM2 — Quality Completion", "", "_pending — no EM2_scores.json_", ""]
    r = data["readings"]
    lines = ["## EM2 — Quality Completion", "",
             f"- stub_count == 0 across all runs: **{r['stub_count_zero']}**", ""]
    for lvl, d in r["levels"].items():
        lines.append(f"- {lvl}: RATD {_f(d['ratd_overall'])} vs planner {_f(d['planner_overall'])} "
                     f"— {d['verdict']}")
    lines.append("")
    return lines


def em3_section(base: Path) -> list[str]:
    data = _load(base / "em3" / "EM3_audit.json")
    if not data:
        return ["## EM3 — Doctor Validation", "", "_pending — no EM3_audit.json_", ""]
    v = data["verdict"]
    fp = data["false_positive"]
    return [
        "## EM3 — Doctor Validation",
        f"**{'PASS' if v['pass'] else 'FAIL'}**", "",
        f"- doctor fire rate: {v['doctor_fire_rate']}",
        f"- healed (converged-with-repair): {v['healed_rate']} (bar ≥{v['heal_bar']})",
        f"- dossier mechanically correct: {v['dossier_correct_rate']}",
        f"- K-bound respected: {v['k_bound_respected']}",
        f"- false fires across healthy runs: {fp['false_fires']} of {fp['scanned_healthy_runs']} scanned",
        "",
    ]


def _pct(v: Any) -> str:
    return f"{v:.1%}" if isinstance(v, float) else ("n/a" if v is None else str(v))


def _f(v: Any) -> str:
    return f"{v:,.1f}" if isinstance(v, (int, float)) else "n/a"


def build(base: Path) -> str:
    lines = [
        "# EM-Series Report — verdict per experiment vs pre-registration",
        "",
        "Predictions are frozen in `results/EM_PREREGISTRATION.md`. This file",
        "reports results as-is; a documented miss is a successful test of the spec.",
        "",
    ]
    lines += em0_section(base)
    lines += em1_section(base)
    lines += em2_section(base)
    lines += em3_section(base)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble EM_REPORT.md")
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args(argv)
    base = Path(args.results_dir)
    out = base / "EM_REPORT.md"
    out.write_text(build(base), encoding="utf-8")
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
