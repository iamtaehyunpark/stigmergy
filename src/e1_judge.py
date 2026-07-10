"""E1 judging + summary (spec 2.4-2.5).

Collects the 24 runs' root artifacts, judges each system-blind against
the frozen per-level rubric (judge model = agent model, fixed seed
shuffle of judging order), and writes judge_scores.json, summary.md,
and crossover.png (two panels: quality vs level, context-chars per
decision vs level) if matplotlib is available.

Context cost per decision: RATD = route_context trace events (one per
routing decision, system+user chars); planner = planner_call events
(context_chars). Workers are execution, not decisions, for both.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import statistics
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
    ensure_credentials,
    load_json,
    write_json,
)

LEVELS = ("L1", "L2", "L3", "L4")
ARTIFACT_CAP = 24000
JUDGE_KEYS = ("accuracy", "completeness", "structure", "consistency", "overall")


def root_artifact_ratd(run_dir: Path) -> str:
    db = sqlite3.connect(run_dir / "state.sqlite")
    rows = db.execute("SELECT namespace_key, value FROM entries WHERE status='done' AND namespace_key LIKE 'root/%' ORDER BY namespace_key").fetchall()
    return "\n\n".join(f"## {k}\n{v}" for k, v in rows)


def root_artifact_planner(run_dir: Path) -> str:
    entries = load_json(run_dir / "entries.json")
    return "\n\n".join(f"## {k}\n{v}" for k, v in sorted(entries.items()) if k.startswith("root/"))


def decision_contexts(run_dir: Path, system: str) -> list[int]:
    chars: list[int] = []
    trace = run_dir / "trace.jsonl"
    if not trace.exists():
        return chars
    for line in trace.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if system == "ratd" and rec.get("event") == "route_context":
            chars.append(int(rec["chars"]))
        elif system == "planner" and rec.get("event") == "planner_call":
            chars.append(int(rec["context_chars"]))
    return chars


def collect(ratd_dir: Path, planner_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for system, base, artifact_fn in (("ratd", ratd_dir, root_artifact_ratd), ("planner", planner_dir, root_artifact_planner)):
        if not base.exists():
            continue
        for run_dir in sorted(p for p in base.iterdir() if p.is_dir() and (p / "metrics.json").exists()):
            metrics = load_json(run_dir / "metrics.json")
            level = run_dir.name.split("_")[0]
            contexts = decision_contexts(run_dir, system)
            rows.append({
                "system": system,
                "level": level,
                "run_id": run_dir.name,
                "converged": metrics.get("converged"),
                "llm_calls": metrics.get("llm_calls"),
                "decisions": len(contexts),
                "mean_context_chars": (sum(contexts) / len(contexts)) if contexts else 0,
                "max_context_chars": max(contexts, default=0),
                "artifact": artifact_fn(run_dir),
            })
    return rows


def judge_one(row: dict[str, Any], rubric: str, judge_prompt: str, config: Config) -> dict[str, Any]:
    artifact = row["artifact"]
    truncated = len(artifact) > ARTIFACT_CAP
    if truncated:
        artifact = artifact[:ARTIFACT_CAP] + "\n[ARTIFACT TRUNCATED FOR JUDGING]"
    if not artifact.strip():
        return {**{k: 1 for k in JUDGE_KEYS}, "rationale": "empty artifact (auto-scored 1)", "artifact_truncated": False, "auto": True}
    message = f"RUBRIC:\n{rubric}\n\nARTIFACT:\n{artifact}"
    raw = ""
    notes: list[str] = []
    for attempt in range(3):
        prompt = message if attempt == 0 else build_repair_message(message, raw, notes)
        raw = call_model(judge_prompt, prompt, config)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed, notes = None, ["strict JSON parse failed"]
            continue
        if isinstance(parsed, dict) and all(isinstance(parsed.get(k), int) and 1 <= parsed[k] <= 10 for k in JUDGE_KEYS):
            return {**{k: parsed[k] for k in JUDGE_KEYS}, "rationale": str(parsed.get("rationale", "")), "artifact_truncated": truncated, "auto": False}
        notes = [f"must contain integer 1-10 fields {JUDGE_KEYS} and rationale"]
    return {**{k: 1 for k in JUDGE_KEYS}, "rationale": f"judge output invalid after retries: {raw[:200]}", "artifact_truncated": truncated, "auto": True}


def summarize(rows: list[dict[str, Any]], out_dir: Path) -> None:
    lines = [
        "# E1 Summary — RATD vs replanning central planner",
        "",
        "Judge: qwen3.6 (same as agents), frozen prompts/judge_v1.md +",
        "rubrics/L*.md, system-blind, fixed-seed order. n=3 per cell —",
        "feasibility-scale evidence, not significance. Temp-0 clustering",
        "may reduce effective n; per-run scores listed for that reason.",
        "",
        "| Level | System | conv | overall (mean±sd, per-run) | ctx chars/decision (mean) | decisions | LLM calls (mean) |",
        "|---|---|---|---|---|---|---|",
    ]
    for level in LEVELS:
        for system in ("ratd", "planner"):
            cell = [r for r in rows if r["level"] == level and r["system"] == system]
            if not cell:
                continue
            overalls = [r["judge"]["overall"] for r in cell]
            sd = statistics.stdev(overalls) if len(overalls) > 1 else 0.0
            ctx = sum(r["mean_context_chars"] for r in cell) / len(cell)
            calls = sum(r["llm_calls"] or 0 for r in cell) / len(cell)
            dec = sum(r["decisions"] for r in cell) / len(cell)
            conv = sum(1 for r in cell if r["converged"])
            lines.append(
                f"| {level} | {system} | {conv}/{len(cell)} | {statistics.mean(overalls):.1f}±{sd:.1f} ({', '.join(str(o) for o in overalls)}) | {ctx:,.0f} | {dec:.1f} | {calls:.1f} |"
            )
    lines += ["", "## Per-run detail", ""]
    for r in rows:
        j = r["judge"]
        lines.append(
            f"- {r['run_id']} [{r['system']}] conv={r['converged']} overall={j['overall']} "
            f"(acc {j['accuracy']}, compl {j['completeness']}, struct {j['structure']}, consist {j['consistency']})"
            f"{' [auto-1]' if j.get('auto') else ''} ctx/decision={r['mean_context_chars']:,.0f} max={r['max_context_chars']:,}"
        )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def crossover_png(rows: list[dict[str, Any]], out_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib unavailable; skipping crossover.png", flush=True)
        return
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    x = list(range(1, len(LEVELS) + 1))
    for system, color in (("ratd", "tab:blue"), ("planner", "tab:orange")):
        quality, ctx = [], []
        for level in LEVELS:
            cell = [r for r in rows if r["level"] == level and r["system"] == system]
            quality.append(statistics.mean([r["judge"]["overall"] for r in cell]) if cell else None)
            ctx.append(statistics.mean([r["mean_context_chars"] for r in cell]) if cell else None)
        axes[0].plot(x, quality, marker="o", color=color, label=system)
        axes[1].plot(x, ctx, marker="o", color=color, label=system)
    axes[0].set_title("Judge overall score vs level")
    axes[0].set_ylim(0, 10)
    axes[1].set_title("Context chars per decision vs level")
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(LEVELS)
        ax.legend()
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "crossover.png", dpi=150)
    print(f"wrote {out_dir / 'crossover.png'}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="E1 judge + summary")
    parser.add_argument("--ratd-dir", default="results/e1/ratd")
    parser.add_argument("--planner-dir", default="results/e1/planner")
    parser.add_argument("--out-dir", default="results/e1")
    parser.add_argument("--judge-prompt", default="prompts/judge_v1.md")
    parser.add_argument("--rubrics-dir", default="rubrics")
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint", default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args(argv)
    config = Config(args.provider, args.model, args.temperature, args.max_tokens, args.local_endpoint)
    ensure_credentials(config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    judge_prompt = Path(args.judge_prompt).read_text(encoding="utf-8")
    rubrics = {lvl: (Path(args.rubrics_dir) / f"{lvl}.md").read_text(encoding="utf-8") for lvl in LEVELS}

    rows = collect(Path(args.ratd_dir), Path(args.planner_dir))
    order = list(range(len(rows)))
    random.Random(0).shuffle(order)  # fixed-seed, system-blind judging order
    for i in order:
        row = rows[i]
        print(f"judging {row['system']}/{row['run_id']}...", flush=True)
        row["judge"] = judge_one(row, rubrics[row["level"]], judge_prompt, config)
    for row in rows:
        row.pop("artifact", None)
    write_json(out_dir / "judge_scores.json", rows)
    summarize(rows, out_dir)
    crossover_png(rows, out_dir)
    print(f"wrote {out_dir / 'judge_scores.json'} and summary.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
