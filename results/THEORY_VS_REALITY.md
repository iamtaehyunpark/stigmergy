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
