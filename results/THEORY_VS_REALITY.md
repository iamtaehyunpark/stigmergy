# Theory vs Reality Log

## 2026-07-09 - API availability is an implementation precondition

- Assumption or gap: The probe specification states a default model and API path, but does not define credential handling or offline behavior.
- What actually happened: The local environment has no `ANTHROPIC_API_KEY`, no `OPENAI_API_KEY`, and no provider SDKs installed.
- Implication for `RATD_Theory.md`: The feasibility probe needs to separate architectural failure from execution-environment incompleteness. Missing credentials should gate empirical claims without counting as Q1 failure.

## 2026-07-09 - Local model execution replaces cloud API as default

- Assumption or gap: The initial scaffold assumed a cloud API provider would be the default execution path.
- What actually happened: The server already has `/data/tpark45/engramtrace-env`, `HF_HOME=/data/tpark45/hugginface`, and local VLLM endpoints. The Phase 1 runner now defaults to `RATD_PROVIDER=local`, model `qwen3.6`, and `http://127.0.0.1:8000/v1/chat/completions`.
- Implication for `RATD_Theory.md`: Phase 1 empirical claims should name the local model and endpoint used, because routing quality may differ materially from the original API-model assumption.

## 2026-07-09 - Phase 1 memory stub conflicts with one task premise

- Assumption or gap: Section 1.3 says all Phase 1 tasks use empty memory, while task `t04` says the buggy function is provided at `root/buggy_fn`.
- What actually happened: The task set is encoded exactly as specified and the context builder uses `(empty)` memory for every task.
- Implication for `RATD_Theory.md`: Routing judgment may be affected by declared-but-unavailable memory. If the model defers `t04`, that should be interpreted as a spec/harness artifact, not necessarily a routing failure.

## 2026-07-09 - Some Phase 1 scoring dimensions are only partly automatable

- Assumption or gap: The spec asks for automated scoring "where possible" plus manual notes, but decomposition sanity and capsule quality require judgment.
- What actually happened: The scorer implements conservative heuristics for schema, budget, namespace, condition references, decomposition shape, and capsule length/root-linkage. It sets `manual_override_flag` on action mismatches but does not count overrides as passes.
- Implication for `RATD_Theory.md`: Empirical claims should cite both the aggregate CSV and the manual review notes for borderline routing decisions, especially `t17` and `t20`.

## 2026-07-09 - Small model cannot do budget-allocation arithmetic single-shot

- Assumption or gap: The spec's budget rule (sum of child budgets <= B - k) assumes the model can perform the arithmetic while composing the action document.
- What actually happened: qwen3.6 at temperature 0 violated the sum constraint on 5/20 tasks even with worked examples in the prompt (harness_v2 single-shot: 15/20). Replacing free allocation with fixed patterns (v3: uniform; v4/v5: tiered with one deep slot) eliminated violations entirely, at the cost of removing the quantitative half of the allocation decision from the agent.
- Implication for `RATD_Theory.md`: Section 6's budget conservation is sound, but *allocation* is a capability assumption that small models fail. Either the runtime clips (spec 2.2 already allows this) or the harness supplies safe patterns; which subtask deserves depth remains a semantic judgment the model handles well. "Economic constraints on recursive spawning" deserves its own treatment.

## 2026-07-09 - Interface orphaning: recursion + namespace isolation + gating were jointly inconsistent

- Assumption or gap: The theory treats namespace isolation (section 4) and recursive decomposition (section 3) as independently sound; neither the spec nor the harness said who writes a child's parent-declared output path if that child spawns instead of executing.
- What actually happened: In harness_v4 runs, every deep run died the same way: a spawning agent writes no data itself, its children may not write outside their own namespaces, so the interface path the parent's triggers were gated on could never legally be produced (t15 both reps, t09_r2; the 5 missing schema agreements were exactly these paths).
- Implication for `RATD_Theory.md`: The iota capsule must carry an interface *contract*, not just context: parent-assigned output paths are delegable obligations, and inherited interface paths are the single principled exception to namespace discipline. Fixed in harness_v5 plus mechanical validator support; schema agreement returned to 100%.

## 2026-07-09 - DEFER was a silent drop: Delta-C semantics must cover all rule-authoring actions

