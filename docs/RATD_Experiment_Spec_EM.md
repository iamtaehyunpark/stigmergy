# RATD Experiment Spec — EM-Series (Memory/Circuit Validation)
## v1.0 — Runs against the rebuilt runtime implementing `RATD_Memory_Circuit_Spec.md` v1.0

**Prerequisite:** runtime rebuilt to spec (pins in C, catalog, list/fetch, wiring validation, abandonment chain, doctor, A5 delivery rules). Serial execution retained (Part A′ semantics pinned, parallel runtime still deferred — nothing here requires true concurrency).
**Model:** local `qwen3.6`, temp 0, JSON-constrained — unchanged, so every result is attributable to the spec, not the model.
**Standing rules:** content-level metrics mandatory alongside address-level (reads-are-grants lesson); shape metrics reported as distributions; harnesses/rubrics frozen per experiment before first run and versioned; every run's interleaving recorded (A′3); THEORY_VS_REALITY.md maintained continuously.
**Kill-order:** EM0 gates everything (if the rebuild regresses, stop). EM1–EM3 are independent of each other and may run in any order after EM0.

**Relation to the theory experiment map:** EM1 = E2 revisited under its scoped precondition (unnameable × retrieval-available) and the precondition test for E5 (first conflicts). EM2 completes E1's quality axis. EM0/EM3 are spec-validation, new.

---

## EM0 — Regression Gauntlet (the coverage table, executed)

**Question:** does the rebuilt runtime preserve everything that worked and land every historical failure class where the spec's coverage table says it should (unwritable / prevented / doctor-visible)?

**Runs (n=3 each unless noted):**

| ID | Scenario | Source of truth | Spec prediction |
|---|---|---|---|
| G1 | t06, t15, t09 (probe Phase-2 set) | PROBE_REPORT | converge, plain `converged`, no doctor fire; schema agreement stays 100% via pin flow |
| G2 | E0 d01–d04 (depth/breadth set) | EXPERIMENT_REPORT §1 | convergence 12/12-equivalent; depth distributions overlap E0's; no new failure modes from pin machinery |
| G3 | E1 L3 task verbatim (blind-defer producer) | E1 L3_r1/r2 | the guessed-address wake gate is **rejected at authoring (B2)**; repair feedback lists real pins; agent re-wires in ≤2 repair rounds; run converges with zero doctor involvement |
| G4 | fig1 v3 task verbatim | FIGURE1.md | promotion now legal (A2/A3): promotion runs produce a pin + catalog line; consistency ≥ the 94–96% band; no extralegal writes |
| G5 | catalog integrity audit (piggybacks on G1–G4, no extra runs) | — | every entry has a summary; every catalog line mechanically derivable from circuit+entry; zero orphan entries (data without pin) — the A2 uniform-creation check |

**Pass bar:** G1/G2 no regression (convergence and schema agreement within historical bands); G3 zero blind-defer occurrences, 100% authoring-time rejection; G4 promotion legalized without consistency loss; G5 zero orphans across all runs.
**Failure protocol:** any regression → fix runtime, rerun EM0 in full; do not proceed on a partial pass.

---

## EM1 — The Two-Regime Test (discovery opens the unnameable regime)

**Question:** with a bounded discovery primitive (`list`), does coordination succeed on tasks whose critical dependency has an *unnameable address* — and do emergence and conflicts appear together, as the two-regime theory predicts?

**Design:** fig1-v3-class tasks where decisive data lives at an address the consumer cannot derive (producer names it organically; task text never states it). 3 task variants (the original + 2 new constructions to escape temp-0 clustering: differing domains, same structure). Two arms:

- **Arm A (list-enabled):** full spec runtime.
- **Arm B (list-disabled):** identical, `list` action removed from the harness/action space. B2 still active — so the blind-defer escape is closed and the agent must coordinate through planned interfaces or fail honestly.

n=4 per task per arm (24 runs). Judge + consistency scoring frozen from FIGURE1.md's final scorer.

**Metrics:** content delivery rate of the decisive artifact (headline — fig1 baseline: 96–100% promoted / 51% emergent); consistency score; count of `list`-mediated discoveries (a `list` call whose result is fetched and used downstream — trace-derivable); conflicts (first ever expected here, if anywhere); doctor fires; DEFER/wake usage.

