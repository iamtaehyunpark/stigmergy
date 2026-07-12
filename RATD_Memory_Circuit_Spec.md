# RATD Memory & Circuit Specification
## v1.0 — Normative. Ground truth for the runtime rebuild.

**Relationship to other documents:** This spec owns the formal semantics of M = (D, C). `RATD_Theory.md` v1.2 §1.1 will point here. Evidence citations refer to `PROBE_REPORT.md`, `EXPERIMENT_REPORT.md`, and `results/THEORY_VS_REALITY.md`. Design history in `RATD_MemCircuit_Design_Tracker.md`.

**The organizing principle (ratified):** RATD has a **control plane** and a **data plane**, and they were previously conflated.
- The **circuit C** is the control plane: agent nodes, pins, gates, wiring. It is enumerable structure. Nothing in it is free-form text.
- The **memory D** is the data plane: the catalog (a mechanically derived one-line shadow of the circuit) and the store (artifact bodies).
- They touch at exactly one directed edge: a data-plane write **fulfills** a control-plane pin. Memory never triggers anything; it only fulfills. All triggering is circuit logic.
- Consequence, by construction: a gate cannot be wired to a nonexistent pin. Dangling references (blind defer, E1 L3_r1) become unwritable, not merely repairable.

**Standing requirements:**
- **R1 — Context-cost bound:** every read/discovery channel declares its bound. The O(1) result (E1: 7.2k→8.4k flat vs 4.6k→41.6k) is enforced structurally.
- **R2 — Mechanical detectability:** every failure state has a stated mechanical signature (preserves the 6/6 detectability record).
- **R3 — Evidence traceability:** every rule cites its motivating run.
- **R4 — No agent discipline:** no rule may depend on agents voluntarily maintaining a behavior; every guarantee is runtime-derived or validator-enforced. (Lesson of the whole E-series.)

---

## §0 Vocabulary (normative)

| Term | Definition |
|---|---|
| **address** | string `namespace/key` conforming to §A1 grammar |
| **pin** | a circuit node: an address existing as *obligation* (a promise), created at authoring time, before data exists. Pins live in C. |
| **entry** | an address existing as *data* in the store: `(address, summary, body, metadata)` |
| **fulfillment** | the write event that flips a pin `promised → done` (or `failed`); the only D→C edge |
| **gate** | AND/OR condition over terms (§B1); when it passes, the circuit fires its consequence (spawn/wake) exactly once |
| **wiring** | an agent authoring a gate by referencing existing pins / agent nodes |
| **agent node** | a circuit object per agent, carrying lifecycle state (§B7) |
| **catalog** | mechanically derived index: one line per pin — `address · status · summary`. The circuit's shadow in D. |
| **store** | write-once body storage, open-read |
| **promotion** | an agent publishing an internal artifact at interface level via declare-and-write (one act) |
| **quiescence** | queue empty ∧ no agent in-flight ∧ no fireable gates |
| **dead gate** | unfired ∧ references unsatisfiable by any pin of a live or sleeping agent |

"Output," "declaration," "promise," and "interface" in older documents all map to **pin** (an interface is a pin authored by a parent for a child).

---

## PART A — Memory D

### A1 Address grammar
- BNF: `address ::= namespace "/" key` ; `namespace ::= "root" ("." index)*` ; `index ::= [1-9][0-9]*` ; `key ::= [a-z][a-z0-9_]*` ; key length ≤ 64.
- No dots, no extensions, no uppercase in keys (evidence: `.tar.gz` drift correlated with worker refusals, E1 d01_r3). Enforced identically in validator, runtime, and worker prompts; never relaxed (the PATH_RE lesson).
- **Numeric families:** keys matching `<stem>_<n>` (e.g. `chapter_3`) are recognized as families for incremental assembly (§A5); a family is declarable as a single pin-set `chapter_{1..n}` with known n.
- Reserved: any namespace beginning `_` (`_system/`, `_doctor/`) is runtime-writable only.
- Naming convention (advisory, in harness; not load-bearing per R4): keys describe content, not role or sequence — `kyoto_restaurants_list`, not `subtask_2_output`. Semantics travel in the catalog summary, never in the name alone (blind defer was a plausible-name guess).

