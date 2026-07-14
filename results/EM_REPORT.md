# EM-Series Report — verdict per experiment vs pre-registration

Predictions are frozen in `results/EM_PREREGISTRATION.md`. This file
reports results as-is; a documented miss is a successful test of the spec.

## EM0 — Regression Gauntlet
**FAIL** — kill-order gate.

- G1: FAIL — converge, plain converged, no doctor fire
- G2: PASS — convergence, no new failure modes from pin machinery
- G3: PASS — guessed wake gate rejected at authoring; converges w/o doctor
- G4: FAIL — promotion legal-if-present (converged, no extralegal writes, consistency held)
- G5: PASS — zero orphan entries across all runs
- doctor fires in EM0: 1 (organic, on genuinely-failed runs; 0 false fires)

## EM1 — Two-Regime Test

- Arm A delivery 3.6% | consistency 1.8% (n=12)
- Arm B delivery 56.8% | consistency 74.3% (n=12)
- **P1** Arm A delivery ≥85%: False (3.6%)
- **P2** Arm A ≥ Arm B delivery: False; consistency: False; discovery load-bearing: False
- **P3** conflicts total 0; all in Arm A: False
- list-mediated discoveries (Arm A): 28; doctor fires: 0

## EM2 — Quality Completion

- stub_count == 0 across all runs: **True**

- L3: RATD 8.3 vs planner 7.7 — quality parity — 'equal quality at ~an order of magnitude lower, non-degrading context cost'
- L4: RATD 5.0 vs planner 5.0 — quality parity — 'equal quality at ~an order of magnitude lower, non-degrading context cost'

## EM3 — Doctor Validation
**FAIL**

- doctor fire rate: 9/9
- healed (converged-with-repair): 6/9 (bar ≥7)
- dossier mechanically correct: 9/9
- K-bound respected: True
- false fires across healthy runs: 0 of 63 scanned

