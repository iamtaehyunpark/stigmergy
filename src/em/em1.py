"""EM1 — The Two-Regime Test (discovery opens the unnameable regime).

Arm A (list-enabled, full spec runtime) vs Arm B (list-disabled: the
`list` action removed from the harness and rejected by the runtime; B2
still active so the blind-defer escape stays closed). 3 fig1-v3-class
tasks whose decisive dependency (the legacy identifiers) lives only in
Part A's internal survey artifact — an address Part B cannot derive.
n=4 per task per arm = 24 runs.

Headline metric: content delivery rate of the decisive artifact — the
fraction of legacy survey terms that actually reach Part B's migration
text (fig1 baseline: 96-100% when the survey was promoted to an
interface, 51% when it was only reachable by a named DEFER). Plus:
terminology consistency (frozen Figure-1 scorer), list-mediated
discovery count, conflicts, doctor fires, DEFER/wake usage.

`--score-only` scores existing run dirs without the model.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import statistics
from pathlib import Path
from typing import Any

from ..figure1_score import consistency, extract_terms
from ..phase1 import (
    DEFAULT_LOCAL_ENDPOINT, DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_PROVIDER,
    Config, ensure_credentials, load_json, write_json,
)
from ..ratd.runtime import Runtime, select_tasks
from . import schema

ARMS = {
    "A": {"harness": "prompts/harness_v7.md", "list_enabled": True},
    "B": {"harness": "prompts/harness_v7_nolist.md", "list_enabled": False},
}
SURVEY_KEY = re.compile(r"surve|legacy|inventor|audit|existing_nam|scan", re.I)
MIGRATION_KEY = re.compile(r"migrat|mapping|tutorial|integration|walkthrough|worked", re.I)
# Part A's *published* answer (the canonical standard or a legacy->canonical
# map) is neither the raw survey source nor Part B — it must not pollute the
# survey-term set with canonical names, or delivery is measured against the
# wrong vocabulary.
SOLUTION_KEY = re.compile(r"canonical|standard|_map$|mapping", re.I)
DELIVERY_BAR = 0.85  # pre-registered prediction 1


def _key(path: str) -> str:
    return path.split("/", 1)[-1]


def decisive_delivery(entries: dict[str, str]) -> dict[str, Any]:
    """Fraction of the legacy identifiers surveyed in Part A that actually
    appear in Part B's migration/tutorial text. The survey artifact is an
    internal Part-A product (the raw inventory, NOT Part A's published
    canonical standard/map); the migration text is the Part-B consumer that
    needs those legacy names but cannot name the survey's address."""
    survey_paths = sorted(p for p in entries
                          if SURVEY_KEY.search(_key(p)) and not SOLUTION_KEY.search(_key(p)))
    migration_paths = sorted(
        p for p in entries
        if MIGRATION_KEY.search(_key(p)) and p not in survey_paths
        and not SOLUTION_KEY.search(_key(p)))
    survey_text = "\n".join(entries[p] for p in survey_paths)
    migration_text = "\n".join(entries[p] for p in migration_paths)
    terms = sorted(extract_terms(survey_text))
    matched = sorted(t for t in terms if t in migration_text)
    return {
        "survey_paths": survey_paths,
        "migration_paths": migration_paths,
        "detection_ok": bool(survey_paths) and bool(migration_paths),
        "legacy_term_count": len(terms),
        "delivered_count": len(matched),
        "delivery": (len(matched) / len(terms)) if terms else None,
    }


def defer_usage(run_dir: Path) -> dict[str, int]:
    defers = wakes = 0
    for ev in schema.trace_events(run_dir):
        if ev.get("event") == "defer":
            defers += 1
        elif ev.get("event") == "trigger_fire" and ":defer" in str(ev.get("id", "")):
            wakes += 1
    return {"defers": defers, "defer_wake_fires": wakes}


