# Recursive Autonomous Task Distribution in MAS
## Theoretical Foundation Document — v1.0

**Author:** Taehyun Park (UW–Madison)
**Status:** Theory closed at v1.0. Next phase: problem formulation writing / minimal testbed design.
**Related projects:** EngramTrace (memory structure → computational cost), Latent Handoff (bounded state transfer between models).

---

## 0. One-Sentence Thesis

Control flow in a multi-agent system can be a property of shared memory state rather than of a central planner: agents make O(1)-context local routing decisions and author trigger rules into an executable memory, so the execution graph emerges recursively — achieving the adaptivity of continuous replanning at none of its context cost.

---

## 1. Formal Objects

The system is `S = (M, A, R)`.

### 1.1 Memory `M = (D, C)`
- **D (Data layer):** append-only, namespaced log. Entries are `(namespace, key, value, status)` tuples; `status ∈ {done, failed, pending}`. Append-only means conflicts are observable (never silently overwritten) and failed paths remain available as reflection context. Storage-level writes are commutative by construction (grow-only set / CRDT-like).
- **C (Agentic Circuit):** a set of trigger rules `(φ, σ)`, where φ is a condition over the current state of D (e.g., `status(A)=done ∧ status(B)=done`) and σ is an agent specification to spawn when φ becomes true.

### 1.2 Agents
An agent is a policy `π(action | context)` over an extended action space:

```
action ∈ { tool_use, write_data, spawn(spec, condition), terminate }
```

There is **no separate router component**. Routing is just the `spawn` action:
- *Sequential (A→B):* spawn rule conditioned on A's completion.
- *Parallel (A, B):* two spawn-immediately rules.
- *Branch (A→B,C,D):* spawn rules into separate namespaces.
- *Execute / defer* are the non-spawn actions.

Agents are task-specific; routing is an option among actions, not a phase. Formally, each agent step returns `(ΔD, ΔC)` — data writes plus new trigger rules.

### 1.3 Runtime `R`
After every write to D, evaluate all φ ∈ C; fire any newly-true rule **exactly once** (exactly-once firing is a required runtime invariant — two concurrent writes satisfying φ must spawn one agent, not two). R is mechanical: pure condition matching, no LLM calls, O(|C|) per write.

### 1.4 Classical identification
S is a **self-extending production system** — equivalently, a Petri net that rewrites its own structure at runtime (places = memory states, transitions = agents, firing conditions = φ). Classical production systems have fixed rule sets; here agents author new rules, and rule authorship is LLM reasoning. This identification supplies vocabulary (liveness, reachability, deadlock) and a 40-year lineage: the circuit is an LLM-native tuple space (Linda) with generative reactions; coordination through environment modification is stigmergy.

---

## 2. The Agent Context (Read Set)

Every agent's context is exactly four bounded terms:

```
ctx(a) = task + role/harness + ι + retrieve(D, query(task), k)
```

1. **task** — the assigned subtask spec.
2. **role/harness** — fixed instructions, schema constraints, namespace rules.
3. **ι (intention capsule)** — bounded compression of *why this agent exists*, produced by the parent at spawn time: subtask goal, justification, constraints, namespace, budget share, pointers into D for anything bulky, and a pointer to the root goal (see §5). ι is bounded by construction (design choice (b) below).
4. **retrieve(D, …, k)** — a mandatory, bounded (top-k) query against D before acting. *That* this read happens is architectural; *how* (RAG technique, embeddings, k value) is implementation detail. This term is load-bearing twice: it is the fourth term of the O(1) bound, and its incompleteness is what makes conflict detection necessary (§4).

### 2.1 The ι design fork
- **(a) Raw inheritance:** child receives parent's full trajectory (or KV prefix). Maximal alignment; context grows O(depth). KV caching reduces *cost*, not *length*.
- **(b) Bounded capsule (chosen):** parent compresses at spawn time; O(1) holds strictly; routing quality now depends on capsule quality.

Open research question (shared with Latent Handoff): *what is the minimal sufficient statistic of a parent's reasoning for a child to route correctly?* Handoff media form a spectrum: text capsule → KV prefix → compressed latent. This paper's claims are independent of the latent version — plain-text ι suffices for the O(1) argument; latent handoff is the upgrade, not the dependency.

---

## 3. Core Theorem (P1+P2 merged): Bounded-Context Adaptive Decomposition

