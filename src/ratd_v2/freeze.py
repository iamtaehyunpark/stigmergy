"""Generate ET_PREREGISTRATION.md (handoff rule 1).

Copies the predictions and fair-fight rules VERBATIM from
docs/RATD_Experiment_Spec_ET.md, then records sha256 hashes of every
frozen artifact (harness variants + their sources, judge prompt,
rubrics, task file), the harness variant composition + diffs, the model
config, and the mechanical metric definitions. Run once, at freeze;
after the first scored run nothing it references may change (defects =>
discard + rerun + deviations section).

    python3 -m src.ratd_v2.freeze
"""
from __future__ import annotations

import argparse
import difflib
import subprocess
import time
from pathlib import Path

from .runtime import sha256_file

SPEC = Path("docs/RATD_Experiment_Spec_ET.md")
FROZEN = [
    "prompts/et/harness_ratd.md",
    "prompts/et/harness_planner.md",
    "prompts/et/harness_worker.md",
    "prompts/et/harness_stig.md",
    "prompts/et/src/core.md",
    "prompts/et/src/role_ratd.md",
    "prompts/et/src/role_planner.md",
    "prompts/et/src/role_worker.md",
    "prompts/et/src/role_stig.md",
    "prompts/et/src/surface_circuit.md",
    "prompts/et/src/surface_planner.md",
    "prompts/et/src/surface_stig.md",
    "prompts/judge_v1.md",
    "rubrics/et/L1.md",
    "rubrics/et/L2.md",
    "rubrics/et/L3.md",
    "rubrics/et/L4.md",
    "rubrics/et/L5.md",
    "tasks/et_ladder.json",
]
RUNTIME_FILES = sorted(str(p) for p in Path("src/ratd_v2").glob("*.py"))


def spec_section(text: str, start_marker: str, end_marker: str) -> str:
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    return text[i:j].rstrip()