def score_run(run_dir: Path, arm: str, task_id: str) -> dict[str, Any]:
    metrics = load_json(run_dir / "metrics.json") if (run_dir / "metrics.json").exists() else {}
    entries = schema.done_entries(run_dir)
    delivery = decisive_delivery(entries)
    cons = consistency(entries)
    disc = schema.list_mediated_discoveries(run_dir)
    defers = defer_usage(run_dir)
    return {
        "run_id": run_dir.name, "arm": arm, "task": task_id,
        "converged": metrics.get("converged"),
        "outcome": metrics.get("outcome"),
        "delivery": delivery["delivery"],
        "delivery_detection_ok": delivery["detection_ok"],
        "legacy_term_count": delivery["legacy_term_count"],
        "consistency": cons.get("consistency"),
        "consistency_detection_ok": cons.get("detection_ok"),
        "list_calls": disc["list_calls"],
        "list_mediated_discoveries": disc["discovery_count"],
        "conflicts": metrics.get("conflict_count", 0),
        "doctor_cycles": metrics.get("doctor_cycles", 0),
        "defers": defers["defers"],
        "defer_wake_fires": defers["defer_wake_fires"],
    }


def run_arm(arm: str, tasks: list[dict[str, Any]], base: Path, config: Config,
            worker: str, doctor: str, reps: int) -> None:
    cfg = ARMS[arm]
    prompts = {
        "harness": Path(cfg["harness"]).read_text(encoding="utf-8"),
        "worker": Path(worker).read_text(encoding="utf-8"),
        "doctor": Path(doctor).read_text(encoding="utf-8"),
    }
    adir = base / f"arm_{arm}"
    for task in tasks:
        for rep in range(1, reps + 1):
            run_id = f"{task['id']}_r{rep}"
            run_dir = adir / run_id
            if (run_dir / "metrics.json").exists():
                print(f"  skip arm {arm}/{run_id} (done)", flush=True)
                continue
            if run_dir.exists():
                shutil.rmtree(run_dir)
            print(f"  running arm {arm}/{run_id} (list_enabled={cfg['list_enabled']})...", flush=True)
            Runtime(f"em1_{arm}_{run_id}", task, prompts, config, run_dir,
                    list_enabled=cfg["list_enabled"]).run()


