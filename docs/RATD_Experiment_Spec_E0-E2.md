# RATD Experiment Specification — E0, Figure-1/E2, E1
## v1.0 — Ground truth for automated build

**Parent documents:** `RATD_Theory.md` v1.1 (claims and evidence tags), `RATD_Probe_Spec.md` (probe design, inherited conventions), `PROBE_REPORT.md` (baseline results and known measurement pitfalls).
**Prerequisite state:** probe closed Q1/Q2/Q3 YES; runtime `src/phase2.py` and `prompts/harness_v5.md` are the working baseline.
**Goal:** answer three questions, in priority order, with the minimum build:

- **E0-min:** With budget machinery removed entirely (rails as the only bound), does the system reach depth ≥ 3 convergence with sensible graph shapes? (Gates E2 and E4; dissolves the fixed-tier depth cap. Budget-scheme *comparison* is deferred to the optimization phase — Appendix A.)
- **Figure-1 / E2:** Construct the minimal task where the emergent graph does something a pre-planned tree structurally cannot, and demonstrate it. (Shapes the paper's pitch; theory open question #1.)
- **E1:** The crossover curve — RATD vs. a replanning central planner as task size/depth grows. (Headline experiment; theory §3's falsifiable prediction.)

**Kill-order:** E0-min first. If depth ≥ 3 convergence is unreachable even with no budget constraint at all, E1's deep end and E4 are unreachable — STOP after E0-min, write `results/e0/FAILURE_REPORT.md`, and re-scope. Figure-1 does not depend on depth and may proceed regardless of E0-min's outcome.

**Inherited hard rules (from the probe, unchanged):**
1. Never overwrite harness or spec versions; log every iteration.
2. All quantitative safety enforced in code, never trusted from model output.
3. Exactly-once trigger firing.
4. Maintain `results/THEORY_VS_REALITY.md` continuously; it remains the highest-value deliverable.
5. Temperature 0; model + version logged per run.
6. **New (from PROBE_REPORT §6 lessons):** any agreement/coordination metric must be reported alongside its fallback count (write-to-declared-path events), and all cross-branch-read figures are unique (agent, path) pairs — never raw events.

**Model config:** E0-min removes budget from the model's interface entirely (no arithmetic anywhere), so the default remains local `qwen3.6` via the vLLM endpoint. E1's planner baseline and the LLM judge should be run on the same model as the RATD agents to keep the comparison fair; a stronger-model replication is optional and out of scope for this spec.

**Global safety rails (all experiments):** max 120 LLM calls per run (raised from 60 — depth-3 graphs are larger), max depth 8, wall-clock 40 min. Hitting a rail is a recorded finding.

---

# E0-min — Unlock Depth (proof of concept, no budget machinery)

## 0.1 Motivation and stance

The probe's fixed tiers guaranteed termination but structurally capped depth at 2 (20 → 8 → 2 → cannot spawn). For proof of concept, budget is removed from the system entirely rather than redesigned: the existing safety rails (max LLM calls) are already a strictly decreasing, code-enforced finite bound, so the §6 termination guarantee survives with zero budget machinery. What is given up — spawn economics, branch isolation, starvation protection — is optimization, deferred to Appendix A. Theory §6's conservation/allocation split stands unchanged; E0-min simply instantiates conservation at the coarsest possible grain (one global call counter) and defers allocation entirely.

## 0.2 Configuration delta (small; target ≤ ~60 lines on `phase2.py`)

- **Schema:** drop `"budget"` from the subtask spec. No weights, no pool line, no allocation of any kind in the model's interface.
- **Participation rule (new, first-class):** a SPAWN document must include a `"self_role"` object — `{goal, outputs, condition}` — declaring the job the spawning agent itself takes. The role is unrestricted: one parallel share of the work (condition null), the gated integrator (condition over children's outputs — expected common case), or an observer-style review job; but it must exist and must declare ≥ 1 output. Runtime: after registering the children, the parent is re-enqueued (condition null) or trigger-registered (condition set) as a worker with the self_role task under its own task_id and namespace. Validator: SPAWN without a non-empty self_role is invalid. Rationale: no pure-router nodes (every agent contributes ΔD, not just ΔC — Cilk-style parent participation), spawn friction as implicit explosion resistance (NOT a bound — rails remain the bound), and when the parent takes the integrator role it writes its own owed interface paths itself, collapsing the common case of the v5 delegation exception. The delegation contract remains as fallback for parents taking non-integrator roles.
- **Harness:** fork `harness_v6.md` from v5; delete the Budget rule section wholesale, replace with two lines: "There is no spawn budget. Spawn only when decomposition genuinely serves the ROOT GOAL — spawning has real cost, and the run has a finite global call limit." Add the participation rule: "If you SPAWN, you must also take a job yourself, declared in self_role: one share of the parallel work, the integrating job gated on your children's outputs, or a review job. Spawning is not delegation of all work — you stay in the run." Everything else (interface contract, DEFER, judgment guidance) byte-identical to v5.
- **Runtime:** remove budget validation and clipping; remove the B<2 no-spawn rule (any agent may spawn). Rails become the only bound: max 120 LLM calls, max depth 8, wall-clock 40 min — all pre-existing, all code-enforced. Interface coverage check updated: self_role outputs count toward the parent's owed paths.
- **Context:** replace `REMAINING BUDGET: {B}` with `GLOBAL CALLS REMAINING: {n}` so agents can still route sensibly near exhaustion (this is information, not a constraint the model computes with).

## 0.3 Task set

Depth ≥ 3 must be plausibly demanded, not just permitted. Use `tasks/e0_tasks.json`:

- **d01 (t09 carryover):** full-stack todo app — known depth-2 shape; regression check that removing budget breaks nothing.
- **d02 (t15 carryover):** business plan — probe spec expected depth 3 here and never got it; with tiers gone, does it appear?
- **d03 (new, constructed deep):** "Write a 4-chapter technical field guide to LLM agent memory systems. Each chapter needs its own research, a draft, and a consistency edit; the book needs a unified glossary and a final assembly pass." — three natural levels (book → chapter → research/draft/edit) plus an integrator.
- **d04 (new, breadth stress):** "Produce localized launch kits (announcement post, FAQ, pricing page copy) for a product in 6 markets: US, KR, JP, DE, BR, IN; then a global consistency review." — wide fan-out; the over-spawn stress case now that nothing limits fan-out but judgment.

## 0.4 Protocol and metrics

- 4 tasks × 3 repetitions = 12 runs. Output to `results/e0/{task}_r{n}/` with the probe's trace/graph conventions.
- Metrics per run (extend `RunMetrics`): convergence; max depth; total spawns; termination source (`natural` / `rail`); rail-hit type if any; unique cross-branch read pairs; conflicts (deeper graphs are the first real test of theory §4's threshold reading — any conflict is a headline finding); **self_role distribution** (parallel share vs. gated integrator vs. other — is parent-as-integrator the dominant pattern as predicted?); **interface self-fulfillment rate** (fraction of owed paths written by the parent's own self_role vs. delegated — measures how far the participation rule collapses the v5 exception).
- **Theory feedback (queue for v1.2, do not edit theory mid-experiment):** the participation rule changes §1.2 (SPAWN becomes spawn-and-continue; the agent's step is no longer terminal on spawn) and interacts with §1.3 (parent-as-integrator makes interface delegation the fallback, not the rule) and §5 (the parent at the join point is a structural drift check). Log all three as THEORY_VS_REALITY entries with E0-min evidence attached.
- **Watch specifically:** how often termination depends on the call rail rather than natural completion. Rail-terminated non-convergence on d04 is the expected failure mode of the no-budget design and is a *recorded finding motivating Appendix A*, not something to engineer around in this phase.

## 0.5 Decision rule

- **PASS = depth ≥ 3 convergence on d03 in ≥ 1 of 3 repetitions with a sensible shape** (qualitative: does the level-3 structure correspond to the task's natural levels?) AND no regression on d01.
- Rail-dependent termination on some runs does not fail E0-min (it's the known cost of no-budget); systematic rail-dependence on *all* deep tasks does — that means unconstrained judgment over-spawns faster than it converges, and Appendix A gets promoted from optimization to prerequisite.
- If depth ≥ 3 never appears even unconstrained: the ceiling is model judgment, not economics — STOP, failure report, re-scope E1 to shallow tasks only and mark E4 blocked.

---

# FIGURE-1 / E2 — The Emergent-DAG Demonstration

## 1.1 Claim under test

Theory §3 corollary: memory-first lookup lets the emergent structure become a DAG whose subtrees merge through shared memory — something a pre-planned tree structurally cannot produce. Prediction: pre-planned tree ⇒ 0 cross-links; RATD ⇒ > 0, and the cross-link must be **decisive** (output is wrong or incomplete without it), not incidental.

The DEFER read-grant mechanism (theory §4.5) is the construction primitive: engineer a dependency that is (a) cross-branch, (b) only discoverable mid-execution, and (c) not expressible as a parent-declared interface at spawn time — which simultaneously makes this the conflict-induction probe for §4's tension (E5' overlap: if the dependency is discovered *too late*, both branches write divergent versions and the conflict log finally fires; either outcome is a finding).

## 1.2 The Figure-1 task (f01) — construct, then iterate

Starting candidate (iterate up to 3 versions, `tasks/figure1_v*.json`, never overwrite):

> **f01:** "Produce a bilingual (EN/KR) API style guide for a payments platform, in two parts developed by separate teams: Part A defines the canonical terminology and naming conventions (endpoint nouns, error-code vocabulary, casing rules); Part B writes the worked integration tutorial with code samples. The tutorial MUST use the canonical terminology exactly — any term drift between parts is a defect. Part A's conventions are not fixed in advance; they emerge from Part A's research."

Why this shape: the root will plausibly spawn A and B in parallel (both look independent at spawn time — the dependency is inside B's *content*, not its interface). B's tutorial agent discovers mid-task that it needs A's terminology, which lives in a sibling branch it is namespace-blind to. Correct resolutions available to it: DEFER on `root.1/terminology` (wake grant gives visibility — the §4.5 mechanism, the ideal Figure-1 trace) or a cross-branch read if visibility rules already expose it. Failure modes that are also findings: B invents its own terminology (drift defect, detectable by a string-overlap check between the tutorial and the glossary) or both branches write competing glossaries (first real conflict).

## 1.3 Baseline and measurement

- **Baseline:** one-shot pre-planned tree — a single planner call decomposes f01 into a fixed task tree with fixed conditions; the same worker prompt executes each leaf; no DEFER, no cross-branch visibility. This is ~50 lines reusing the worker path of `phase2.py`.
- **Runs:** RATD × 4 repetitions, baseline × 4, same model, E0-min configuration (no budget).
- **Metrics:** unique cross-branch (agent, path) pairs (predicted: baseline 0 by construction, RATD > 0); DEFER/wake cycles; terminology-consistency score (exact-match rate of glossary terms appearing in the tutorial — the decisiveness measure); conflicts.
- **Success = the figure:** RATD graph rendering showing the cross-branch edge, side-by-side with the baseline tree, plus the consistency-score gap. If RATD's consistency ≤ baseline's, the cross-link was not decisive — iterate the task (make the terminology more arbitrary so invention can't accidentally match) rather than the harness.

Output: `results/figure1/{ratd|baseline}/r{n}/`, comparison in `results/figure1/FIGURE1.md`.

---

# E1 — The Crossover Curve

## 2.1 Claim under test

Theory §3 (the core theorem, `[UNTESTED]`): a replanning central planner pays O(n) context per decision and degrades as state grows; RATD pays O(1). Prediction: planner ≥ RATD on small tasks (RATD pays coordination overhead); gap reverses and widens with size/depth.

## 2.2 Baseline: replanning central planner (the only genuinely new build)

`src/planner_baseline.py` (~200 lines):

- One planner loop: after every completed task, ONE planner LLM call receives the ROOT GOAL + the **entire** accumulated state (all done entries, full values, truncated only by the model's context limit — truncation events are themselves a measurement: the degradation mechanism made visible) + the remaining plan, and emits the updated remaining plan as strict JSON (same task/output/condition schema as RATD subtasks, minus capsules).
- Same worker prompt executes leaves; same memory D; no triggers (the planner is the scheduler); same rails.
- Log per planner call: context tokens in (the O(n) curve's y-axis), plan-churn (tasks added/removed/changed vs. previous plan).

## 2.3 Task ladder

Four sizes, same domain family so the judge rubric is stable (`tasks/e1_ladder.json`):

- **L1 (small):** single-artifact task, no decomposition needed (e.g., probe t17-class). Expect planner wins or ties.
- **L2 (moderate):** probe t06-class (3 parallel + synthesis, ~5 leaves).
- **L3 (deep):** E0's d03-class (depth 3, ~12–15 leaves).
- **L4 (deep+discovery):** d03 + a Figure-1-style mid-execution dependency, the regime where replanning must actually replan. Only runnable if E0-min passed.

3 repetitions per system per level = 24 runs.

## 2.4 Metrics and the figure

- **Quality:** LLM-judge score of the root artifact against a per-level rubric (fixed judge prompt, judge model = agent model, rubric written before any runs and versioned; judge sees system-blind outputs in random order).
- **Context cost:** mean context tokens per decision — planner calls for the baseline vs. routing calls for RATD. Prediction: flat for RATD across L1→L4; growing for the planner. This is the one-figure thesis proof if it appears (quality crossover on the same x-axis).
- **Secondary:** total tokens, wall time, convergence, conflicts, plan-churn (baseline), truncation events (baseline).
- Output: `results/e1/summary.md` + `results/e1/crossover.png` (two panels: quality vs. level, context/decision vs. level).

## 2.5 Honesty constraints (pre-registered)

- If the planner wins at every level, that is the finding; the theory's prediction is falsified at this scale and THEORY_VS_REALITY records it. Do not tune RATD harnesses per-level to chase the curve; one harness for all levels, frozen before L1 runs.
- The judge is the weakest link: report inter-repetition judge variance; if variance swamps the system gap, the quality axis is inconclusive and only the context-cost axis is claimable.
- n=3 per cell is feasibility-scale evidence, not significance; state this in the summary.

---

# Order of work

1. E0-min: `harness_v6.md` fork + budget-removal delta on `phase2.py` (≤ ~40 lines), run 12, decide per §0.5. Update THEORY_VS_REALITY (§6 instantiation, rail-dependence findings).
2. Figure-1: construct f01, build the tree baseline, run 8, iterate the task up to 3 versions. Produce FIGURE1.md.
3. E1: build `planner_baseline.py`, write + freeze rubrics, run the 24-run ladder, produce the crossover figure.
4. Final report `EXPERIMENT_REPORT.md`: E0 decision, Figure-1 verdict, E1 curve — each with evidence pointers, deviations declared, and the fallback/unique-pair reporting rules of the probe applied throughout.

# Deliverables checklist

```
prompts/harness_v6.md                 (E0-min, forked from v5, budget section removed)
tasks/e0_tasks.json                   (d01–d04)
tasks/figure1_v*.json                 (f01 iterations, never overwritten)
tasks/e1_ladder.json                  (L1–L4)
src/phase2.py                         (E0-min delta: budget machinery removed)
src/planner_baseline.py               (E1 baseline)
prompts/judge_v1.md + rubrics/        (frozen before E1 runs)
results/e0/{task}_r{n}/ + results/e0/summary.md
results/figure1/ + results/figure1/FIGURE1.md
results/e1/ + results/e1/summary.md + crossover.png
results/THEORY_VS_REALITY.md          (continuous)
EXPERIMENT_REPORT.md
```

---

# Appendix A — Deferred: budget-scheme comparison (optimization phase)

Not to be built now. Preserved so the design work isn't lost and so E0-min's failure modes have a named successor. If E0-min shows systematic rail-dependent non-convergence (unconstrained judgment over-spawns), promote this appendix to a prerequisite; otherwise it runs after E1, if at all.

Three candidate schemes, all keeping arithmetic out of the model (conservation structural, allocation semantic — theory §6 split):

- **A. Global pool:** runtime counter debited 1 per accepted spawn; SPAWN rejected when pool < k; context shows pool remaining. Zero pre-estimation, maximal autonomy; exposed to starvation (greedy early branch drains the pool). Termination: pool is strictly decreasing.
- **B. Weighted subdivision:** model emits relative `weight` 1–10 per child; runtime computes `budget_i = floor((B − k) × w_i / Σw)`. Conservation by construction; adds size-signaling and branch isolation at the cost of implicit size prediction. Risk to measure: flat weights starve deep children.
- **C. Pool + per-branch semaphore:** Arm A plus a renewable per-agent cap on *direct live child subtrees* (live = spawned until all interface paths done and no pending descendants); excess spawns held FIFO and activated as capacity returns, mechanically. Per-branch by construction (grandchildren limited only by their own parent's cap). **The semaphore is a concurrency bound, not a termination mechanism** — renewable capacity alone permits unbounded total spawns; the pool underneath provides termination. Purpose: starvation isolation and frontier-width control.

Comparison protocol when promoted: 3 arms × d01–d04 × 2 reps; decision = arm(s) achieving depth ≥ 3 on d03 with sensible shape; prefer A over C unless A shows starvation on d04; metrics as E0-min plus starvation events (A/C), sem_hold/release (C), weight entropy (B). Findings feed the paper's "economic constraints on recursive spawning" subsection either way.
