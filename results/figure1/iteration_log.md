# Figure-1 / E2 Iteration Log

Spec: `RATD_Experiment_Spec_E0-E2.md` §1.1–1.3. Baseline state:
E0-min PASS (`results/e0/`), runtime = post-E0 `src/phase2.py` +
`prompts/harness_v6.md` (no budget, participation rule).

## Build iteration 0 (pre-run)

- `tasks/figure1_v1.json` — f01 exactly as the spec's starting
  candidate (bilingual EN/KR payments API style guide; Part A
  terminology emerges from research; Part B tutorial must use it
  exactly). Iterations, if needed, go to `figure1_v2.json` etc.,
  never overwriting (inherited rule 1).
- `src/tree_baseline.py` — one-shot pre-planned tree baseline:
  single planner call emits the entire fixed task tree (same
  task/output/condition schema as RATD subtasks, no capsules), with
  the same 3-attempt validation-repair loop as RATD routing; the
  RATD runtime's `WORKER_PROMPT` executes each task when its
  condition is true; no DEFER, no re-decomposition, no new edges
  after t=0. Rails matched (120 calls / 40 min). Resume semantics
  matched (metrics.json sentinel). Stall (unsatisfiable plan
  conditions) is recorded, not repaired.
  - **Declared design choice:** baseline workers get the SAME
    visibility rule as RATD workers (ancestor namespaces +
    condition-named refs). The spec's "no cross-branch visibility"
    is interpreted as "no *emergent* cross-branch structure":
    planner-written sequential conditions still grant reads, so the
    comparison isolates frozen-vs-emergent structure rather than
    strawmanning the baseline's read permissions. Baseline planned
    cross-branch reads are reported separately from the emergent
    count (which is 0 by construction for the baseline).
- `src/figure1_score.py` — per-run scoring:
  - Terminology-consistency (the decisiveness measure): identifier-
    like terms (snake_case, SCREAMING_CASE, camelCase, kebab-case,
    endpoint paths) extracted from Part-A terminology/glossary
    artifacts, matched verbatim in Part-B tutorial artifacts.
    Artifact detection is by key-name pattern, excludes the
    integrated `root/` deliverable, and is emitted in the output for
    audit; detection failure is flagged, never silently scored.
  - **Emergent cross edge (the Figure-1 quantity), defined:** a
    dependency edge authored mid-run by a non-root agent — spawn or
    self_role conditions referencing paths outside the author's own
    subtree, or DEFER wake conditions referencing paths outside the
    deferring agent's branch/ancestry. Root-authored conditions are
    NOT emergent (a one-shot planner could write those too — and the
    f01 task text telegraphs the A→B dependency, so root probably
    will). Unique (consumer, ref) pairs. This is deliberately
    stricter than the raw cross-branch-read metric, which is also
    reported (unique pairs, per inherited rule 6).
  - Plus defer/wake cycles and convergence/calls passthrough.
- Verified offline with scripted mocks (no network): baseline planner
  repair on an invalid plan, condition-gated execution order, planned
  cross-pair counting (3 pairs on the 3-task mock plan), scorer
  consistency 5/6 on a constructed glossary/tutorial pair with one
  term missing by design, emergent detection counting the non-root
  spawn condition + defer wake (deduped to 1 pair) while scoring the
  root-authored baseline edges as 0.

Prediction registered before the runs (spec 1.1): baseline emergent
edges = 0 by construction; RATD > 0 via DEFER read-grant or deep
spawn conditions, and decisive (RATD consistency > baseline).
Registered risks: root may plan the A→B dependency at spawn time
(emergent count 0 at root level — iterate the task toward v2 with the
dependency less visible in the task text); both branches may write
competing glossaries (first real conflict — a headline finding, not a
failure); B may invent terminology (drift defect, visible as low
consistency).

## Protocol

- RATD × 4: `python3 -m src.phase2 --harness prompts/harness_v6.md
  --tasks tasks/figure1_v1.json --out-dir results/figure1/ratd
  --repetitions 4`
