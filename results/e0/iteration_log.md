# E0-min Iteration Log

Spec: `RATD_Experiment_Spec_E0-E2.md` §E0-min. Baseline: probe-final
`src/phase2.py` + `prompts/harness_v5.md` (commit 56ff825).

## Build iteration 0 (pre-run) — harness_v6 + budget-removal delta

- `prompts/harness_v6.md`, forked from v5:
  - Budget rule section deleted, replaced by the spec's two-line
    "Spawn cost" note (no budget; finite global call limit).
  - Participation rule section added: SPAWN requires `self_role`
    (parallel share / gated integrator / review job), ≥ 1 output,
    written under the agent's own namespace or its owed interface
    paths. `budget` removed from the subtask schema; `self_role`
    added to the JSON schema.
  - Declared deviation from the spec's "everything else byte-identical
    to v5": the Interface contract's SPAWN bullet now names the
    agent's own self_role as the normal producer of owed paths, with
    delegation to a subtask as fallback. Keeping the v5 wording
    ("assign each owed path to exactly one of your subtasks") would
    contradict the participation rule and the updated validator
    (self_role outputs count toward interface coverage per spec §0.2).
    One sentence in the shared-memory section also adds self_role
    outputs to what conditions may reference.
- `src/phase2.py` delta (124 insertions / 57 deletions — over the
  spec's ~60-line target; the excess is the new metrics plumbing, not
  extra mechanism):
  - `budget` removed from `AgentSpec`, the validator (int/sum/negative
    checks), `spawn()` (allocation clipping), and context
    (`REMAINING BUDGET` → `GLOBAL CALLS REMAINING: {max_calls − used}`).
  - Rails raised per spec: 120 LLM calls, depth 8, 40 min wall-clock.
    Rails are now the only bound.
  - Participation rule, runtime side: after registering children, the
    spawning agent is re-enqueued (condition null) or
    trigger-registered (condition set, trigger id `…:{task_id}:self`)
    as a `worker_only` continuation carrying the self_role task —
    it goes straight to the worker path, not through routing, so an
    agent routes at most once. self_role outputs of root count toward
    `root_outputs` (convergence target); a root that EXECUTEs now also
    registers its declared outputs as the convergence target.
  - Validator: SPAWN without a valid `self_role` (goal + ≥1 output
    under own namespace or owed paths) is invalid (repairable).
    Interface coverage = children's declared outputs ∪ self_role
    outputs. Conditions (children's and self_role's) may reference
    either set.
  - Metrics extended per spec §0.4: `total_spawns`, `termination`
    (natural/rail), `cross_branch_unique_pairs` (unique (agent, path)
    pairs, reported with the raw event count as declared fallback per
    inherited rule 6), `self_role_parallel`/`self_role_gated`,
    `interface_owed_self`/`interface_owed_delegated` (self-fulfillment
    rate). `budget_violations` metric removed with the machinery.
  - CLI: `--tasks tasks/e0_tasks.json` (d01–d04), `--task-ids` filter
    (empty = all tasks in file order), `--out-dir results/e0`,
    `--repetitions 3` defaults.
- `tasks/e0_tasks.json`: d01 (= probe t09, regression), d02 (= probe
  t15, depth-3 candidate), d03 (constructed deep: 4-chapter field
  guide), d04 (breadth stress: 6-market launch kits).
- Verified offline with a scripted mock model (no network): SPAWN with
  gated self_role, repair loop on a missing self_role, depth-2
  recursion, DEFER/wake, natural convergence, and all new metrics
  fields populated as expected.

## Build iteration 1 (mid-protocol) — resume semantics after session-teardown kill

- First 12-run invocation was killed mid-d03_r2 by server session
  teardown (`Linger=no` for the user: the systemd user instance — and
  the job under it — dies with the SSH session). Not an experiment
  bug; d01/d02 (6 runs) and d03_r1 completed with valid metrics.json;
  d03_r2 partial; d03_r3 and all of d04 never ran.
