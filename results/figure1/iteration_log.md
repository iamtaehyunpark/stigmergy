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
