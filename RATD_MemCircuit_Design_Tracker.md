# RATD Memory & Circuit Specification — Design Tracker
## v0.1 (working document — decisions land here one by one)

**Purpose:** This tracker is the worklist for designing D (memory) and C (circuit) as first-class artifacts with defined semantics — the layer the E-series proved was under-designed relative to load. Each item below becomes a normative section of the final `RATD_Memory_Circuit_Spec.md` once its decision is RATIFIED. Nothing gets built until its section is ratified.

**Relationship to theory:** This spec will own the formal semantics of M = (D, C). `RATD_Theory.md` v1.2 §1.1 will become a pointer to this document.

**Standing requirements (apply to every section, non-negotiable):**
- **R1 — Context-cost bound:** every grant/discovery/visibility channel defined in this spec MUST declare its context-cost bound. The O(1) theorem (E1's confirmed result) is enforced structurally here, not by hope.
- **R2 — Mechanical detectability:** every failure state defined here must have a stated mechanical signature (the 5/5 detectability record is a property to preserve by design).
- **R3 — Evidence traceability:** every decision cites the run/finding that motivates it.

**Design order (dependency-driven):**
0 → A2 → A1 → A3 → A4 → A5 → A6 → B1–B7 → C1–C5 → final assembly.
(A2 first: the promise lifecycle underpins A6, B2, B4, B5, C2 — most downstream sections can't be written precisely until "promise" is pinned.)

---

## §0 — Vocabulary Table [STATUS: UNDECIDED — design first or fill as we go]

The words that must be pinned before they drift (the "budget" lesson: fuel vs. frontier-capacity conflation cost us a full confused thread):

| Term | Candidate definition (to ratify) |
|---|---|
| **address** | a string `namespace/key` conforming to the grammar (A1) |
| **promise** | an address existing as *obligation* — declared by a spawn/self_role document before any data exists |
| **entry** | an address existing as *data* — (address, value, status, author, metadata) in D |
| **interface** | a promise assigned by a parent that downstream rules may gate on |
| **grant** | a circuit-recorded permission for a specific agent to read a specific entry/promise |
| **rule** | (φ, σ) in C — condition over D state + consequence |
| **promotion** | an agent electing to publish an internal artifact at interface level (observed in fig1 v3; currently extralegal) |
| **quiescence** | queue empty ∧ no fireable rules (B5) |
| **dead rule** | unfired ∧ refs unsatisfiable by any live promise (B4) |

Open items: does "output" survive as a term or collapse into promise/interface? Does "declaration" = promise exactly?

---

## PART A — Memory D (the medium)

### A1 — Address grammar [STATUS: LEANING — strict snake_case, no dots in keys]
One formal syntax, enforced everywhere (validator, runtime, worker prompts), never silently relaxed again.
- Evidence: PATH_RE relaxation between phases; `schema.json`/`backend_code.tar.gz` drift; `.tar.gz` paths correlated with worker refusals (E1 d01_r3).
- Claude's position: strict. Extension-like suffixes invite file-system semantics the memory doesn't have.
- To design: exact BNF; key length cap; reserved prefixes (`_system/`); whether numeric-suffix families (`chapter_1..n`) get grammar support (assembly A5 wants them).

### A2 — Address lifecycle: promises before data [STATUS: FORCED mechanism, details to design]
A declarations/promises registry: `(address, promiser, status: promised | done | failed | abandoned)`. Root cause fix for blind defer; underpins B2, B4, B5, C2, A6.
- Evidence: L3_r1 (Q2's 100% held only where strings flowed through spawn docs; root.5 had no registry to consult).
- To design: exactly which acts create a promise (spawn outputs; self_role outputs; EXECUTE result_outputs?; promotion?); who may transition each status; **the abandonment chain** (Claude's Gap 1): agent dies/fails → its unmet promises → abandoned → immediate liveness re-evaluation (B4) → dead rules surfaced mid-run, consumed by doctor at quiescence today, by failure-triggered rules later. `status=failed` finally gets a consumer.

### A3 — Ownership & write rules [STATUS: LEANING — write-once, argument strengthened]
Formalize: own namespace + owed interface paths (v5 contract) + **promotion** made legal (94–96% consistency when used, fig1 v3).
- Concurrency argument (A′): write-once + first-writer-wins makes the blackboard safe under true parallelism with no locks and no versioning; mutable entries would force one or the other. The serialization realization upgrades this lean to near-forced.
- To design: write-once semantics ratification (second write → conflicts table stays as §4 instrumentation); promotion's exact mechanics (does promoting create a promise retroactively? who may gate on a promoted path?); `_system/` write rules.

### A4 — Visibility / read grants [STATUS: CONTESTED — worksheet says remove capsule grants; Claude says compile them]
Today three channels: ancestor namespaces + condition refs + capsule-mentioned paths (informal, undocumented, silently load-bearing in fig1 v3 r2/r3).
- Claude's synthesis to ratify or reject: **compile capsule grants** — at spawn time the runtime mechanically extracts capsule-mentioned paths and materializes them as explicit grant records in C. Capsule stays the authoring surface (ι's "pointers into D" semantics preserved per theory §2); circuit becomes the complete coordination record (doctor/visualizer see every grant); informal channel eliminated.
- To design: grant record schema; whether ancestor-namespace visibility also gets materialized or stays ambient; grant context-cost bound (R1).

### A5 — Delivery model, both directions [STATUS: LEANING — structured entries]
Stated capacity, not accidental truncation.
- Evidence: reads-are-grants (fig1 v1, 0% content across a 100%-agreed channel); assembly stubs (E1, 5 runs, both architectures).
- Structured entry = `(summary, body, metadata)`: summary doubles as producer digest (closes delivery-audit menu item), metadata carries provenance + content length, "summary free / body on grant" makes input capacity a designed number.
- To design: summary length cap; slice budgets per read type (route vs. work — replace today's accidental 700/4000); incremental assembly convention (per-section keys — needs A1 numeric families); output-cap handling (chunked assembly protocol).

### A6 — Discovery [STATUS: LEANING — (b) directory listing, BOUNDED]
For the address you cannot name. The regime door.
- Evidence: nameability boundary (fig1 v3 r4: 51% delivery); blind defer (E1 L3).
- Claude's bound (R1, non-negotiable): namespace-filtered, k-capped, paths + one-line summaries only, never bodies. Unbounded registry read = O(n) context = the crossover figure's flat line bends.
- To design: the exact query form (an action? a context term? doctor-only at first?); k; interaction with B2's repair feedback (rejection lists actual promises — that's already a micro-discovery channel); (c) semantic search stays deferred to the deep-research slice.

---

## PART A′ — Concurrency semantics (added after the serialization realization)

**Scoping note (record, permanent):** all 68 runs executed as a serial interleaving (`while queue: pop(0)` — every agent's read→LLM→write cycle atomic against all others). "Parallel" was logical only. Therefore: namespace ownership eliminates write-write conflicts *by construction* (survives parallelism); every other conflict class was eliminated *by serialization for free* and has never been exercised. The E-series validated the coordination grammar, not its concurrency safety. Design below is required before true parallelism ships; sections marked (spec-now) get their semantics pinned in this spec even though the parallel runtime stays in Part D.

### A′1 — Snapshot semantics [STATUS: UNDECIDED] (spec-now)
What does an agent see: snapshot-at-dequeue (what serialization currently emulates) or live state during its step?
- Under parallelism an agent's 30–60s LLM call means its decision is based on stale state either way; the question is whether staleness is *defined* (snapshot) or *arbitrary* (live reads mid-step).
- Claude's lean: snapshot-at-dequeue — it makes every routing decision attributable to a definite D-state (R2: mechanical signatures need this; so does trace replay/debugging).
- Interacts with: doctor dossier (which snapshot did the failing agent act on), determinism/effective-n reporting.

### A′2 — In-flight visibility / reservation state [STATUS: UNDECIDED — biggest structural addition parallelism forces] (spec-now)
Stigmergy coordinates through completed traces; the trace is a record, not a reservation. Two parallel branches that both need a glossary and cannot see each other's in-flight intent will both spawn one.
- Candidate: a `claimed` status between absent and done — promises already give the natural home (A2's registry entry *is* the reservation; a spawn document claiming an address is visible intent).
- Note the elegant collapse: if A2 promises are visible to discovery (A6) and to B2 validation, in-flight visibility may come for free — a promise IS the "being produced" signal. To verify when designing A2: promise visibility rules must serve this double duty.
- New mechanically-detectable failure class (R2): claimed-but-never-completed → feeds A2 abandonment chain → doctor dossier. (Sixth class; keeps the 5/5→6/6 record.)
- Interacts with: duplicate-work prevention, A5 metadata, C2.

### A′3 — Determinism & replication policy [STATUS: FORCED — policy, not mechanism]
Temp-0 clustering and all reproducibility claims were conditioned on FIFO order; parallel completion order makes every run a distinct interleaving.
- Policy: shape/quality metrics are distributions (already adopted post-E0); additionally every parallel-era run records its interleaving (agent start/end order) so any run is replayable as a serial schedule. Cheap now, priceless in a debugging session.

---

## PART B — Circuit C (the rules)

### B1 — Rule semantics [STATUS: FORCED — freeze as proven]
`done()` over exact strings, AND/OR, exactly-once firing, re-eval after every write. No fuzzy matching ever (L3_r1 argues for A2/B2, not semantic triggers).
- Concurrency amendment (A′, spec-now): exactly-once must be specified as an **atomic check-and-set on the fired flag** (concurrent completions can satisfy the same AND-condition simultaneously). The current `UPDATE ... WHERE fired=0` idiom is the right shape; the spec states it as an invariant with a required atomicity mechanism, not an implementation accident.

### B2 — Reference validity [STATUS: LEANING — hard reject]
Conditions (spawn / self_role / wake) may only reference promised addresses; rejection feedback lists actual nearby promises (the one-round-trip fix L3_r1 needed).
- To design: exact scope (are ancestor `done` entries referenceable too — presumably yes); feedback format; interaction with promotion (A3).

### B3 — Rule provenance [STATUS: FORCED]
Every rule carries author + mechanism (root-spawn / deep-spawn / self_role-gate / defer-wake / system-default / doctor-repair). Doctor and visualizer need it natively.

### B4 — Liveness semantics [STATUS: FORCED, details to design]
Dead rule := unfired ∧ refs ⊄ (done ∪ promises of live/sleeping agents). Evaluated at quiescence + on every promise abandonment (A2 chain).
- To design: whether mid-run dead-rule detection warns immediately or only feeds the quiescence dossier.

### B5 — Quiescence & failure predicate [STATUS: FORCED, definition amended for concurrency]
Run complete := queue empty ∧ **no agent in-flight** ∧ no fireable rules ("queue empty" alone no longer means "nothing running" under parallelism — quiescence detection must be race-safe or the doctor fires mid-run). Systemic failure := unmet root promises ∨ dead rules ∨ fallback-marked writes ∨ claimed-but-never-completed promises (A′2). This predicate is circuit spec, not doctor-private logic.

### B6 — System-rules layer [STATUS: LEANING — `_system/` namespace]
Runtime-installed rules with conditions over system facts (quiescence, failure flags), not just `done()`. Doctor first occupant; content-audit Observer second.
- To design: can agents read `_system/`? Can they gate on system facts? (Probably no/no in v1.)

### B7 — Agent lifecycle states [STATUS: FORCED]
Explicit statechart: promised → queued → routing → executing / sleeping → done / dropped / starved / failed. Each state a mechanical signature (R2), not archaeology.
- To design: exact transition events; where `failed` feeds A2's abandonment chain.

---

## PART C — The Doctor (first Observer, default system rule)

### C1 — Trigger [STATUS: FORCED]: quiescence ∧ failure predicate (B5); K-bounded (K=2 suggested); inside global call rail; prior attempts in dossier.
### C2 — Dossier [STATUS: FORCED, format to design]: dead rules + unresolvable refs + nearest promised/done paths per namespace; unmet root promises; fallback-marked writes; sleepers + wake conditions; prior doctor cycles. All mechanical.
### C3 — Privileges [STATUS: LEANING — (b) additive + corrective]: may SPAWN repair agents, add wake rules, re-enqueue sleepers with corrected conditions (the DEFER re-enqueue pattern). May never retire others' rules (provenance).
### C4 — Accounting [STATUS: FORCED]: failure predicate re-runs after doctor subtree quiesces; doctored runs report `converged-with-repair`, never plain `converged`.
### C5 — Boundary [STATUS: FORCED]: systemic failures only; semantic failure (L4_r3 plan-instead-of-guide) belongs to the future content-audit Observer on the B6 layer.

---

## PART D — Explicitly deferred (evidence says they can wait)

Conflict resolution policy (0/68 runs — scoped by A′: zero-conflict evidence covers write-write by construction only) · async/parallel **runtime implementation** (its *semantics* are spec-now per Part A′) · budget economics (Appendix A — proportionality evidence logged, d02_r1) · store persistence/scale · semantic search (A6-c) · content-audit Observer (C5) · heterogeneous model routing · human-in-the-loop gates · security/rule-authorship permissions.

---

## Decision log
| Date | Section | Decision | Rationale pointer |
|---|---|---|---|
| 2026-07-12 | Principle | Control plane (circuit: pins/gates/wiring) vs data plane (catalog+store); fulfillment is the only D→C edge | user's logic-gate reframe; blind defer becomes unwritable |
| 2026-07-12 | A2 | Pins created at authoring by all four acts (SPAWN, self_role, EXECUTE, promotion declare-and-write); pins double as reservations | derived from control-plane principle; A′2 collapse |
| 2026-07-12 | A4 | **Open-read ratified — grant concept deleted.** Reads bounded by budget, never permission; every fetch logged | user: "absolutely no need to limit; concern is context window" |
| 2026-07-12 | A5/A6 | Catalog = mechanical shadow (address+status from circuit, summary from entry); discovery = bounded `list` action; librarian-as-organizer rejected, derived indexes only | user's idea-1/idea-2 synthesis |
| 2026-07-12 | A1 | Descriptive-naming as advisory convention, never load-bearing (semantics travel in summaries) | blind defer was a plausible-name guess |
| 2026-07-12 | B1 | Two term types: `done(pin)`, `completed(agent)` | expresses L3_r1's actual intent |
| 2026-07-12 | Remaining | A1 details, A′1 snapshot-at-dequeue, B4 warn-then-dossier, B6 read-yes/write-no, C1–C5 as leaned — filled by Claude per stop-asking instruction | tracker v0.2 leans |

**STATUS: ALL SECTIONS RATIFIED → compiled into `RATD_Memory_Circuit_Spec.md` v1.0.**

## Changelog
- v0.1 — Tracker created from the E-series design worksheet + Claude's review (compile-grants synthesis, bounded discovery, abandonment chain, R1–R3 standing requirements, vocabulary table).
- v0.2 — Concurrency semantics added after the serialization realization: Part A′ (scoping note on the 68-run serial record; A′1 snapshot semantics; A′2 in-flight visibility/reservation, sixth failure class; A′3 interleaving-recording policy), B1 atomic-firing invariant, B5 race-safe quiescence + claimed-but-never-completed in the failure predicate, A3 write-once upgraded to near-forced, Part D scoped.