**Pre-registered predictions:**
1. Arm A closes the delivery gap on unnameable-address runs to ≥85% (vs 51% historical).
2. Arm A ≥ Arm B on delivery and consistency; if Arm B matches Arm A, discovery wasn't load-bearing → A6 demoted to convenience, logged honestly.
3. Coupled-regime prediction (falsifiable): any conflict that occurs, occurs in Arm A on an unnameable-address run. Zero conflicts in both arms = the nameable-regime prevention result extends further than theorized → §4 threshold statement strengthens.

**Honest scoping:** serial execution means conflict pressure is still reduced (A′ note); a null conflict result here does not close E5 — it scopes it to "requires concurrency," which is itself a finding.

---

## EM2 — E1 Quality Completion (the crossover's second axis)

**Question:** with the assembly-stub class closed (A5: numeric-family incremental assembly, visible truncation, stubs illegal), does the deep-task quality crossover appear, or do RATD and the replanning planner reach quality parity with the 9× context gap?

**Design:** rerun E1 L3 and L4 only, both systems, n=3 per cell (12 runs). The planner baseline receives the *identical* A5 assembly mechanics (numeric families + index emission) — symmetry is mandatory or the result is confounded. E1 judge and rubrics reused **frozen and untouched** — same rubric versions, same blinding. L1/L2 results carry over from E1 (no change affects shallow cells).

**Metrics:** E1's full set — judge overall per-run, convergence, context chars/decision, truncation events, plan churn (planner), plus new: stub count (must be 0), family completeness (all `section_1..n` present + index).

**Pre-registered readings (declared before any run):**
- Quality crossover at L3/L4 → theory §3 fully confirmed, both axes.
- Quality parity + flat-vs-O(n) context → claim becomes "equal quality at an order of magnitude lower, non-degrading context cost" — a complete and publishable theorem form.
- Planner leads at depth with stubs eliminated → §3's quality prediction is wrong as stated; scope to the cost axis permanently.
**Variance rule inherited from E1:** within-cell sd > 3 on the 10-point judge scale → that cell reports cost axis only.

---

## EM3 — Doctor Validation (healing under induced systemic failure)

**Question:** does the quiescence→dossier→repair loop convert systemic failures into `converged-with-repair`, within its K-bound, without touching healthy runs?

**Design:** blind defer is now unwritable (B2), so doctor pressure must come from the failure classes that remain reachable. Three induced scenarios, n=3 each (9 runs), induction mechanized in the runner (not hand-edited state):

| ID | Induction | Reaches doctor via |
|---|---|---|
| H1 | worker failure injection: one designated leaf's worker call returns a failure (probability 1 on chosen agent) | `failed` → abandonment chain → abandoned pins + dead downstream gates |
| H2 | drop injection: one mid-tree agent dropped after routing (its spawn side-effects stand, its own pins unfulfilled) | abandoned interface pins → unmet root pins |
| H3 | fallback write injection: one integrator's output forced through the schema-mismatch fallback path | fallback-marked write in the failure predicate |

**Metrics:** doctor fire rate (should be 9/9); dossier correctness audit (does the dossier name the true dead gates/abandoned pins — manual check against trace, all 9); repair outcome (`converged-with-repair` rate); repair economy (LLM calls spent by the doctor subtree); K-bound respected (no run exceeds 2 cycles); **false-positive check:** across all EM0–EM2 healthy runs, doctor fires = 0.

**Pass bar:** ≥7/9 healed to `converged-with-repair`; 9/9 dossiers mechanically correct; zero false fires anywhere in the series. Failures of healing (doctor fired, repair didn't converge) are findings, not bugs to hide — they scope C3's privilege level for the next iteration.

---

## Deliverables

```
results/em0/  (per-run traces, catalog audits, regression table)
results/em1/  (per-arm runs, delivery/consistency scores, conflict log, discovery-usage traces)
results/em2/  (rerun cells, judge scores, updated crossover.png — both axes)
results/em3/  (induction configs, dossier audits, healing outcomes)
results/EM_REPORT.md   (verdict per experiment against its pre-registered predictions)
results/THEORY_VS_REALITY.md  (continuous; entries feed theory v1.2)
```

Every prediction above is written before the first run and is not edited after. Disagreement between prediction and result is reported as-is — the EM-series exists to test the spec, and a clean documented miss is a successful test.
