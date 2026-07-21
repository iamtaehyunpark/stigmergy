# RATD Playground Spec v2.0
## The minimal faithful architecture for testing the theory

**Status:** Normative for the v2 rebuild. Supersedes the v1 runtime architecture entirely (memory, circuit interface, and agent model are all redesigned). The v1 *substrate findings* (mechanical gate firing, CAS exactly-once, catalog integrity, abandonment detection, provenance, doctor) carry forward as validated concepts; their implementations are rebuilt around the new agent model.
**Relationship to theory:** the theory is unchanged. This document builds the environment the theory always assumed: autonomous agents that reason over multiple rounds, use tools by choice, and deploy other agents during execution. Rationale: the architecture-reframing discussion (2026-07-15) — the v1 experiments implemented the theoretical agent as a single-shot QA call, so the substrate was validated but the theory's causal variable was never isolated; this spec is the faithful realization. Three-level separation (theory / realization / architecture) governs the paper.
**Governing stance (ratified):**
1. **Proof-of-concept first.** Build only what the decisive experiment needs. Every deferred capability gets an unlock condition, not a design.
2. **No behavioral rules on agents.** This is an experiment, not a product. Agents have full freedom — including editing any circuit rule. Everything is logged; outcomes are observed raw and handled after.
3. **Fair fight.** Any capability given to RATD agents is given identically to the baseline's agents, except the causal variable itself (spawn + circuit authorship). See `RATD_Experiment_Spec_ET.md`.

---

## 1. The Agent (the center of the redesign)

An agent is a persistent, multi-round process:

```
loop:
  observe   (own workspace state, tool results, anything it chooses to inspect)
  reason
  act       (one tool call, or several, or none)
  observe effects
  update own state
until the agent itself declares: done | failed | waiting(condition)
```

- **Identity & lifecycle:** persistent id; states `spawned → running → waiting | done | failed | terminated`. State transitions are runtime-tracked events (circuit-referenceable). `waiting(condition)` = the agent authors its own wake rule and suspends.
- **The agent decides everything semantic:** whether to read memory, what to write, whether work already exists (duplicate checking is the agent's job via catalog inspection — never the system's), whether to spawn, what conditions to author, whether its own output is good enough, when it is done.
- **Between-round state:** what survives is the agent's workspace (structured files: plan, checklist, notes, drafts) plus a bounded rolling window of recent rounds — NOT an unbounded transcript. The harness instructs agents to externalize durable state to workspace files; the runtime enforces only the window bound.
- **Bounds (rails, not rules):** max rounds per agent R_max=30, global call rail, wall-clock rail. Hitting a rail = recorded finding.
- **Harness repositioning:** the system prompt documents tools and gives behavioral *guidance* ("check existing work before spawning; verify effects before claiming done"), never mandatory sequences, schemas-as-actions, or required declarations. Routing is not a form to fill; it is a decision the agent may or may not take.

## 2. Memory M = (K, W, G, E)

- **K — Catalog (mechanical index, runtime-maintained):** what agents exist + states; what artifacts exist + location/version-head/author; what rules are installed. Queryable, bounded returns. Never contains bodies. The catalog answers "what's there"; agents decide what it means.
- **W — Workspaces:** one filesystem namespace per agent (`agents/<id>/`), free-form files, owner-organized. **Visibility: open** — any agent may read any workspace (ownership = who organizes, not who may see). Cross-workspace *writes*: allowed (no rules, per stance 2), logged loudly.
- **G — Global memory (`global/`):** shared artifacts. **Linear versioning only:** every write creates an immutable new version; head pointer; author+round provenance per version; concurrent-write to same artifact = both versions kept + divergence flagged in catalog (visibility, not resolution). No branching, no merge machinery — unlock condition: a run where two agents genuinely contend and linear versions + agent judgment demonstrably can't cope.
- **E — External task memory:** deferred until a task class demands it (coding tasks → repo). The decisive experiment uses text-artifact tasks; E is not built for v2.0.

## 3. Circuit C

A rule is `(φ, σ, μ, p)`: condition, target, firing policy, provenance.

