"""ET-series run entrypoint.

    python3 -m src.ratd_v2.run --arm r --tasks tasks/et_ladder.json \
        --task-ids L1 --reps 4 --out-dir results/et

Run directories follow the ET deliverable layout:
    results/et/{arm}_{level}_r{rep}/  (trace.jsonl, state.json, metrics.json,
                                       run_meta.json)
"""
from __future__ import annotations

import argparse
import os
import shutil
import time
from pathlib import Path

from .client import (DEFAULT_LOCAL_ENDPOINT, DEFAULT_MAX_TOKENS, DEFAULT_MODEL,
                     DEFAULT_PROVIDER, Config, ensure_credentials, load_json,
                     write_json)
from .runtime import ARMS, Rails, Runtime, sha256_file

HARNESS_FILES = {
    "p": {"planner": "harness_planner.md", "worker": "harness_worker.md"},
    "r": {"ratd": "harness_ratd.md"},
    "s": {"stig": "harness_stig.md"},
}


def load_harnesses(harness_dir: Path, arm: str) -> tuple[dict[str, str], dict[str, str]]:
    texts: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for role, fname in HARNESS_FILES[arm].items():
        path = harness_dir / fname
        texts[role] = path.read_text(encoding="utf-8")
        hashes[str(path)] = sha256_file(path)
    return texts, hashes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RATD v2 ET runner")
    parser.add_argument("--arm", required=True, choices=sorted(ARMS))
    parser.add_argument("--tasks", default="tasks/et_ladder.json")
    parser.add_argument("--task-ids", default="", help="comma-separated; empty = all")
    parser.add_argument("--reps", type=int, default=4)
    parser.add_argument("--rep-start", type=int, default=1)
    parser.add_argument("--out-dir", default="results/et")
    parser.add_argument("--harness-dir", default="prompts/et")
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint",
                        default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--max-llm-calls", type=int, default=300)
    parser.add_argument("--wall-clock-s", type=float, default=3600.0)
    parser.add_argument("--r-max", type=int, default=30)
    parser.add_argument("--window-rounds", type=int, default=8)
    args = parser.parse_args(argv)

    config = Config(args.provider, args.model, args.temperature,
                    args.max_tokens, args.local_endpoint)
    ensure_credentials(config)
    rails = Rails(max_llm_calls=args.max_llm_calls,
                  wall_clock_s=args.wall_clock_s,
                  r_max=args.r_max, window_rounds=args.window_rounds)
    harness_dir = Path(args.harness_dir)
    harnesses, harness_hashes = load_harnesses(harness_dir, args.arm)
    wanted = tuple(t for t in args.task_ids.split(",") if t)
    base = Path(args.out_dir)
    summary = []
    for task in load_json(Path(args.tasks)):
        if wanted and task["id"] not in wanted:
            continue
        for rep in range(args.rep_start, args.rep_start + args.reps):
            run_id = f"{args.arm}_{task['id']}_r{rep}"
            run_dir = base / run_id
            if (run_dir / "metrics.json").exists():
                print(f"skipping {run_id} (completed)", flush=True)
                summary.append(load_json(run_dir / "metrics.json"))
                continue
            if run_dir.exists():
                print(f"clearing partial {run_id}", flush=True)
                try:
                    shutil.rmtree(run_dir)
                except OSError as exc:
                    # AFS/NFS can hold locks from a killed process; move the
                    # partial aside instead of dying (observed: .__afsE* busy)
                    stale = run_dir.with_name(
                        f"{run_id}.stale-{int(time.time())}")
                    print(f"  rmtree failed ({exc}); moving aside to "
                          f"{stale.name}", flush=True)
                    run_dir.rename(stale)
            print(f"running {run_id}...", flush=True)
            run_dir.mkdir(parents=True, exist_ok=True)
            write_json(run_dir / "run_meta.json", {
                "run_id": run_id,
                "arm": args.arm,
                "task": task,
                "provider": config.provider,
                "model": config.model,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "local_endpoint": config.local_endpoint,
                "rails": vars(rails),
                "harness_files": harness_hashes,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            })
            metrics = Runtime(run_id, args.arm, task, harnesses, config,
                              run_dir, rails).run()
            h = metrics["health"]
            print(f"  -> calls={metrics['llm_calls']} agents={metrics['n_agents']} "
                  f"tokens={metrics['total_tokens']} root={h['root_state']} "
                  f"failure={h['systemic_failure']} rail={h['rail_hit'] or '-'}",
                  flush=True)
            summary.append(metrics)
    write_json(base / f"summary_{args.arm}.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
