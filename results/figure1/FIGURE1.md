# Figure-1 / E2 — Verdict

**Claim under test** (spec §1.1, theory §3 corollary): memory-first
lookup lets RATD grow a DAG whose subtrees merge through shared
memory — a decisive cross-branch edge a pre-planned tree structurally
cannot produce.

**Verdict: the mechanism is demonstrated; decisiveness is refuted at
this scale.** The DEFER read-grant grew organic cross-branch edges in
exactly 1 of 12 RATD runs across three task versions, and that run
produced the *worst* output of its cohort. Where the dependency was
nameable at spawn time — 11 of 12 runs — local routing planned it,
and planned RATD coordination beat the one-shot tree. The emergent
channel's boundary is address nameability: you can only defer on a
path you can name.

## The three-way result (task v3, branch-aggregated scoring)

| Configuration | Runs | Terminology consistency | Survey→migration delivery |
|---|---|---|---|
| RATD, dependency planned + survey promoted to interface | r1 r2 r3 | **94.2–96.0%** | 96–100% (53/55, 59/59, 61/64) |
| One-shot pre-planned tree (baseline) | 4 | 72.2–90.8% | — (planner also planned a survey task) |
| RATD, emergent defer/wake edges (survey not promoted) | r4 | **49.5%** | 51% (27/53) |

Means (RATD 83.6% vs baseline 83.0%) are a tie and are the wrong
summary — the split by mechanism above is the result. Temp-0
clustering caveat applies throughout (effective n per cell is small).

## The exhibit trace (v3 r4 — the mechanism works)

Root assigned Part A only `root.1/canonical_standard` (no survey
interface — the one run where root did not make the dependency
statable). Part B spawned two tutorial writers (EN/KR) with null
conditions; both started, found no standard in visible memory, and
DEFERred naming `done("root.1/canonical_standard")`; both wake
triggers fired, the read grant exposed exactly the named entry, and
both wrote their tutorials. Two cross-branch edges authored at depth
2, mid-execution, by agents that did not exist when root planned —
structurally impossible for the one-shot tree. Side-by-side:
`results/figure1_v3/ratd/f01_r4/graph.png` vs
`results/figure1_v3/baseline/f01_r1/graph.png`.

Root's self_role in this run was `root/consistency_report` — the
first observed review-job self_role (every prior spawner chose gated
integrator).

## Why the emergent run lost

The task's engineered unforeseeable dependency — migration notes need
the LEGACY names, which live only in Part A's internal survey — was
never resolvable by DEFER: the survey's address
(`root.1.1/legacy_survey`) is not nameable from Part B's context.
r4's writers deferred on the address they *could* name (the
standard), wrote migration notes from 51% survey coverage, and the
run scored 49.5%. In r1/r2/r3, root generalized from the task text
and promoted the survey to a declared interface at spawn
(`root.1/legacy_survey`), making it plannable — delivery 96–100%,
consistency 94–96%.

**Boundary statement for the theory:** the DEFER read-grant resolves
mid-execution *timing* uncertainty over nameable addresses; it cannot
resolve *address* uncertainty. Genuinely unforeseeable dependencies
require either interface promotion ahead of need (which is planning,
and is what competent local routing actually does) or a memory-search
primitive the runtime does not have. Theory §3's corollary should be
scoped accordingly.

## History and honesty notes

- v1: task text stated the dependency → root planned it 4/4; scoring
  was confounded (child-artifact denominators; 1000-char worker
  truncation severed payloads — "reads are grants, not delivery").
  Both fixed, symmetric, before v2.
- v2: audit-property phrasing → root still planned it 4/4; RATD led
  53.9% vs 33.0% but effective n≈2 per arm (temp-0 clustering),
  unclaimable.
- v3: forced Part-B decomposition + unnameable survey address →
  results above. Scoring fix (branch aggregation for the tutorial
  side) was needed because B's interface artifact can be a stub over
  real child content; v1/v2 scores unchanged by the fix (verified).
- Conflicts: **zero in all 12 Figure-1 RATD runs** (44 runs
  cumulative across probe+E0+Figure-1). Even duplicate survey
  artifacts landed at distinct namespaced paths. The §4
  conflict-induction hope of this experiment also came up empty.
- All scores: `results/figure1_v3/FIGURE1_scores_branch.json` (v3),
  `results/figure1_v2/FIGURE1_scores.json` (v2),
  `results/figure1/FIGURE1_scores{,_interface_metric}.json` (v1).

## What the paper's Figure 1 should be instead

The defensible figure from these 12 runs is not "emergent beats
planned" — it is the r4 trace as the *mechanism* panel (DEFER →
wake → read-grant → write, with the two dashed cross-branch edges)
next to the *boundary* result: coordination quality by mechanism
(promotion 94–96% / tree 72–91% / unpromoted-emergent 49.5%). The
emergent-DAG advantage, if it exists, lives where addresses cannot be
known ahead of time AND a retrieval primitive exists — an explicit
next experiment, not a claim of this one.