def summarize(rows: list[dict[str, Any]], base: Path) -> dict[str, Any]:
    def cell(arm):
        return [r for r in rows if r["arm"] == arm]

    def mean(vals):
        vals = [v for v in vals if isinstance(v, (int, float))]
        return statistics.mean(vals) if vals else None

    a, b = cell("A"), cell("B")
    a_delivery = mean([r["delivery"] for r in a])
    b_delivery = mean([r["delivery"] for r in b])
    a_cons = mean([r["consistency"] for r in a])
    b_cons = mean([r["consistency"] for r in b])
    conflicts = [r for r in rows if (r["conflicts"] or 0) > 0]
    pred = {
        "1_armA_delivery_ge_85": (a_delivery is not None and a_delivery >= DELIVERY_BAR),
        "1_armA_delivery": a_delivery,
        "2_armA_ge_armB_delivery": (a_delivery is not None and b_delivery is not None
                                    and a_delivery >= b_delivery),
        "2_armA_ge_armB_consistency": (a_cons is not None and b_cons is not None
                                       and a_cons >= b_cons),
        "2_discovery_load_bearing": (a_delivery is not None and b_delivery is not None
                                     and a_delivery > b_delivery + 1e-9),
        "3_conflicts_total": len(conflicts),
        "3_conflicts_all_armA": bool(conflicts) and all(c["arm"] == "A" for c in conflicts),
        "list_mediated_discoveries_armA": sum(r["list_mediated_discoveries"] for r in a),
        "doctor_fires_total": sum(r["doctor_cycles"] for r in rows),
    }
    summary = {
        "arm_A": {"delivery_mean": a_delivery, "consistency_mean": a_cons, "n": len(a)},
        "arm_B": {"delivery_mean": b_delivery, "consistency_mean": b_cons, "n": len(b)},
        "predictions": pred,
    }
    lines = [
        "# EM1 — Two-Regime Test results", "",
        f"- Arm A delivery mean: {_pct(a_delivery)}  consistency mean: {_pct(a_cons)}  (n={len(a)})",
        f"- Arm B delivery mean: {_pct(b_delivery)}  consistency mean: {_pct(b_cons)}  (n={len(b)})",
        f"- list-mediated discoveries (Arm A): {pred['list_mediated_discoveries_armA']}",
        f"- conflicts total: {pred['3_conflicts_total']} (all in Arm A: {pred['3_conflicts_all_armA']})",
        f"- doctor fires total: {pred['doctor_fires_total']}",
        "",
        "## Pre-registered predictions",
        f"1. Arm A delivery >= 85%: **{pred['1_armA_delivery_ge_85']}** ({_pct(a_delivery)})",
        f"2. Arm A >= Arm B (delivery): **{pred['2_armA_ge_armB_delivery']}**; "
        f"(consistency): **{pred['2_armA_ge_armB_consistency']}**; "
        f"discovery load-bearing: **{pred['2_discovery_load_bearing']}**",
        f"3. Any conflict occurs in Arm A on an unnameable-address run: "
        f"**{pred['3_conflicts_all_armA'] if conflicts else 'no conflicts (null result — scopes E5 to concurrency)'}**",
        "",
        "| run | arm | task | conv | delivery | consist | list-disc | confl | doctor | defers |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: (x["arm"], x["run_id"])):
        lines.append(
            f"| {r['run_id']} | {r['arm']} | {r['task']} | {r['converged']} | "
            f"{_pct(r['delivery'])} | {_pct(r['consistency'])} | "
            f"{r['list_mediated_discoveries']} | {r['conflicts']} | "
            f"{r['doctor_cycles']} | {r['defers']} |"
        )
    (base / "EM1_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(base / "EM1_scores.json", {"summary": summary, "rows": rows})
    return summary


def _pct(v: Any) -> str:
    return f"{v:.1%}" if isinstance(v, float) else ("n/a" if v is None else str(v))


def collect_scores(base: Path, tasks: list[dict[str, Any]], reps: int) -> list[dict[str, Any]]:
    task_ids = {t["id"] for t in tasks}
    rows: list[dict[str, Any]] = []
    for arm in ARMS:
        adir = base / f"arm_{arm}"
        if not adir.exists():
            continue
        for run_dir in sorted(p for p in adir.iterdir() if p.is_dir() and (p / "metrics.json").exists()):
            tid = run_dir.name.rsplit("_r", 1)[0]
            if tid in task_ids:
                rows.append(score_run(run_dir, arm, tid))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EM1 Two-Regime Test")
    parser.add_argument("--tasks", default="tasks/em1_tasks.json")
    parser.add_argument("--out-dir", default="results/em1")
    parser.add_argument("--arms", default="A,B")
    parser.add_argument("--repetitions", type=int, default=4)
    parser.add_argument("--worker-prompt", default="prompts/worker_v7.md")
    parser.add_argument("--doctor-prompt", default="prompts/doctor_v1.md")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint", default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args(argv)

    base = Path(args.out_dir)
    base.mkdir(parents=True, exist_ok=True)
    tasks = select_tasks(Path(args.tasks))
    if not args.score_only:
        config = Config(args.provider, args.model, args.temperature, args.max_tokens, args.local_endpoint)
        ensure_credentials(config)
        for arm in args.arms.split(","):
            if arm in ARMS:
                print(f"== Arm {arm} ==", flush=True)
                run_arm(arm, tasks, base, config, args.worker_prompt, args.doctor_prompt, args.repetitions)

    rows = collect_scores(base, tasks, args.repetitions)
    summary = summarize(rows, base)
    print(f"\nArm A delivery {_pct(summary['arm_A']['delivery_mean'])} | "
          f"Arm B delivery {_pct(summary['arm_B']['delivery_mean'])} | "
          f"conflicts {summary['predictions']['3_conflicts_total']}", flush=True)
    print(f"wrote {base / 'EM1_report.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