- Assumption or gap: Theory section 1.3 defines the runtime as firing newly-true rules after every change, and section 1.2 says every agent step returns (Delta-D, Delta-C). The Phase 2 runtime implemented Delta-C for SPAWN conditions but DEFER only logged.
- What actually happened: A correctly-behaving agent (root.2.1 in t09, needing sibling-branch memory it could not see) deferred naming an already-done path and was silently dropped from the circuit; both t09 reps failed with root_outputs starved. Fixed by registering (wake_condition, same agent re-enqueued with condition = wake_condition): already-true wakes fire on the next trigger pass, and condition refs grant the woken agent visibility of exactly the memory it named. 6/6 convergence followed.
- Implication for `RATD_Theory.md`: Two lessons. (1) Every action that authors a rule is a Delta-C edit and must be installed in C - "fire newly-true rules" includes rules that are true at installation (the Petri-net analogue: adding an enabled transition must schedule it). (2) DEFER-then-wake doubles as the visibility mechanism for cross-branch dependencies: the wake condition is simultaneously a scheduling constraint and a read grant. That coupling was not in the theory and is worth stating.

## 2026-07-09 - Conflict-as-feedback (section 4) never fired: zero conflicts in 24 runs

- Assumption or gap: The theory argues misclassified-parallel conflicts are inevitable under bounded retrieval and are the mechanism that completes local routing.
- What actually happened: Across all Phase 2 runs (24 total over four iterations), zero write conflicts occurred. Namespace isolation plus explicit interface assignment prevented every WAW hazard at this scale.
- Implication for `RATD_Theory.md`: The necessity argument is untested, not falsified: 3-8 agents, depth <= 2, and parent-declared interfaces may simply be below the conflict threshold. The crossover/scale experiment must measure conflict rate as tasks grow; if it stays zero at depth 4-6 with wider fan-out, section 4 needs revisiting.
## 2026-07-10 - E0-min: SPAWN is spawn-and-continue; the terminal-step model of section 1.2 is wrong

- Assumption or gap: Theory section 1.2 models an agent's step as terminal - emit (Delta-D, Delta-C) and exit; a spawning agent contributes only Delta-C. The E0 participation rule (spec 0.2) forces every spawner to also declare a self_role job it executes itself.
- What actually happened: 12/12 E0 runs converged with the rule in force; validation rejected-and-repaired SPAWNs lacking self_role without any convergence cost. The self_role was the gated integrator in 69/69 cases (0 parallel shares, 0 review jobs).
- Implication for `RATD_Theory.md`: Section 1.2 should model SPAWN as spawn-and-continue: the agent's step returns (Delta-D, Delta-C) where Delta-D may be deferred behind a trigger the agent registers for itself. Every agent contributes data, not just rules - there are no pure-router nodes. This is also the cleanest statement of why interface orphaning (probe finding) cannot recur: the interface owner stays alive until its interface is written.

## 2026-07-10 - E0-min: parent-as-integrator is universal; interface delegation is dead code so far

- Assumption or gap: The v5 interface contract made delegation-to-a-subtask the normal way a spawning agent discharges its owed paths, with spec 0.2 predicting parent-as-integrator would become the common case under the participation rule.
- What actually happened: Stronger than predicted - interface self-fulfillment was 93/93 (100%) across all 12 runs. Every spawning agent kept its owed paths in its own self_role; the v5 delegation exception to namespace discipline was never exercised once. DEFER was also never used (0/12 runs) - the gated self_role absorbs the wait-for-siblings case that previously surfaced as mid-branch DEFERs.
- Implication for `RATD_Theory.md`: Section 1.3's interface contract should present self-fulfillment as the rule and delegation as an untested fallback. Note the measurement consequence: with integration pulled into parents, DEFER/wake and cross-branch reads (theory 4.5) nearly vanish from natural traces (cross-branch pairs: only d01's 4/run) - Figure-1 must engineer its cross-branch dependency deliberately, exactly as the spec anticipated.

## 2026-07-10 - E0-min: removing budget unlocks depth but not proportionality; termination held without it

