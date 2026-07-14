# RATD Feasibility Probe

This repository implements the Phase 1 routing probe from `RATD_Probe_Spec.md`.
Phase 2 is intentionally not implemented until Phase 1 passes the spec's kill-order gate.

## Current Verdicts

**Q1: PASS.** With `prompts/harness_v3.md`, a single-shot run (no repair loop) on local `qwen3.6` scores valid_json 20/20, action_match 20/20, mean decomposition_sanity 2.00, condition_correctness 100% — above the §1.5 bar. Full iteration history (v1 13/20 → v2 15/20 → v3 20/20) is in `results/phase1/iteration_log.md`. Residual outside the bar: namespace_discipline 18/20 (aggregator children on t06/t08 wrote to the parent namespace).

**Q2: PASS.** Schema agreement 100% (26/26) in the final `results/phase2_v5b/` runs: every namespace/key referenced in a trigger condition was independently written by the producing agent at the exact declared path. Zero conflicts, zero trigger-fire errors across all 6 runs.

**Q3: PASS.** 6/6 runs converged within rails under `prompts/harness_v5.md`, including the recursive t09 (depth 2, interface delegation across levels, one defer/wake cycle per run). Two architecture-level defects were found and fixed on the way — interface orphaning under recursion (fixed by the v5 interface contract + validator support) and dropped DEFERs (runtime never registered wake conditions as triggers) — full history in `results/phase1/iteration_log.md`.

## Configuration

Defaults:

- Provider: `local`
- Model: `qwen3.6`
- Local endpoint: `http://127.0.0.1:8000/v1/chat/completions`
- Temperature: `0`

Environment variables:

- `RATD_PROVIDER` to override provider (`local`, `anthropic`, or `openai`)
- `RATD_MODEL` to override the model
- `RATD_LOCAL_ENDPOINT` to override the local OpenAI-compatible chat endpoint
- `ANTHROPIC_API_KEY` for Anthropic
- `OPENAI_API_KEY` for OpenAI

The runner uses Python's standard library only.

On the server, the local model environment follows `../two-stage-stitcher`:

```bash
source /data/tpark45/engramtrace-env/bin/activate
export HF_HOME=/data/tpark45/hugginface
```

The current default expects an already-running VLLM OpenAI-compatible server on port `8000`.

## Run Phase 1

```bash
python3 -m src.phase1 run
python3 -m src.phase1 score
```

To use a different local endpoint:

```bash
RATD_LOCAL_ENDPOINT=http://127.0.0.1:8000/v1/chat/completions \
RATD_MODEL=qwen3.6 \
python3 -m src.phase1 run
```

To use an API provider instead:

```bash
RATD_PROVIDER=openai RATD_MODEL=<model-name> python3 -m src.phase1 run
python3 -m src.phase1 score
```

Saved outputs:

- Raw model responses: `results/phase1/{task_id}.raw.txt`
- Strict parsed action documents: `results/phase1/{task_id}.json`
- Scores: `results/phase1/scores.csv`
- Run metadata: `results/phase1/run_meta.json`

## Deliverables Status

- `prompts/harness_v1.md`: present
- `tasks/phase1_tasks.json`: present
- `src/phase1.py`: present
- `results/phase1/iteration_log.md`: present
- `results/THEORY_VS_REALITY.md`: started
- `results/phase1/{*.json, scores.csv}`: pending full local-model run
- `results/phase2/*`: gated by Phase 1