**Claim.** A centralized planner — even with replanning — must re-read accumulated global state at every (re)planning point: O(n) context per decision, with planning quality degrading as state grows. In S, the equivalent adaptation decisions are distributed across nodes at O(1) context each (the four bounded terms of §2).

**Important honesty note.** This is *not* an expressivity theorem. A replanning planner can emulate any graph S produces; the hierarchy "static ⊂ one-shot ⊂ self-extending" collapses at the top. The claim is purely about *cost and degradation*: self-extension is cheap, non-degrading replanning. One sharp theorem instead of two soft claims.

**Falsifiable prediction (the crossover curve — headline experiment).**
Against a replanning central-planner baseline:
- Small tasks: no advantage, possibly a loss (coordination overhead).
- Large / deep tasks: performance gap widens with task size and depth — exactly where O(n) context hurts and O(1) does not.
If experiments show the crossover, the thesis is proven in one figure.

**Structural corollary (emergent DAG, not tree).** Memory-first lookup lets distant agents short-circuit paths via cache hits, so the emergent structure is a DAG whose subtrees merge through shared memory — something a pre-planned tree structurally cannot produce. Measurable as *% of tasks resolved via cache hit / short-circuit* (Figure-1 candidate).

---

## 4. Necessity Result: Conflicts as the Completion Mechanism

**Chain:** bounded retrieval (top-k) ⇒ routing is necessarily incomplete (non-local dependencies can be missed) ⇒ misclassified-parallel conflicts are inevitable ⇒ append-only conflict detection is the *recovery mechanism that completes local routing*.

So conflict-as-feedback is not a feature; it is theoretically necessary. Mechanism:
- A write conflict between tasks routed as independent = WAW hazard = evidence of a missed dependency.
- Append-only D makes every conflict observable and recoverable.
- Each conflict is logged as `(task-pair, predicted-independent, actually-dependent)` — negative samples for the routing policy (few-shot injection or fine-tuning). The system self-improves as it runs.
- Connection to uncertainty work: routing decisions can carry confidence; low-confidence parallelizations get pre-emptive namespace isolation.

**Namespace isolation** remains the prevention layer: branch-scoped labeling (Branch_ID / Context_Tag metadata) keeps diverging paths logically separate entities.

---

## 5. Drift Bound: Parent + Root Anchoring

**Problem.** Every spawn is a lossy re-compression of intent. "Serves" is an approximate LLM judgment, preserved only within ε per link. Approximate relations are not transitive: X–Y within ε and Y–Z within ε gives X–Z within 2ε; depth d gives dε — linear silent drift. Parent-only checks cannot detect inherited error, because the reference itself may have drifted (link 3 corrupted ⇒ everything below verifies faithfully against a corrupted reference and passes).

**Fix (free).** The root goal X is a single constant — O(1) regardless of n or depth — so every capsule carries a pointer to it. Every agent then checks:
1. **Local fidelity** (fine-grained): does my task serve my parent's stated reason? — preserves the causality-chain intuition; the only check compatible with O(1).
2. **Root anchoring** (coarse): is this plausibly still in service of X? — its only job is to bound *compounding*; it need not be fine-grained (deep subtasks legitimately look unrelated to the root).

Result: drift bound goes from dε (depth-linear) to depth-independent (coarse-check tolerance).

**Falsifiable prediction.** Goal drift grows with spawn depth under parent-only checking and flattens under parent+root checking. Measure: LLM judge scores leaf outputs against root intent across depths.

---

## 6. Termination: Budget Conservation

Non-termination has exactly two sources:
- **(a) Circular trigger chains** — handled by Observers (semantic layer, §7).
- **(b) Unbounded spawning** — handled structurally: spawn capacity is a **conserved quantity**. Root starts with budget k; every spawn rule allocates part of the parent's remaining budget to each child; budget strictly decreases along every spawn chain. Termination follows by well-founded induction. No Observer needed for (b).

This separation is important: Observers are a *quality* mechanism (escape semantic stagnation / local minima), not a *safety* mechanism (prevent divergence). Safety is structural.

Bonus: "economic constraints on recursive agent spawning" is an undertreated subproblem — potentially its own contribution.

---

## 7. Observers (LLM-as-a-Judge)

- Conditionally co-spawned only where loops can form: at branch creation or when a task group shares a namespace. Never 1:1 with serial tasks.
- Lifecycle isolated to their branch: terminate when the branch reaches a terminal state in D.
- Function: semantic early stopping (goal satisfied → cut the loop), trajectory delta evaluation (no state change / diverging trajectory → intervene), root-anchoring checks (§5 — judged against the *root* goal read from D, not the possibly-drifted branch goal).
- Role after §6: quality, not safety.

