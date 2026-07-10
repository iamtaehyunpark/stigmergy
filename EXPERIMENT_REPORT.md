# RATD Experiment Report — E0, Figure-1/E2, E1

**Date:** 2026-07-10
**Scope:** `RATD_Experiment_Spec_E0-E2.md` in full (E0-min, Figure-1/E2, E1)
**Baseline:** probe-final runtime (`PROBE_REPORT.md`, Q1–Q3 all YES)
**Model:** local `qwen3.6` (vLLM, temp 0, JSON-constrained) for every
agent, planner, worker, and judge — no stronger model anywhere.

**Verdicts:**
- **E0-min: PASS.** Budget machinery removed entirely; rails alone
  preserve termination (12/12 natural). Depth ≥ 3 with task-natural
  shape on d03; no d01 regression.
- **Figure-1/E2: mechanism demonstrated, decisiveness refuted.** The
  DEFER→wake→read-grant cross-branch edge exists in the wild (exhibit
  trace, v3 r4) but planned coordination beat it; the boundary is
  address nameability.
- **E1: theory §3's cost claim CONFIRMED** — RATD context/decision is
  flat (7.2k→8.4k chars, L1→L4) while the replanning planner grows
  O(n) (4.6k→41.6k, truncation events at L4). Quality axis: planner
  wins shallow; at depth both systems hit the same
  architecture-independent output-capacity wall, so per the
  pre-registered rule only the cost axis is claimable there.

**Meta-result across 68 runs:** zero write conflicts, zero trigger
errors, 100% schema agreement over 300+ condition references, and
every failure that occurred was diagnosed to a specific, fixable
mechanism with its rule-level remedy identified.

---

## 1. E0-min — Unlock depth (12 runs)

Budget removed from schema/validator/runtime/context; rails (120
calls / depth 8 / 40 min) the only bound; participation rule added
(SPAWN requires a `self_role` the spawner executes itself).

| Task | Convergence | Depth | Notes |
|---|---|---|---|
| d01 (t09 regression) | 3/3 | 1,1,2 | no regression |
| d02 (business plan) | 3/3 | **8,4,4** | depth unlocked; disproportionate deep branch |
| d03 (field guide) | 3/3 | 2,**3**,2 | §0.5 PASS: depth 3, task-natural levels |
| d04 (breadth stress) | 3/3 | 2,2,2 | 25 agents, identical reps, no over-spawn |

All 12 natural terminations; zero rail hits (max 96/120 calls).
Participation rule: 69/69 SPAWNs carried a valid self_role,
first-try, all gated-integrator; interface self-fulfillment 93/93 —
the v5 delegation exception went unused. DEFER count: 0 (the gated
self_role absorbs wait-for-siblings).

Findings: (1) budget buys *proportionality*, not termination — d02_r1
grew 5 extra levels of YouTube-creator-incentive minutiae while
market analysis got one (Appendix A's motivating evidence; still
deferred, since termination held); (2) temp-0 replication is not
deterministic — d02 reps diverged depth 8 vs 4 from identical
contexts (vLLM batching noise, structure-amplified); shape metrics
are distributions.

## 2. Figure-1 / E2 — Emergent-DAG demonstration (24 runs, 3 task versions)

Full verdict: `results/figure1/FIGURE1.md`. One-shot pre-planned-tree
baseline built (`src/tree_baseline.py`); consistency scored by
verbatim terminology overlap between independently-produced branches.

- **v1:** root planned the A→B edge 4/4 (task text stated it). Two
  measurement defects found and fixed symmetrically: term-denominator
  asymmetry, and the 1000-char worker-context slice that silently
  severed a 100%-agreed channel (**"reads are grants, not delivery"**).
- **v2:** root still planned it 4/4. RATD led on consistency but
  temp-0 clustering left effective n≈2/arm — unclaimable.
- **v3** (B forced to decompose; decisive data at an unnameable
  address): emergent defer/wake edges appeared in r4 — the exhibit
  trace — but scored worst (49.5%); runs where root *promoted* the
  survey to a declared interface scored 94–96%, beating the baseline
  tree (72–91%). Survey-content delivery: 96–100% with promotion vs
  51% without.

**Boundary statement:** DEFER resolves *timing* uncertainty over
nameable addresses; it cannot resolve *address* uncertainty.
Statable dependencies get planned (and that coordination wins);
unforeseeable ones need interface promotion (= planning) or a
memory-search primitive the runtime lacks. Theory §3's corollary is
scoped accordingly; the paper's Figure 1 pairs the mechanism trace
with the coordination-quality-by-mechanism bars.

## 3. E1 — Crossover curve (24 runs + blind judging)

Replanning planner baseline (`src/planner_baseline.py`): one planner
call per completed task, full accumulated state (60k-char budget,
truncation logged), plan churn measured. Judge and rubrics frozen
before the first run; system-blind; per-run scores published.