- Runtime hazard found while planning the rerun: `Runtime` reuses an
  existing out dir — it appends to `trace.jsonl` and reopens
  `state.sqlite`, so rerunning into a completed/partial dir would
  raise a primary-key conflict on every write (polluting the conflict
  metric, the §4 headline) and double-count trace events.
- Fix in `run_phase2` (resume semantics, no per-run behavior change):
  a run dir with `metrics.json` is skipped and its metrics reloaded
  into the summary (metrics.json is written only on run completion,
  so it is a valid completion sentinel); a run dir without it is
  wiped before the rerun. One re-invocation of the full command now
  completes the protocol and writes the full 12-run summary.
  Completed runs are never silently rerun; delete a run dir to force.
- Verified offline (mock model): completed rep skipped, partial rep
  wiped and rerun with zero stale conflicts/trace lines, summary
  rebuilt over all reps.
- Server durability fix, separate from code: `loginctl enable-linger
  tpark45` so detached jobs survive disconnects.

Decision rule for the runs (spec §0.5): PASS = depth ≥ 3 convergence
on d03 in ≥ 1/3 reps with a sensible shape AND no regression on d01.
Rail-terminated non-convergence on d04 is an expected, recorded
finding (motivates Appendix A), not a failure to engineer around.

## Run results (12/12) and decision — E0-min: PASS

Runs 2026-07-10, `results/e0/` (first invocation killed mid-d03_r2 by
session teardown; resumed per build iteration 1 — d03_r2 was wiped and
rerun clean, 7 completed runs reused with zero LLM calls).

- Convergence 12/12, all natural terminations, zero rail hits (max
  observed 96/120 calls, d02_r1). Schema agreement 271/271 (100%).
  Zero conflicts, zero trigger errors, zero ready-but-unfired.
- **§0.5 PASS**: d03_r2 reached depth 3 with the task's natural
  levels — root → 4 chapters → (research, draft) → research
  subtopics (vector DB / KG / RAG), root's gated self_role producing
  root/glossary + root/final_guide (the task's "unified glossary and
  final assembly pass"). d01 no regression: 3/3 converged; r1/r2
  reproduce the probe-era 5-agent shape.
- Depth by task: d01 1,1,2 · d02 8,4,4 · d03 2,3,2 · d04 2,2,2.
  The fixed-tier depth cap is gone; depth now varies with the task.
- **Participation rule results**: self_role distribution 62/62 gated
  integrator, 0 parallel — parent-as-integrator is not just dominant
  but universal. Interface self-fulfillment 93/93 (100%): the v5
  delegation exception was never used once. DEFER: 0 uses in 12 runs.
- **Finding — depth is unlocked but unbalanced (d02_r1)**: depth 8 /
  48 agents, all sensible locally, globally disproportionate — one
  YouTube-creator-incentive micro-branch got 5 extra levels
  (root.4.2.3.2.2.2.2.*) while market analysis got 1, and its ~2–4k-
  char leaf artifacts barely surface in the 4.4k-char
  root/business_plan. No cost signal → local judgment recurses on
  minutiae. Not rail-dependence (terminated naturally), so Appendix A
  stays deferred per §0.5, but this is its motivating evidence:
  proportionality, not termination, is what budget machinery buys.
- **Finding — temp-0 replication is not deterministic**: d02 reps
  diverge wildly in shape (depth 8 vs 4, 48 vs 21 agents) from
  identical initial contexts — vLLM batching nondeterminism amplified
  by the recursive structure. d04 was byte-identical across reps.
  The probe's "deterministic replication" caveat needs restating:
  variance exists and is structure-amplified.
- Minor: 3 worker schema mismatches (d01_r3 only) — agents declared
  archive paths (root.2/backend_code.tar.gz etc.) and the text worker
  returned empty outputs for them; fallback values kept the run
  converging. Same phase-grammar drift noted in PROBE_REPORT §3.
- Conflicts remain zero even at depth 8 / 48 agents (now 36 runs
  total across probe+E0) — theory §4 threshold pushed further out;
  Figure-1's conflict-induction design is now the only live path to
  exercising it.

Next per spec order of work: Figure-1 / E2 (f01 construction + tree
baseline). E1's deep end (L3/L4) is unlocked by this PASS.