---

## 8. Honest Non-Claims (pre-empting reviewer attacks)

1. **Not fully decentralized.** Rule *authorship* is fully distributed; rule *evaluation* (runtime R) is centralized but mechanical — condition matching, no intelligence, no LLM. Claim: "we decentralize all cognitive work (planning, routing, decomposition) while retaining only a mechanical trigger-evaluation substrate." Claim "no central planner," never "no central anything."
2. **Not confluent.** Different schedulings ⇒ different cache hits ⇒ different (both valid) graphs and answers. Correctness is defined as goal-satisfaction, not determinism. Claiming determinism is a trap; don't.
3. **Not more expressive than replanning.** See §3 — the claim is cost/degradation, not capability.
4. **Exactly-once firing** must be stated as a runtime invariant or reviewers will find the race.

---

## 9. Positioning

| System | Their mechanism | Differentiator |
|---|---|---|
| DynTaskMAS | central task-graph generator + scheduler | graph generated once, then executed; ours grows *during* execution via local decisions |
| LangGraph | developer-defined workflow | static graph at compile time |
| Blackboard MAS | passive shared board | our memory is *executable* (circuit + triggers), not just readable |
| MetaGPT | fixed role pipeline | runtime routing protocol, task-agnostic |
| GPTSwarm / DyLAN / AFlow / ADAS | optimize or generate graphs *before/between* runs | we grow the graph *within* a run |
| Linda / tuple spaces | syntactic pattern-matched reactions | LLM-native: semantic routing, generative rule authorship |
| Petri nets | fixed structure | self-rewriting structure at runtime; supplies our formal vocabulary |

Key one-liner for related work: *prior systems optimize or generate the coordination graph before or between runs; ours grows it during execution through local decisions.*

Framing keywords: stigmergic LLM computation; self-extending production system; memory as the machine (continuity with EngramTrace thesis).

---

## 10. Experiment Map (theory → measurement)

| # | Claim | Experiment | Prediction |
|---|---|---|---|
| E1 | Core theorem (§3) | vs. replanning central planner, scaling task size/depth | crossover curve: planner wins small, S wins large/deep |
| E2 | Emergent DAG (§3) | count cache-hit short-circuits | pre-planned tree produces 0; S produces >0, growing with breadth |
| E3 | ι matters + is boundable (§2) | 3-arm: no-ι / bounded capsule / full trajectory (shared with Latent Handoff) | capsule ≈ full-trajectory performance ⇒ O(1) validated empirically |
| E4 | Drift bound (§5) | drift vs. depth, parent-only vs. parent+root | linear growth vs. flat |
| E5 | Conflict feedback (§4) | routing accuracy over time with conflict-log injection/fine-tuning | accuracy improves as system runs |
| E6 | Router form (ablation) | dedicated small classifier vs. schema-constrained LLM routing | cost/accuracy tradeoff; conflict-log training applies to both |
| E7 | Ablations of necessity | remove circuit triggers (poll instead) / remove namespaces / remove Observers | each removal degrades a specific metric |

**Benchmark requirement:** tasks where the correct decomposition is *unknowable upfront* — mid-execution discoveries must change plan structure (GAIA / BrowseComp-style deep research; or constructed tasks). On HotpotQA-style tasks a central planner suffices and S only adds latency — expected, and consistent with the crossover prediction.

**Open item:** the single crisp Figure-1 task — the minimal concrete example where the emergent graph does something a pre-generated tree structurally cannot (E2's short-circuit demo is the leading candidate).

---

## 11. Open Questions (parked, in priority order)

1. **Figure-1 task construction** — the minimal demo (blocks E2, shapes the whole pitch).
2. **Minimal sufficient statistic for ι** — delegated to Latent Handoff experiments (E3 first).
3. **Capsule format spec** — concrete schema; drift mechanism (§5) becomes concrete here.
4. **Budget allocation policy** — how parents split budget among children (uniform? routing-confidence-weighted?).
5. **Observer judging protocol** — what exactly the trajectory-delta prompt looks like (production detail, but E7 needs a fixed version).

---

## Changelog
- **v1.0** — Theory closed: formal objects (§1), four-term O(1) context (§2), merged core theorem P1+P2 (§3), conflict-necessity chain (§4), parent+root drift bound (§5), budget-conservation termination (§6), Observer role separation (§7), honest non-claims (§8).