| Level | System | Conv | Judge overall (per-run) | Ctx chars/decision |
|---|---|---|---|---|
| L1 | RATD | 3/3 | 9, 9, 9 | 7,248 |
| L1 | planner | 3/3 | 10, 9, 10 | 4,605 |
| L2 | RATD | 3/3 | 9, 9, 9 | 7,283 |
| L2 | planner | 3/3 | 10, 10, 10 | 5,505 |
| L3 | RATD | 1/3 | 1, 1, 1 | 7,638 |
| L3 | planner | 3/3 | 1, 9, 1 | 30,472 |
| L4 | RATD | 3/3 | 5, 5, 1 | 8,176 |
| L4 | planner | 3/3 | 7, 1, 1 | 41,581 |

Curves: `results/e1/crossover.png`. The cost panel is the theorem:
flat vs 9× growth, with L4 planner calls hitting the state budget
(4–5 truncation events/run) and churn rising to ~20 plan edits/run.

Quality reading, honestly: planner better shallow (as predicted);
at depth the pre-registered variance rule triggers — within-cell sd
up to 4.6 — because of a shared failure, not a coordination gap:
**five converged runs (1 RATD, 4 planner) shipped a 15-char
`{"outputs": []}` stub** as the final artifact. Verified mechanism:
single-call assembly of a book-sized artifact exceeds the 4k-token
output cap (18.5k chars emitted, unclosed JSON, fallback). The judge
correctly scored stubs 1. Deep-task quality currently measures
output-capacity roulette, in both architectures equally.

RATD's two non-convergences are the report's most valuable organic
failure: **blind defer** — a condition-null glossary agent, sighted
on nothing, deferred on guessed addresses no agent ever declared and
slept forever. The Figure-1 nameability boundary, occurring naturally.

## 4. Consolidated findings for the theory rewrite

1. §3 cost claim: **CONFIRMED** (flat vs O(n), degradation mechanism
   observed). §3 emergent-DAG corollary: **scoped** to unnameable
   addresses × retrieval-available — currently empty regime.
2. §4 conflicts: never fired — 68 runs, zero, including engineered
   induction. Needs a threshold statement, not an inevitability claim.
3. §4.5 DEFER: works as specified for nameable addresses; is a silent
   liveness hole for guessed ones (blind defer).
4. §6 budget: conservation structural (rails suffice for
   termination); allocation buys proportionality; small models cannot
   do the arithmetic regardless.
5. §1.2 SPAWN is spawn-and-continue (participation rule: universal,
   spontaneous adoption; kills interface orphaning by construction).
6. Delivery is coordination semantics: input side (context slice) and
   output side (token cap) both produced silent
   perfect-metrics/zero-content runs. Content-level metrics are
   mandatory; an audit Observer is the natural rule.

## 5. Design-choice menu for the improvement phase (user decision)

| Gap | Evidence | Cheapest rule | General fix |
|---|---|---|---|
| Blind defer | 2 organic E1 failures | validator: wake refs must be declared paths (+ list in repair feedback); dead-trigger warning | memory-search primitive |
| Assembly output cap | 5 stub artifacts, both systems | raise max_tokens; assembler writes per-section keys incrementally | chunked/streaming assembly mechanism |
| Proportionality | d02_r1 depth-8 minutiae | Appendix A arm A (global pool) | Appendix A comparison |
| Delivery audit | 2 silent channel failures | consistency-audit Observer rule | content-level metrics standard |

## 6. Deviations declared

- Figure-1 measurement evolved mid-experiment (scorer denominator,
  branch aggregation, worker slice 1000→4000): each change
  documented, applied symmetrically, prior results rescored with
  originals retained. v1↔v2 deltas confound task+truncation changes.
- E1 harness/rubrics frozen before L1 and never touched; the L3
  blind-defer failures therefore stand unpatched in the results.
- Units: context cost in characters (system+user, both systems
  identically), not tokens. n=3 per cell; temp-0 clustering reduces
  effective n (per-run values published everywhere).
- One process interruption (session teardown mid-E0) was recovered
  with resume semantics; `loginctl enable-linger` fixed the class.

## 7. Artifact index

| Artifact | Location |
|---|---|
| E0 runs + log | `results/e0/` |
| Figure-1 verdict | `results/figure1/FIGURE1.md` |
| Figure-1 runs (v1/v2/v3) | `results/figure1*/` |
| E1 runs, judge scores, curves | `results/e1/` (`summary.md`, `judge_scores.json`, `crossover.png`) |
| Theory-vs-reality log (continuous) | `results/THEORY_VS_REALITY.md` |
| Runtimes | `src/phase2.py`, `src/tree_baseline.py`, `src/planner_baseline.py`, `src/e1_judge.py`, `src/figure1_score.py` |
| Harnesses v1–v6, judge v1, rubrics | `prompts/`, `rubrics/` (never overwritten) |