- Baseline × 4: `python3 -m src.tree_baseline --tasks
  tasks/figure1_v1.json --out-dir results/figure1/baseline
  --repetitions 4`
- Score: `python3 -m src.figure1_score` (writes
  `results/figure1/FIGURE1_scores.json`, prints the comparison table)
- Then: `FIGURE1.md` with the side-by-side graphs (RATD graph.png vs
  baseline graph.png) and the consistency gap.

## Run 1 (task v1) — no emergent edges; measurement confounded; NOT a decisiveness verdict

Runs 2026-07-10, 8/8 converged (RATD 4, baseline 4), zero conflicts,
zero rails, RATD schema agreement 22/22.

- **Registered risk #1 realized**: root pre-planned the A→B edge in
  4/4 RATD runs (root.2 gated on root.1's terminology interface).
  Zero DEFERs, zero emergent cross edges. The v1 task text's "MUST
  use the canonical terminology" made the dependency plannable at
  spawn time; the graphs RATD grew are trees a planner could write.
- Headline consistency as first scored (RATD 20.8% vs baseline
  22.0%) is **not a valid decisiveness verdict**; two measurement
  defects dominated it:
  1. **Scoring asymmetry**: the term denominator included Part-A's
     *child* artifacts (root.1.1/…, root.1.2/…) that the tutorial
     author could never see - penalizing exactly the system that
     decomposes more deeply. Fixed: `split_parts` now scores
     interface-level (depth-1) artifacts only, both systems alike.
     Rescoring v1 under the fixed metric flips the sign (RATD 30.3%
     vs baseline 22.0%, `FIGURE1_scores_interface_metric.json`) -
     i.e., the v1 "baseline wins" was metric-sensitive; neither
     direction is claimable from v1.
  2. **Worker context truncation severed the payload**: worker
     memory values were sliced to 1000 chars. RATD's bimodal spread
     (0%, 4.8% vs 39.3%, 39.3%) is fully explained: in r1/r3 the
     terminology doc (~2830 chars) led with ~1000 chars of prose -
     ZERO identifier terms survived into the tutorial author's view
     (0/0 extractable); in r2/r4 terms led the doc and the tutorial
     used 11 of the 12-14 visible ones (79-92% of what it saw). The
     model was faithful to what it read in every run; the runtime
     logged the cross-branch read as successful while delivering
     none of the vocabulary. Fixed symmetrically: worker memory
     slice 1000 → 4000 chars in both `phase2.py` and
     `tree_baseline.py`. Theory implication logged in
     THEORY_VS_REALITY ("reads are grants, not delivery").
- Baseline behaved as designed: 4 planner+worker calls/run, planned
  tree with planned cross-branch reads, emergent 0 by construction.

## Iteration → task v2 + measurement fixes (pre-registered before run 2)

- `tasks/figure1_v2.json`: terminology made idiosyncratic house
  style ("Cheonma", discovered from legacy code, not industry
  defaults) so invention cannot accidentally match - the spec's
  decisiveness lever; the consistency requirement restated as a
  global audit property of the final deliverable rather than a
  Part-B instruction, weakening the spawn-time signal that let root
  pre-plan the edge. If root still plans the edge in v2, that is
  recorded as evidence that statable dependencies get planned and
  the emergent-DAG advantage requires genuinely unforeseeable
  dependencies (v3 would need mid-execution dependency injection).
- Declared: run 2 changes task wording AND the truncation limit
  together (both systems symmetrically). v1↔v2 deltas are therefore
  not attributable to either alone; the decisiveness comparison is
  within-run-2, RATD-vs-baseline.
- Run 2 protocol: same as run 1 with `--tasks tasks/figure1_v2.json`
  and out-dirs `results/figure1_v2/{ratd,baseline}`, then
  `python3 -m src.figure1_score --ratd-dir results/figure1_v2/ratd
  --baseline-dir results/figure1_v2/baseline --out
  results/figure1_v2/FIGURE1_scores.json`.
