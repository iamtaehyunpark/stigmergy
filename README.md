# RATD Feasibility Probe

This repository implements the Phase 1 routing probe from `RATD_Probe_Spec.md`.
Phase 2 is intentionally not implemented until Phase 1 passes the spec's kill-order gate.

## Current Verdicts

**Q1: PARTIAL.** The Phase 1 harness, 20-task set, runner, and automated scorer are implemented. A real verdict is blocked because the local environment has no model API key configured.

**Q2: Not evaluated.** Phase 2 must not be built or run until Phase 1 passes.

**Q3: Not evaluated.** Phase 2 must not be built or run until Phase 1 passes.

## Configuration

Defaults:

- Provider: `anthropic`
- Model: `claude-sonnet-4-6`
- Temperature: `0`

Environment variables:

- `ANTHROPIC_API_KEY` for Anthropic
- `OPENAI_API_KEY` for OpenAI
- `RATD_PROVIDER` to override provider (`anthropic` or `openai`)
- `RATD_MODEL` to override the model

The runner uses Python's standard library only.

## Run Phase 1

```bash
python3 -m src.phase1 run
python3 -m src.phase1 score
```

To use OpenAI instead:

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
- `results/phase1/{*.json, scores.csv}`: blocked until API-backed run
- `results/phase2/*`: gated by Phase 1
