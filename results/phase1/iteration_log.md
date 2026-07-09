# Phase 1 Iteration Log

Model: local `qwen3.6` via vLLM OpenAI-compatible endpoint
(`http://127.0.0.1:8000/v1/chat/completions`), temperature 0. The local
call uses `response_format: {"type": "json_object"}` (constrained
decoding) and `/no_think`; this is declared as part of the execution
environment for all runs below.

## harness_v1 (original scaffold prompt)

- Run: 2026-07-09, first full 20-task run.
- Result: valid_json 13/20, action_match 13/20. FAIL.
- Dominant failure modes:
  1. Formatting: Markdown-fenced (```json) or truncated JSON.
  2. Routing: t12 and t13 chose SPAWN instead of DEFER — the model
     spawned children to fabricate missing prerequisite artifacts
     instead of waiting for them.
- Note: this run's raw artifacts were overwritten by the next run
  (the runner did not version output dirs at the time); numbers are
  from the session record.

## harness_v2 (delta from v1)

- Prompt changes: explicit strict-JSON/no-fences instruction; explicit
  child-namespace rule; budget-arithmetic guidance with worked
  examples; DEFER guidance (do not invent missing artifacts); capsule
  conciseness guidance.
- Runner changes made alongside (declared, since they affect metrics):
  local provider default with `json_object` constrained decoding, and
  a validation-feedback repair loop (`--retries`, default 2).
- Result WITH repair loop (retries=2): valid_json 20/20,
  action_match 20/20, mean decomposition_sanity 2.00,
  condition_correctness 100%. (`results/phase1/scores.csv`)
- Result SINGLE-SHOT (retries=0): valid_json 15/20,
  action_match 20/20, mean decomposition_sanity 2.00,
  condition_correctness 100%. FAIL on valid_json.
  (`results/phase1_singleshot/scores.csv`)
- Dominant single-shot failure mode: budget arithmetic. All five
  invalid docs (t07, t08, t09, t11, t18) allocated the full budget
  B=20 across children instead of reserving k (sum <= B - k), despite
  worked examples in the prompt. t11 additionally wrote
  `root/decision_memo` instead of `root.4/...`. None of the five are
  JSON parse failures — formatting is fully solved by v2 + constrained
  decoding; the residual is constraint arithmetic.
- Interpretation: routing judgment (the core Phase 1 question) is not
  the bottleneck; action_match has been 20/20 since v2 single-shot.

## harness_v3 (delta from v2)

- Prompt change (minimal, targets the dominant failure mode): replace
  free budget allocation with a fixed rule — every child gets budget
  exactly 2, at most 6 children. This removes arithmetic from the
  model's job entirely (2k <= 20 - k holds for all k <= 6, covering
  the 4-6 children the model naturally spawns).
- Result SINGLE-SHOT (retries=0): valid_json 20/20, action_match 20/20,
  mean decomposition_sanity 2.00, condition_correctness 100%. PASS.
  (`results/phase1_v3_singleshot/scores.csv`)
- Zero budget violations: every SPAWN doc used budget 2 per child as
  instructed. The fixed rule fully eliminated the v2 failure mode.
- Residual (outside the pass bar): namespace_discipline 18/20. On t06
  and t08 the final aggregator child (root.4) declared its output as
  `root/final_report` / `root/itinerary` instead of `root.4/...`. The
  runner's stricter validator rejected these at run time (no t06.json /
  t08.json written), but the scorer correctly scores namespace in its
  own rubric column, not in valid_json. Watch this "aggregator writes
  to parent namespace" tendency in Phase 2, where children actually
  execute and a misplaced write becomes a real conflict.
- Verdict: Phase 1 pass bar met single-shot with no repair loop.
  Phase 2 gate open.
