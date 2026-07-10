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

## Results (24 runs + judging) — cost axis: theory CONFIRMED; quality axis: inconclusive at depth

Full table in `results/e1/summary.md`, curves in `crossover.png`.

- **Context per decision (the theorem's cost half): confirmed exactly
  as predicted.** RATD flat 7.2k → 8.4k chars L1→L4 (O(1)); planner
  4.6k → 41.6k (9x growth, O(n)) with 4-5 state-truncation events per
  L4 run (the degradation mechanism, observed) and plan churn rising
  to 16 added + 4 modified per run. Cost crossover sits between L2
  and L3.
- **Quality: planner wins at shallow levels** (L1 9.7 vs 9.0, L2 10.0
  vs 9.0 — matching the pre-registered "planner >= RATD on small
  tasks"); **at L3/L4 BOTH systems collapse bimodally** (per-run 1s
  and 9s; within-cell sd up to 4.6). Per the pre-registered rule,
  judge/outcome variance swamps the system gap at depth: only the
  context-cost axis is claimable there.
- The deep-level collapse is a shared, architecture-independent
  failure: 5 converged runs (1 RATD, 4 planner) shipped a 15-char
  final artifact = the `{"outputs": []}` schema-mismatch fallback.
  Verified mechanism (ratd L3_r3): the assembly worker emitted
  18,555 chars against a 4,000-token output cap - unclosed JSON, 3
  parse failures, stub. The judge scored the stubs 1 across the
  board, correctly (content-level metrics catching what address-level
  metrics miss, again). ratd L4_r3 shipped a planning document
  instead of the guide (shallow root EXECUTE trajectory).
- **First ORGANIC blind-defer failures** (ratd L3_r1/r2, the 2/24
  non-convergences): the glossary agent, spawned condition-null with
  no read grants, DEFERred on guessed addresses
  (`done("root.1/draft")...`) that no agent ever declared; the wake
  trigger could never fire; root's integrator starved. Exactly the
  Figure-1 nameability boundary, now appearing untriggered in a
  standard task. Harness stayed frozen per pre-registration; the
  failures stand in the results.
- Judge behaved sanely: bimodal scores track artifact reality
  (verified by reading the artifacts), not system identity; empty/
  stub artifacts scored 1, real guides 5-9.

Verdict for theory §3: the O(1)-vs-O(n) context claim graduates from
[UNTESTED] to CONFIRMED at feasibility scale on the cost axis. The
quality-crossover half remains open pending a worker/assembly
mechanism that can actually produce deep integrated artifacts (the
binding constraint at L3/L4 is single-call output capacity, not
coordination).
