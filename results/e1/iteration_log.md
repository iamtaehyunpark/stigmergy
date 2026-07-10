# E1 Iteration Log — Crossover curve

Spec: `RATD_Experiment_Spec_E0-E2.md` §2.1–2.5. Claim under test:
theory §3 `[UNTESTED]` — replanning central planner pays O(n) context
per decision and degrades as state grows; RATD pays O(1). Prediction:
planner ≥ RATD on small tasks; gap reverses and widens with size.

## Build (pre-run) — everything frozen before the first L1 run

- `src/planner_baseline.py`: replanning central planner. ONE planner
  call after every completed task, receiving ROOT GOAL + the ENTIRE
  accumulated state (all done entries, full values; state budget
  `--max-state-chars` 60000, oldest-entries-first truncation with
  truncation events logged as measurement) + previous remaining plan;
  emits the updated remaining plan (strict JSON, same schema as the
  tree baseline, validated + 3-attempt repair). Same worker prompt,
  same visibility rule (own/ancestor namespaces + condition refs —
  the planner is TOLD conditions double as read grants, so workers
  are not strawman-starved), same rails (120 calls / 40 min), same
  resume semantics. Logged per planner call: context chars
  (system+user — the O(n) axis), plan churn (added/removed/modified
  vs previous plan), truncation. Convergence = planner returns
  {"tasks": []} with a root/ deliverable written, no rails/stall.
  Stall = two consecutive identical no-runnable plans.
- `tasks/e1_ladder.json` (one domain family — developer-facing
  technical writing — so the rubric family is stable): L1 explainer
  (t17-class), L2 = probe t06 verbatim, L3 = E0 d03 verbatim, L4 =
  d03 + Figure-1-style terminology-standard track (the replanning
  regime; nameable-address discovery, per the Figure-1 boundary).
- `prompts/judge_v1.md` + `rubrics/L1–L4.md`: FROZEN as of this
  commit, before any E1 run. Judge model = agent model (qwen3.6),
  system-blind, fixed-seed judging order, 5 integer dimensions +
  rationale; empty artifacts auto-score 1 (declared).
- `src/e1_judge.py`: collects the 24 runs, judges, writes
  judge_scores.json / summary.md / crossover.png (two panels:
  quality vs level, context-chars per decision vs level).
- `src/phase2.py` instrumentation only: `route_context` trace event
  (harness+context chars per routing decision) — RATD's side of the
  context-cost axis. No harness or behavioral change; harness_v6
  frozen for all levels.
- Offline mock smoke green: replan-per-task loop, churn counting,
  truncation events, done-declaration convergence, judge collection
  (RATD sqlite + planner entries.json), blind scoring, summary.

## Pre-registered honesty constraints (spec 2.5)

- One harness (v6) for all levels, frozen before L1; no per-level
  tuning to chase the curve. If the planner wins at every level,
  that is the finding and THEORY_VS_REALITY records the
  falsification at this scale.
- Judge is the weakest link: inter-repetition judge variance is
  reported per cell; if variance swamps the system gap, only the
  context-cost axis is claimable.
- n=3 per cell is feasibility-scale evidence; temp-0 vLLM clustering
  may reduce effective n further (known from E0/Figure-1) — per-run
  scores are listed, not just means.
- Decision-context units are characters (both systems identically:
  system prompt + user message), not tokens; the curve compares like
  with like.

## Protocol (24 runs + judging)

1. RATD: `python3 -m src.phase2 --harness prompts/harness_v6.md
   --tasks tasks/e1_ladder.json --out-dir results/e1/ratd
   --repetitions 3`
2. Planner: `python3 -m src.planner_baseline --tasks
   tasks/e1_ladder.json --out-dir results/e1/planner --repetitions 3`
3. Judge + summary: `python3 -m src.e1_judge`