### A2 Pins: creation and lifecycle
- **Creation (uniform rule):** every act that authors circuit structure creates its pins at authoring time —
  1. SPAWN subtask outputs (each child's declared outputs),
  2. self_role outputs (the spawner's own owed paths),
  3. EXECUTE `result_outputs` (pins exist during the worker call — the leaf's in-flight work is visible and reservable),
  4. promotion (declare-and-write: the emission that writes the artifact registers its pin in the same act; the registry never lags reality).
- **Lifecycle:** `promised → done | failed | abandoned`.
  - `done`: fulfilled by a conforming write.
  - `failed`: the owning agent completed but could not produce it (worker reports failure) — the entry may carry a failure body for reflection.
  - `abandoned`: the owning agent died/was dropped with the pin unfulfilled. **Abandonment chain (normative):** agent enters a terminal failure state (§B7) → all its `promised` pins flip to `abandoned` → liveness re-evaluation runs immediately (§B4) → newly dead gates are flagged mid-run and enter the doctor dossier at quiescence.
- Pins double as **reservations** (A′2): a `promised` pin is the "being produced" signal; parallel branches consult the catalog before spawning producers of equivalent artifacts. `claimed-but-never-completed` ≡ `abandoned` — same mechanical class.

### A3 Ownership and writes
- Write-once, first-writer-wins. A second write to a done address inserts into `conflicts` (observability preserved for theory §4) and does not modify the entry. No locks, no versions (required for concurrency safety, A′).
- An agent may write to: (a) addresses of its own pins (own namespace or inherited interface pins), (b) new addresses under its own namespace via promotion.
- `_`-prefixed namespaces: runtime and system agents only.

### A4 Reads: open-read (ratified)
- **Any agent may fetch any `done` entry by address. No read authorization exists in the system.** The only read constraints are economic (R1 budgets, §A5); the only read record is the fetch log (every fetch is a logged circuit event).
- The grant concept is deleted. Capsule pointers are ordinary addresses the child fetches like any other. There are no hidden coordination channels because there are no closed ones.

### A5 Delivery model (both directions, stated capacity)
- **Structured entry:** `summary` (≤ 160 chars, produced by the writer, mandatory), `body` (artifact), `metadata` (author, created_at, content_length, provenance). The summary is the producer digest — the catalog line derives from it mechanically (address + status from the circuit, summary from the entry). R4: no separate notification discipline exists or is needed.
- **Input side:** two read actions, both bounded —
  - `list(namespace_prefix, k)` → up to k catalog lines (addresses + status + summaries; never bodies). Default k = 20.
  - `fetch(address)` → the body, delivered up to the per-step fetch budget; default budgets: routing step 8,000 chars total across fetches, worker step 24,000 chars total. Over-budget bodies deliver head + tail with an explicit `[truncated: full length N]` marker — truncation is always visible to the reader (fig1 v1's silent slice is prohibited).
- **Output side:** per-response cap acknowledged as an environment constant (4k tokens observed). Any artifact expected to exceed ~12k chars MUST be produced as a numeric family (`section_1..n`) plus a final short index entry — the assembly-stub class (5 runs, E1) is closed by making single-emission mega-artifacts illegal at the harness/validator level.

### A6 Discovery
- v1 primitive: `list` (§A5) — mechanical, namespace-filtered, k-capped, summaries only. This is the bounded catalog query; it dissolves the L3_r1 class (root.5 lists `root.1/` and sees `chapter_1_final — polished EN translation…`).
- Escalation path (same slot, plug-in upgrades, all deferred): embedding search over summaries → librarian agent. **Librarian-as-organizer is rejected:** no agent may mutate source entries or addresses (breaks write-once and wiring stability). Derived indexes under `_system/` are permitted.

### A′ Concurrency semantics (spec-now; parallel runtime itself remains deferred)
- **A′1 Snapshot-at-dequeue:** an agent's context is built from a snapshot of catalog+circuit taken at dequeue; its decision is attributable to that definite state (R2). Fetches during a step read the live store (bodies are write-once, so no torn reads).
- **A′2** resolved into §A2 (pins are reservations).
- **A′3** Every run records its interleaving (agent start/end order); shape metrics are reported as distributions (temp-0 divergence, E0 d02).

---

## PART B — Circuit C

### B1 Gates
- Grammar: terms combined with AND/OR and parentheses. Two term types:
  - `done("address")` — the pin at address is fulfilled (data dependency; required for interface contracts),
  - `completed("agent_id")` — all pins of that agent node are terminal-done (structural dependency; sugar, but first-class: it expresses "my siblings finished" without naming artifacts — L3_r1's actual intent).
- No fuzzy/semantic matching, ever. Exactly-once firing is an invariant implemented as an atomic check-and-set on the fired flag (`UPDATE … WHERE fired=0`, rowcount-guarded) — required under concurrency, honored today.
- Re-evaluation: after every fulfillment, every abandonment, and at quiescence.

### B2 Wiring validity
- A gate (spawn condition, self_role condition, wake condition) may reference only **existing pins / agent nodes** at authoring time. Hard reject otherwise; the repair feedback lists the actual pins in the referenced namespaces (the one-round-trip fix). Ancestor `done` entries are referenceable (their pins exist).
- Consequence: blind defer is unwritable.

### B3 Provenance
Every gate records author + mechanism: `root-spawn | deep-spawn | self_role-gate | defer-wake | system-default | doctor-repair`.

### B4 Liveness
- Dead gate per §0. Evaluated: at quiescence, and immediately upon any pin abandonment. Mid-run detection logs a warning event; consumption happens at quiescence (doctor).
- A dead gate is a systemic-failure input (§B5), never silently dropped.

### B5 Quiescence and the failure predicate
- Quiescence := queue empty ∧ no agent in-flight ∧ no fireable gates.
- Systemic failure := unmet root pins ∨ dead gates ∨ fallback-marked writes ∨ abandoned pins.
- This predicate is circuit spec (runtime-evaluated, mechanical), not doctor-private logic.

### B6 System layer
- `_system/` facts (quiescence flags, failure dossiers, doctor cycle count) are written by the runtime only. Agents may **read** them (open-read is universal) but may not **write or gate on** them in v1. System gates (conditions over system facts) are reserved to runtime-installed rules; the doctor rule is the first occupant.

### B7 Agent lifecycle statechart
`promised → queued → routing → (executing | sleeping) → done | failed | dropped | starved`
- `sleeping`: DEFER accepted, wake gate installed. `dropped`: removed by rail/validator exhaustion. `starved`: sleeping ∧ wake gate dead. `failed`: terminal error in routing/working.
- Terminal failure states (`failed`, `dropped`, `starved`) trigger the §A2 abandonment chain. Every state transition is a logged circuit event with a mechanical signature (R2).

### B-parked (user item, logged not designed)
Agent-modifiable fulfillment surfaces — e.g. todo-list gates agents can check off, autonomous fulfillment verification. Revisit after the doctor era.

---

## PART C — The Doctor (first system rule)

- **C1 Trigger:** quiescence ∧ systemic failure (§B5). K-bounded, K=2 per run, inside the global call rail; prior doctor cycles included in its dossier.
- **C2 Dossier (all mechanically derived):** dead gates with their unresolvable references + the actual pin list per referenced namespace (the string delta root.5 was blind to); unmet root pins; abandoned pins and their owning agents' terminal states; fallback-marked writes; sleeping/starved agents with their wake gates; prior doctor attempts.
- **C3 Privileges — additive + corrective:** may SPAWN repair agents; may install wake gates; may re-enqueue a sleeper with a corrected gate (the DEFER re-enqueue pattern). May never retire or edit another author's gates (provenance integrity).
- **C4 Accounting:** after the doctor's subtree quiesces, the failure predicate re-runs. A doctored run reports `converged-with-repair`, never plain `converged`.
- **C5 Boundary:** systemic failures only. Semantic failure (L4_r3's plan-instead-of-guide) belongs to a future content-audit system rule on the same B6 layer.

---

## PART D — Explicitly deferred (with evidence)

Parallel runtime implementation (semantics pinned in A′/B1/B5) · conflict resolution policy (write-write impossible by construction; other classes unexercised) · budget/proportionality economics (Appendix A of experiment spec; d02_r1 evidence logged) · store persistence & scale · semantic search / librarian retrieval (A6 escalation) · content-audit observer (C5) · heterogeneous model routing · human-in-the-loop gates · security/wiring permissions · agent-modifiable fulfillment surfaces (B-parked).

---

## Failure-class coverage table (R2 audit)

| Class | Mechanical signature | Prevented or detected by |
|---|---|---|
| No-integrator | unmet root pins at quiescence | B5 → doctor |
| Interface orphaning | (killed by participation rule) abandoned interface pins | A2 chain → doctor |
| Dropped DEFER | sleeping agent with no installed gate — unrepresentable | B7 (DEFER ⇒ gate installed, atomic) |
| Blind defer | wiring to nonexistent pin | **unwritable** (B2) |
| Assembly stub | fallback-marked write | B5 predicate; class shrunk by A5 output rule |
| Claimed-never-completed | abandoned pin | A2 chain → doctor |
| Silent truncation | — | prohibited by A5 (visible truncation markers) |

## Changelog
- v1.0 — Compiled from Design Tracker v0.2 after ratification: control/data-plane separation; uniform pin creation (all four acts); open-read; catalog as mechanical shadow; bounded list/fetch with stated budgets; numeric-family assembly; gate grammar with `completed()`; wiring validity (hard reject); doctor C1–C5. All seven original [CHOOSE] items resolved.