def variant_diff(a: Path, b: Path) -> str:
    return "".join(difflib.unified_diff(
        a.read_text(encoding="utf-8").splitlines(keepends=True),
        b.read_text(encoding="utf-8").splitlines(keepends=True),
        fromfile=str(a), tofile=str(b), n=1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="ET_PREREGISTRATION.md")
    parser.add_argument("--model", default="qwen3.6")
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--max-llm-calls", type=int, default=300)
    parser.add_argument("--wall-clock-s", type=int, default=3600)
    parser.add_argument("--r-max", type=int, default=30)
    parser.add_argument("--window-rounds", type=int, default=8)
    args = parser.parse_args(argv)
    spec = SPEC.read_text(encoding="utf-8")
    fair_fight = spec_section(spec, "**FAIR-FIGHT RULES", "## 2. Task ladder")
    predictions = spec_section(spec, "## 4. Pre-registered predictions",
                               "## 5. Deliverables")
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True,
                                capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        commit = "(not in a git checkout)"

    lines = [
        "# ET_PREREGISTRATION — frozen before run 1",
        "",
        f"Frozen: {time.strftime('%Y-%m-%d %H:%M:%S %z')} · git {commit}",
        "Spec: docs/RATD_Experiment_Spec_ET.md v1.1 (verbatim excerpts below).",
        "After the first scored run, nothing referenced here changes. If a",
        "defect forces a change, the affected runs are discarded and rerun,",
        "and the change is logged under Deviations.",
        "",
        "## Predictions (verbatim from ET spec §4)",
        "",
        predictions,
        "",
        "## Fair-fight rules (verbatim from ET spec §1)",
        "",
        fair_fight,
        "",
        "## Design (n, ladder, order)",
        "",
        "5 levels (tasks/et_ladder.json) × 3 arms × n=4 reps = 60 runs.",
        "Run order: interleave arms within level, level 1 → 5",
        "(r,p,s, rep-by-rep). Judging: system-blind, fixed-seed (0) shuffled",
        "order, per-run scores published (src/ratd_v2/judge.py).",
        "",
        "## Model & rails (identical across arms)",
        "",
        f"- model: {args.model}, temp 0, local vLLM, max_tokens {args.max_tokens} per call",
        "- serving (owned instance, frozen): vLLM 0.16.1rc1, single GPU,",
        "  `vllm serve Qwen/Qwen3.6-27B --served-model-name qwen3.6 --port 8001",
        "  --max-model-len 262144 --gpu-memory-utilization 0.92`; endpoint",
        "  http://127.0.0.1:8001/v1/chat/completions (galaxy-05 GPU 0);",
        "  no other workload shares the serving process",
        f"- global call rail {args.max_llm_calls}, wall clock {args.wall_clock_s}s per run",
        f"- R_max {args.r_max} rounds per multi-round agent (Arms P, R);",
        "  Arm S bounded by the call rail alone (spec rule 1)",
        f"- rolling window {args.window_rounds} rounds (Arms P, R); Arm S carries only",
        "  the previous activation's op results (in-substrate continuity)",
        "- Arm S decodes under response_format=json_object (single action",
        "  document; the v1 single-shot model re-hosted). Arms P/R emit free",
        "  text with fenced tool blocks. Same parser, same tools, same caps.",
        "",
        "## Mechanical metric definitions (fixed before run 1)",
        "",
        "- Context per decision (v2 definition): per-round prompt size in",
        "  chars (system + identity + window + delivered observations),",
        "  logged per llm_call; token counts logged per llm_reply.",
        "- Adaptation event: structure-changing tool call (spawn /",
        "  circuit.add_rule / circuit.update_rule) by an agent at round or",
        "  activation > 1 (Arms R/S); planner spawn at round > 1 (Arm P).",
        "- Arm S chain: maximal run of consecutive activations of one agent",
        "  linked by self-resume rules (continue / wait-self).",
        "- Cross-activation handoff: read whose target was last written by a",
        "  different agent; delivered chars = bounded result size,",
        "  truncation flagged.",
        "- Judge artifact: concatenated heads under global/final/* in path",
        "  order; fallback to all global heads is recorded per run.",
        "- Health verdict: quiescence + failure predicate per Playground",
        "  Spec §5, logged mechanically every run (doctor off).",
        "- Variance rule (spec §4): within-cell sd > 3 on the judge scale →",
        "  that cell reports cost + adaptation axes only.",
        "",
        "## Frozen artifacts (sha256)",
        "",
    ]
    for f in FROZEN:
        lines.append(f"- `{f}` {sha256_file(Path(f))}")
    lines += ["", "### Runtime (reference, not judge-visible)", ""]
    for f in RUNTIME_FILES:
        lines.append(f"- `{f}` {sha256_file(Path(f))}")
    lines += [
        "",
        "## Harness variants: composition + diffs",
        "",
        "Variants are generated by src/ratd_v2/build_harnesses.py by",
        "concatenating role/core/surface sources; the CORE",
        "(prompts/et/src/core.md — tool docs + behavioral guidance) is",
        "byte-identical across all four variants by construction.",
        "",
        "| variant | composition |",
        "|---|---|",
        "| harness_ratd.md | role_ratd + core + surface_circuit |",
        "| harness_planner.md | role_planner + core + surface_planner |",
        "| harness_worker.md | role_worker + core |",
        "| harness_stig.md | role_stig + core + surface_circuit + surface_stig |",
        "",
        "### Unified diffs vs harness_ratd.md",
        "",
    ]
    base = Path("prompts/et/harness_ratd.md")
    for other in ("harness_planner.md", "harness_worker.md", "harness_stig.md"):
        lines += [f"#### {other}", "", "```diff",
                  variant_diff(base, Path("prompts/et") / other), "```", ""]
    lines += [
        "## Deviations",
        "",
        "(none at freeze)",
        "",
    ]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
