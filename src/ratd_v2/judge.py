"""ET judging + summary + crossover_v2.png.

Reuses the frozen E1 judge prompt (prompts/judge_v1.md) and the frozen
L1-L3 rubrics; L4 reuses the frozen E1 L4 rubric; L5 is new (frozen
before any ET run). System-blind: artifacts are judged in fixed-seed
shuffled order with no arm identity in the judge prompt. Per-run scores
published.

Judge artifact = concatenated heads of global/final/* in path order;
fallback (flagged) = all global heads.

    python3 -m src.ratd_v2.judge --runs-dir results/et
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
from pathlib import Path
from typing import Any

from .client import (DEFAULT_LOCAL_ENDPOINT, DEFAULT_MAX_TOKENS, DEFAULT_MODEL,
                     DEFAULT_PROVIDER, Config, call_model, ensure_credentials,
                     load_json, write_json)

LEVELS = ("L1", "L2", "L3", "L4", "L5")
ARM_NAMES = ("p", "r", "s")
ARTIFACT_CAP = 24000
JUDGE_KEYS = ("accuracy", "completeness", "structure", "consistency", "overall")


def final_artifact(state: dict[str, Any]) -> tuple[str, bool]:
    """Returns (artifact_text, used_fallback)."""
    glob = state.get("global", {})
    parts = []
    for path in sorted(glob):
        art = glob[path]
        if not art.get("head"):
            continue
        if path.startswith("global/final/"):
            head = art["versions"][art["head"] - 1]
            parts.append(f"## {path}\n{head['content']}")
    if parts:
        return "\n\n".join(parts), False
    for path in sorted(glob):
        art = glob[path]
        if art.get("head"):
            head = art["versions"][art["head"] - 1]
            parts.append(f"## {path}\n{head['content']}")
    return "\n\n".join(parts), True


def collect(runs_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        metrics_path = run_dir / "metrics.json"
        state_path = run_dir / "state.json"
        if not metrics_path.exists() or not state_path.exists():
            continue
        name = run_dir.name                       # {arm}_{level}_r{rep}
        bits = name.split("_")
        if len(bits) != 3 or bits[0] not in ARM_NAMES:
            continue
        metrics = load_json(metrics_path)
        artifact, fallback = final_artifact(load_json(state_path))
        prompt_chars = [c for a in metrics.get("per_agent", {}).values()
                        for c in a.get("prompt_chars_per_round", [])]
        rows.append({
            "run_id": name,
            "arm": bits[0],
            "level": bits[1],
            "rep": bits[2],
            "systemic_failure": metrics["health"]["systemic_failure"],
            "rail_hit": metrics["health"]["rail_hit"],
            "llm_calls": metrics["llm_calls"],
            "total_tokens": metrics["total_tokens"],
            "n_agents": metrics["n_agents"],
            "mean_prompt_chars": (sum(prompt_chars) / len(prompt_chars))
                if prompt_chars else 0,
            "max_prompt_chars": max(prompt_chars, default=0),
            "artifact_fallback": fallback,
            "artifact": artifact,
        })
    return rows


def build_repair(message: str, raw: str, note: str) -> str:
    return (f"Your previous output was invalid: {note}\n"
            "Return strict JSON only with integer 1-10 fields "
            f"{JUDGE_KEYS} and a rationale string.\n\n{message}\n\n"
            f"Previous output:\n{raw}")


def judge_one(row: dict[str, Any], rubric: str, judge_prompt: str,
              config: Config) -> dict[str, Any]:
    artifact = row["artifact"]
    truncated = len(artifact) > ARTIFACT_CAP
    if truncated:
        artifact = artifact[:ARTIFACT_CAP] + "\n[ARTIFACT TRUNCATED FOR JUDGING]"
    if not artifact.strip():
        return {**{k: 1 for k in JUDGE_KEYS},
                "rationale": "empty artifact (auto-scored 1)",
                "artifact_truncated": False, "auto": True}
    message = f"RUBRIC:\n{rubric}\n\nARTIFACT:\n{artifact}"
    raw = ""
    note = ""
    for attempt in range(3):
        prompt = message if attempt == 0 else build_repair(message, raw, note)
        reply = call_model([{"role": "system", "content": judge_prompt},
                            {"role": "user", "content": prompt}],
                           config, json_mode=True)
        raw = reply.text
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            note = "strict JSON parse failed"
            continue
        if isinstance(parsed, dict) and all(
                isinstance(parsed.get(k), int) and 1 <= parsed[k] <= 10
                for k in JUDGE_KEYS):
            return {**{k: parsed[k] for k in JUDGE_KEYS},
                    "rationale": str(parsed.get("rationale", "")),
                    "artifact_truncated": truncated, "auto": False}
        note = f"must contain integer 1-10 fields {JUDGE_KEYS}"
    return {**{k: 1 for k in JUDGE_KEYS},
            "rationale": f"judge output invalid after retries: {raw[:200]}",
            "artifact_truncated": truncated, "auto": True}


def summarize(rows: list[dict[str, Any]], out_dir: Path) -> None:
    lines = [
        "# ET Summary — three arms (P centralized, R RATD multi-round, S RATD single-shot)",
        "",
        "Judge: qwen3.6 (same as agents), frozen prompts/judge_v1.md +",
        "rubrics/et/L*.md, system-blind, fixed-seed order. n=4 per cell.",
        "Per-run scores listed (temp-0 clustering may reduce effective n).",
        "",
        "| Level | Arm | fail | overall (mean±sd, per-run) | ctx chars/activation (mean) | total tokens (mean) | calls (mean) | agents (mean) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for level in LEVELS:
        for arm in ARM_NAMES:
            cell = [r for r in rows if r["level"] == level and r["arm"] == arm]
            if not cell:
                continue
            overalls = [r["judge"]["overall"] for r in cell]
            sd = statistics.stdev(overalls) if len(overalls) > 1 else 0.0
            ctx = statistics.mean([r["mean_prompt_chars"] for r in cell])
            toks = statistics.mean([r["total_tokens"] for r in cell])
            calls = statistics.mean([r["llm_calls"] for r in cell])
            agents = statistics.mean([r["n_agents"] for r in cell])
            fails = sum(1 for r in cell if r["systemic_failure"])
            lines.append(
                f"| {level} | {arm} | {fails}/{len(cell)} | "
                f"{statistics.mean(overalls):.1f}±{sd:.1f} "
                f"({', '.join(str(o) for o in overalls)}) | {ctx:,.0f} | "
                f"{toks:,.0f} | {calls:.1f} | {agents:.1f} |")
    lines += ["", "## Per-run detail", ""]
    for r in rows:
        j = r["judge"]
        lines.append(
            f"- {r['run_id']} fail={r['systemic_failure']} rail={r['rail_hit'] or '-'} "
            f"overall={j['overall']} (acc {j['accuracy']}, compl {j['completeness']}, "
            f"struct {j['structure']}, consist {j['consistency']})"
            f"{' [auto-1]' if j.get('auto') else ''}"
            f"{' [fallback-artifact]' if r['artifact_fallback'] else ''} "
            f"ctx/act={r['mean_prompt_chars']:,.0f} max={r['max_prompt_chars']:,} "
            f"tokens={r['total_tokens']:,}")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def crossover_png(rows: list[dict[str, Any]], out_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib unavailable; skipping crossover_v2.png", flush=True)
        return
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    x = list(range(1, len(LEVELS) + 1))
    labels = {"p": "P centralized planner", "r": "R RATD multi-round",
              "s": "S RATD single-shot"}
    colors = {"p": "tab:orange", "r": "tab:blue", "s": "tab:green"}
    for arm in ARM_NAMES:
        quality, ctx, toks = [], [], []
        for level in LEVELS:
            cell = [r for r in rows if r["level"] == level and r["arm"] == arm]
            quality.append(statistics.mean([r["judge"]["overall"] for r in cell])
                           if cell else None)
            ctx.append(statistics.mean([r["mean_prompt_chars"] for r in cell])
                       if cell else None)
            toks.append(statistics.mean([r["total_tokens"] for r in cell])
                        if cell else None)
        axes[0].plot(x, quality, marker="o", color=colors[arm], label=labels[arm])
        axes[1].plot(x, ctx, marker="o", color=colors[arm], label=labels[arm])
        axes[2].plot(x, toks, marker="o", color=colors[arm], label=labels[arm])
    axes[0].set_title("Judge overall score vs level")
    axes[0].set_ylim(0, 10)
    axes[1].set_title("Context per decision vs level")
    axes[2].set_title("Total tokens per run vs level")
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(LEVELS)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    fig.suptitle("ET crossover — v2 measurement: context per decision = per-round "
                 "prompt size (window + workspace-loaded state + tool returns), "
                 "all agents; planner rounds included for Arm P", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out_dir / "crossover_v2.png", dpi=150)
    print(f"wrote {out_dir / 'crossover_v2.png'}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ET judge + summary")
    parser.add_argument("--runs-dir", default="results/et")
    parser.add_argument("--out-dir", default="results/et")
    parser.add_argument("--judge-prompt", default="prompts/judge_v1.md")
    parser.add_argument("--rubrics-dir", default="rubrics/et")
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint",
                        default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=4000)
    args = parser.parse_args(argv)
    config = Config(args.provider, args.model, args.temperature,
                    args.max_tokens, args.local_endpoint)
    ensure_credentials(config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    judge_prompt = Path(args.judge_prompt).read_text(encoding="utf-8")
    rubrics = {lvl: (Path(args.rubrics_dir) / f"{lvl}.md").read_text(encoding="utf-8")
               for lvl in LEVELS}
    rows = collect(Path(args.runs_dir))
    order = list(range(len(rows)))
    random.Random(0).shuffle(order)   # fixed-seed, system-blind judging order
    for i in order:
        row = rows[i]
        print(f"judging {row['run_id']}...", flush=True)
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
