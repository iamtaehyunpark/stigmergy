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

Decision rule for the runs (spec §0.5): PASS = depth ≥ 3 convergence
on d03 in ≥ 1/3 reps with a sensible shape AND no regression on d01.
Rail-terminated non-convergence on d04 is an expected, recorded
finding (motivates Appendix A), not a failure to engineer around.
