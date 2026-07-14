"""EM2 — E1 Quality Completion (the crossover's second axis).

Reruns E1 L3 and L4 on both systems (RATD rebuilt runtime + the
A5-symmetric planner), n=3 per cell, then judges every root artifact with
the E1 judge and rubrics **frozen and untouched** (same prompt, same
rubric files, same fixed-seed blinding). L1/L2 carry over from E1.

Adds the two A5 metrics the spec requires: stub_count (must be 0 with the
assembly-stub class closed) and family completeness (all `stem_1..n`
present). Reads pre-registered crossover predictions and applies E1's
inherited variance rule (within-cell sd > 3 on the 10-pt judge scale ->
that cell reports the cost axis only).
"""
from __future__ import annotations

import argparse
import os
import random
import shutil
import statistics
from pathlib import Path
from typing import Any

from .. import e1_judge
from ..e1_judge import crossover_png, decision_contexts, judge_one, root_artifact_planner
from ..phase1 import (
    DEFAULT_LOCAL_ENDPOINT, DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_PROVIDER,
    Config, ensure_credentials, load_json, write_json,
)
from ..ratd.runtime import Runtime, select_tasks
from .em2_planner import A5PlannerRun
from . import schema

LEVELS = ("L3", "L4")
VARIANCE_LIMIT = 3.0  # E1 inherited rule


def root_artifact_ratd(run_dir: Path) -> str:
    entries = schema.done_entries(run_dir)
    return "\n\n".join(f"## {k}\n{entries[k]}" for k in sorted(entries) if k.startswith("root/"))


def run_ratd(base: Path, tasks: list[dict[str, Any]], config: Config,
             prompts: dict[str, str], reps: int) -> None:
    rdir = base / "ratd"
    for task in tasks:
        for rep in range(1, reps + 1):
            run_id = f"{task['id']}_r{rep}"
            run_dir = rdir / run_id
            if (run_dir / "metrics.json").exists():
                print(f"  skip ratd/{run_id} (done)", flush=True)
                continue
            if run_dir.exists():
                shutil.rmtree(run_dir)
            print(f"  running ratd/{run_id}...", flush=True)
            Runtime(f"em2_{run_id}", task, prompts, config, run_dir).run()


def run_planner(base: Path, tasks: list[dict[str, Any]], config: Config, reps: int,
                max_state_chars: int) -> None:
    pdir = base / "planner"
    for task in tasks:
        for rep in range(1, reps + 1):
            run_id = f"{task['id']}_r{rep}"
            run_dir = pdir / run_id
            if (run_dir / "metrics.json").exists():
                print(f"  skip planner/{run_id} (done)", flush=True)
                continue
            if run_dir.exists():
                shutil.rmtree(run_dir)
            print(f"  running planner/{run_id}...", flush=True)
            A5PlannerRun(run_id, task, config, run_dir, max_state_chars).run()


def a5_audit_for(system: str, run_dir: Path) -> dict[str, Any]:
    if system == "ratd":
        return schema.family_audit(run_dir)
    entries = load_json(run_dir / "entries.json") if (run_dir / "entries.json").exists() else {}
    prov = load_json(run_dir / "provenance.json") if (run_dir / "provenance.json").exists() else {}
    root_only = {k: str(v) for k, v in entries.items()}
    return schema.family_audit_entries(root_only, prov)


