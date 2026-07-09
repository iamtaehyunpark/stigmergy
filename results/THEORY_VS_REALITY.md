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