- Assumption or gap: Theory section 6 ties safe recursion to budget conservation; E0-min bet that rails alone (120 calls, code-enforced) preserve termination, deferring allocation entirely.
- What actually happened: Termination: confirmed - 12/12 natural terminations, zero rail hits (max 96/120 calls). Depth: unlocked - d03 hit depth 3 with the task's natural levels (E0 PASS), d02 hit depth 8. But d02_r1's depth-8 branch is globally disproportionate: a YouTube-creator-incentive micro-topic received 5 more decomposition levels than market analysis, and its leaf artifacts barely surface in the 4.4k-char root plan. GLOBAL CALLS REMAINING in context did not curb it.
- Implication for `RATD_Theory.md`: Split section 6's claim: termination needs only a global, code-enforced bound (conservation at the coarsest grain); what per-branch budget actually buys is proportionality - matching subtree size to subtree importance. Local judgment is locally sensible but has no global cost signal. This is Appendix A's motivating evidence when/if promoted, and depth>=4 branches now make section 5 goal-drift measurable for the first time.

## 2026-07-10 - E0-min: zero conflicts persists at depth 8 / 48 agents; temp-0 replication is not deterministic

- Assumption or gap: The probe left section 4 untested at 3-8 agents / depth <= 2 and treated temperature-0 replicates as near-deterministic.
- What actually happened: 36 total runs (probe + E0) with zero write conflicts, now including 48-agent depth-8 graphs - parent-owned interfaces plus namespace discipline keep eliminating WAW hazards as scale grows. Meanwhile d02's reps diverged sharply in shape (depth 8 vs 4, 48 vs 21 agents) from identical initial contexts: vLLM batching nondeterminism, amplified by recursive structure; d04's reps were byte-identical.
- Implication for `RATD_Theory.md`: Section 4's inevitability argument now needs engineered dependency overlap (Figure-1 f01) to be tested at all - organic conflict has a much higher threshold than theorized, which is itself a positive coordination result worth stating. And replicate variance at temp 0 is real: shape metrics need distributional reporting, not single-trace claims, even before sampling temperature enters.
## 2026-07-10 - Figure-1 run 1: reads are grants, not delivery - context truncation silently severed a 100%-agreed channel

- Assumption or gap: The theory (and every metric so far) treats a cross-branch read as information transfer: if the consumer's condition names the path and the entry is visible, coordination happened. Schema agreement measures address consistency only.
- What actually happened: In f01 v1, all 4 RATD runs had root gate the tutorial on the terminology interface, and the tutorial agent read it (cross_branch_read logged, schema agreement 22/22). But worker context sliced memory values to 1000 chars; in 2 of 4 runs the terminology doc led with ~1000 chars of prose, so ZERO vocabulary terms reached the consumer - terminology consistency 0% while every coordination metric read perfect. In the other 2 runs the terms led the doc and the consumer used 79-92% of what it could see. The model was faithful to its visible window in all 4 runs; the channel, not the agent, failed.
- Implication for `RATD_Theory.md`: The retrieval model is not an optimization detail - it is part of the coordination semantics. A (Delta-D, Delta-C) step whose data exceeds the consumer's context window delivers a prefix, and no current signal detects the loss (a consistency-audit Observer would). "Memory-first lookup" needs a stated delivery model: what fraction of an entry a reader gets, and whether producers are incentivized to front-load interfaces (the run that front-loaded terms coordinated fine). Also a measurement rule for the paper: any content-coordination claim needs a content-level metric alongside the address-level ones.

## 2026-07-10 - Figure-1 run 1: statable dependencies get planned - no emergent edge without unforeseeability

- Assumption or gap: Theory section 3's corollary predicts RATD grows DAG cross-links a pre-planned tree cannot. The f01 v1 task stated the A->B consistency requirement in the root task text.
- What actually happened: Root pre-planned the A->B edge in 4/4 runs (tutorial gated on the terminology interface at spawn time). Zero DEFERs, zero emergent cross edges; the RATD graphs were trees a one-shot planner could write - and the baseline planner wrote essentially the same tree in 4/4 runs.
- Implication for `RATD_Theory.md`: Local routing with root-goal visibility plans every dependency that is statable at spawn time; that is correct behavior, not a failure. The emergent-DAG advantage is therefore confined to dependencies that are genuinely unforeseeable at spawn time (discovered from content mid-execution). Section 3's corollary should be narrowed to that class, and Figure-1's task must instantiate it (v2 buries the signal; if root still plans it, v3 needs dependencies that only materialize from intermediate results).