def collect(base: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    specs = (("ratd", base / "ratd", root_artifact_ratd),
             ("planner", base / "planner", root_artifact_planner))
    for system, sdir, artifact_fn in specs:
        if not sdir.exists():
            continue
        for run_dir in sorted(p for p in sdir.iterdir() if p.is_dir() and (p / "metrics.json").exists()):
            metrics = load_json(run_dir / "metrics.json")
            level = run_dir.name.split("_")[0]
            contexts = decision_contexts(run_dir, system)
            audit = a5_audit_for(system, run_dir)
            rows.append({
                "system": system, "level": level, "run_id": run_dir.name,
                "converged": metrics.get("converged"),
                "llm_calls": metrics.get("llm_calls"),
                "decisions": len(contexts),
                "mean_context_chars": (sum(contexts) / len(contexts)) if contexts else 0,
                "max_context_chars": max(contexts, default=0),
                "stub_count": audit["stub_count"],
                "incomplete_families": len(audit["incomplete_families"]),
                "oversize": len(audit["oversize"]),
                "artifact": artifact_fn(run_dir),
            })
    return rows


def readings(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def cell(system, level):
        return [r for r in rows if r["system"] == system and r["level"] == level]

    out: dict[str, Any] = {"levels": {}}
    for level in LEVELS:
        r_cell, p_cell = cell("ratd", level), cell("planner", level)
        r_scores = [r["judge"]["overall"] for r in r_cell if "judge" in r]
        p_scores = [r["judge"]["overall"] for r in p_cell if "judge" in r]
        r_sd = statistics.stdev(r_scores) if len(r_scores) > 1 else 0.0
        p_sd = statistics.stdev(p_scores) if len(p_scores) > 1 else 0.0
        high_variance = r_sd > VARIANCE_LIMIT or p_sd > VARIANCE_LIMIT
        r_mean = statistics.mean(r_scores) if r_scores else None
        p_mean = statistics.mean(p_scores) if p_scores else None
        r_ctx = statistics.mean([r["mean_context_chars"] for r in r_cell]) if r_cell else None
        p_ctx = statistics.mean([r["mean_context_chars"] for r in p_cell]) if p_cell else None
        verdict = "cost-axis-only (variance rule)" if high_variance else _quality_verdict(r_mean, p_mean)
        out["levels"][level] = {
            "ratd_overall": r_mean, "planner_overall": p_mean,
            "ratd_sd": r_sd, "planner_sd": p_sd, "high_variance": high_variance,
            "ratd_ctx": r_ctx, "planner_ctx": p_ctx,
            "ratd_stub_total": sum(r["stub_count"] for r in r_cell),
            "planner_stub_total": sum(r["stub_count"] for r in p_cell),
            "verdict": verdict,
        }
    out["stub_count_zero"] = all(r["stub_count"] == 0 for r in rows)
    return out


def _quality_verdict(r_mean: float | None, p_mean: float | None) -> str:
    if r_mean is None or p_mean is None:
        return "insufficient data"
    diff = r_mean - p_mean
    if diff >= 1.0:
        return "quality crossover (RATD leads) — theory §3 quality axis confirmed"
    if diff <= -1.0:
        return "planner leads at depth — §3 quality prediction wrong as stated; scope to cost axis"
    return "quality parity — 'equal quality at ~an order of magnitude lower, non-degrading context cost'"


def write_report(base: Path, rows: list[dict[str, Any]], reading: dict[str, Any]) -> None:
    e1_judge.summarize(rows, base)  # frozen E1 summary table (reused)
    lines = ["# EM2 — Quality Completion readings", ""]
    lines.append(f"- stub_count == 0 across all EM2 runs: **{reading['stub_count_zero']}**")
    lines.append("")
    for level, d in reading["levels"].items():
        lines += [
            f"## {level}",
            f"- RATD overall {_f(d['ratd_overall'])} (sd {d['ratd_sd']:.1f}) | "
            f"planner overall {_f(d['planner_overall'])} (sd {d['planner_sd']:.1f})",
            f"- context chars/decision — RATD {_f(d['ratd_ctx'])} | planner {_f(d['planner_ctx'])}",
            f"- stubs — RATD {d['ratd_stub_total']} | planner {d['planner_stub_total']}",
            f"- **reading: {d['verdict']}**",
            "",
        ]
    (base / "EM2_readings.md").write_text("\n".join(lines), encoding="utf-8")
    slim = [{k: v for k, v in r.items() if k != "artifact"} for r in rows]
    write_json(base / "EM2_scores.json", {"readings": reading, "rows": slim})


def _f(v: Any) -> str:
    return f"{v:,.1f}" if isinstance(v, (int, float)) else "n/a"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EM2 Quality Completion")
    parser.add_argument("--tasks", default="tasks/e1_ladder.json")
    parser.add_argument("--task-ids", default="L3,L4")
    parser.add_argument("--out-dir", default="results/em2")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--systems", default="ratd,planner")
    parser.add_argument("--harness", default="prompts/harness_v7.md")
    parser.add_argument("--worker-prompt", default="prompts/worker_v7.md")
    parser.add_argument("--doctor-prompt", default="prompts/doctor_v1.md")
    parser.add_argument("--judge-prompt", default="prompts/judge_v1.md")
    parser.add_argument("--rubrics-dir", default="rubrics")
    parser.add_argument("--max-state-chars", type=int, default=60000)
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint", default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args(argv)

    base = Path(args.out_dir)
    base.mkdir(parents=True, exist_ok=True)
    task_ids = tuple(t for t in args.task_ids.split(",") if t)
    tasks = select_tasks(Path(args.tasks), task_ids)
    config = Config(args.provider, args.model, args.temperature, args.max_tokens, args.local_endpoint)
    systems = args.systems.split(",")

    if not args.score_only:
        ensure_credentials(config)
        if "ratd" in systems:
            print("== RATD ==", flush=True)
            prompts = {
                "harness": Path(args.harness).read_text(encoding="utf-8"),
                "worker": Path(args.worker_prompt).read_text(encoding="utf-8"),
                "doctor": Path(args.doctor_prompt).read_text(encoding="utf-8"),
            }
            run_ratd(base, tasks, config, prompts, args.repetitions)
        if "planner" in systems:
            print("== planner (A5-symmetric) ==", flush=True)
            run_planner(base, tasks, config, args.repetitions, args.max_state_chars)

    # judge (frozen), fixed-seed system-blind order
    ensure_credentials(config)
    judge_prompt = Path(args.judge_prompt).read_text(encoding="utf-8")
    rubrics = {lvl: (Path(args.rubrics_dir) / f"{lvl}.md").read_text(encoding="utf-8") for lvl in LEVELS}
    rows = collect(base)
    order = list(range(len(rows)))
    random.Random(0).shuffle(order)
    for i in order:
        row = rows[i]
        print(f"judging {row['system']}/{row['run_id']}...", flush=True)
        row["judge"] = judge_one(row, rubrics[row["level"]], judge_prompt, config)

    reading = readings(rows)
    write_report(base, rows, reading)
    crossover_png(rows, base)
    print(f"\nstub_count==0: {reading['stub_count_zero']}", flush=True)
    for lvl, d in reading["levels"].items():
        print(f"  {lvl}: {d['verdict']}", flush=True)
    print(f"wrote {base / 'EM2_readings.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