- **Conditions: general expressions, minimal machinery.** A condition is a Python boolean expression string, evaluated by the runtime via restricted-namespace `eval`: the namespace contains **only the state accessors** (read-only, deterministic views of observable state — `exists(path)`, `head(path)`, `field(path, key)`, `state(agent_id)`, `children(agent_id)`, `fired(rule_id)`, `matching(glob)`, `count(...)`), with empty builtins and an evaluation timeout. No parser, no custom grammar — agents write conditions in the expression syntax they already know, with full boolean/comparison logic free of charge. The `circuit.add_rule` tool echoes back the expression's current truth value, so the authoring agent sees immediately how its intention compiled (and whether it's already true). **The only hard boundary (architectural):** mechanical evaluability, enforced by the namespace itself — only deterministic read-only accessors are referenceable; no semantic predicates exist to call. "Fire when the draft is good enough" is not expressible; an agent judges quality, writes `global/review.json`, and gates on `field("global/review.json","approved")==True`. Evaluation errors and timeouts are tool errors (mechanical rejection, not policy). New accessors are registered when a task class brings a new state source (e.g. `tests_passed(repo, commit)`); the mechanism never changes, its visible world grows. (Restricted eval is experiment-grade by design; a hardened parser is a product-era item, Part D.).
- **Firing:** mechanical evaluation on every state event; exactly-once via atomic CAS; activation = spawn the specified agent or resume the specified waiting agent. Target specs carry task, capsule, root-goal pointer, initial references.
- **Authorship: unrestricted.** Any agent may `add_rule`, `update_rule`, `disable_rule` — including others' rules. Every edit is provenance-logged with before/after. **Edit semantics (mechanical, complete):** rules are state rows; the `fired` flag is ordinary editable state; nothing re-fires unless an agent explicitly resets `fired` (allowed, logged) — exactly-once holds per armed state via the same CAS. No validator rejections of circuit edits in v2 (stance 2); malformed conditions are returned as tool errors (mechanical unevaluability, not policy).
- **No declared obligations.** There are no pins/promises in v2. Future-work coordination is expressed through what is observable: agent lifecycle accessors, `exists()` on eventual artifacts, workspace inspection. "Someone intends to produce X" is state you can see, not an object you register.
- **The circuit never reasons.** No semantic evaluation, no LLM calls, no dedup, no repair logic inside R.

## 4. Tool layer T (the complete v2 surface)

```
catalog.search(query, k) / catalog.inspect(id)
workspace.read(path) / workspace.write(path, content) / workspace.list(prefix)
global.read(path, version?) / global.commit(path, content, summary?) / global.history(path)
circuit.inspect(filter) / circuit.add_rule(φ, σ) / circuit.update_rule(id, ...) / circuit.disable_rule(id)
spawn(task, capsule, initial_refs, on_complete_rule?)
wait(condition)          # suspend self; sugar for add_rule(φ, resume-self)
done(summary) / fail(reason)
```

All returns bounded (size caps with visible truncation markers — the reads-are-grants lesson is law). Every call logged: agent, round, args, result size. No other tools in v2.0 (task work is reasoning + memory operations; external tools arrive with E).

## 5. Runtime R

Mechanical only: tool execution, persistence, catalog maintenance, condition evaluation, CAS firing, activation/scheduling, lifecycle tracking, rails, full event trace. **Scheduling: serial** (round-robin over runnable agents, one round per turn) — concurrency semantics were pinned in v1 A′ and remain deferred; serial keeps the theory experiment clean of race confounds. **Quiescence & failure (pin-free definitions):** quiescence := no agent runnable ∧ no rule true-and-unfired. At quiescence no further state change is mechanically possible, so any `waiting` agent at quiescence is permanently stuck by definition — no dead-rule analysis required. Systemic failure := root agent not `done` ∨ any agent `waiting` at quiescence ∨ any unhandled `failed` agent. **Doctor: not installed** for the decisive experiment (stance 2: observe raw failure); the failure predicate still evaluates and logs so every run ends with a mechanical health verdict. Doctor returns as an option in later phases.

## 6. Measurement redefinition (required before any run)

"Context per decision" for multi-round agents: **per-round prompt size** (window + workspace-loaded state + tool returns), reported per agent per round; plus rounds-per-agent r and workspace size over time. The O(1) claim's honest v2 form: *per-round context is bounded by local effort (O(r), r capped) and independent of global task size n and graph depth* — vs the centralized planner's per-decision context growing with global state. Both eras of the crossover figure must state which definition they use.

## 7. Deferred table (each with its unlock condition)

| Capability | Unlock condition |
|---|---|
| Branch/merge in G | linear versions + agent judgment demonstrably insufficient in a real contention run |
| New state accessors (external-state predicates etc.) | a task class registers the corresponding state source (the expression language itself is already general) |
| External memory E + task tools | task class requiring it enters the experiment set |
| Concurrency (A′ semantics ready) | serial wall-clock becomes the binding constraint on experiments |
| Doctor / observers | post-decisive-experiment; induced-failure phase |
| Retrieval beyond catalog.search | catalog.search demonstrably insufficient at real memory scale |
| Budget/proportionality economics | disproportionality distorts a result (d02_r1-class recurrence) |
| Circuit-edit permissions, HITL, security | product phase, not experiment phase |

## 8. What carries over from v1 unchanged

Address discipline for global/catalog paths (grammar, advisory descriptive naming) · visible-truncation law · content-level metrics mandatory alongside address-level · distributional reporting of shapes · interleaving recording · pre-registration discipline · THEORY_VS_REALITY.md continuous.
