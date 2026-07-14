# EM0 — Regression Gauntlet results

- **G1**: FAIL — converge, plain converged, no doctor fire
- **G2**: PASS — convergence, no new failure modes from pin machinery
- **G3**: PASS — guessed wake gate rejected at authoring; converges w/o doctor
- **G4**: FAIL — promotion legal-if-present (converged, no extralegal writes, consistency held)
- **G5**: PASS — zero orphan entries across all runs
- doctor fires across EM0: 1 (organic, on genuinely-failed runs: t15_r3 [failed])
- **overall: FAIL**

| group | run | outcome | conv | doctor | promo | confl | wrej | blind-rej | consist | catalog |
|---|---|---|---|---|---|---|---|---|---|---|
| G1 | t06_r1 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G1 | t06_r2 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G1 | t06_r3 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G1 | t09_r1 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G1 | t09_r2 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G1 | t09_r3 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G1 | t15_r1 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G1 | t15_r2 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G1 | t15_r3 | failed | False | 2 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d01_r1 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d01_r2 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d01_r3 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d02_r1 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d02_r2 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d02_r3 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d03_r1 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d03_r2 | converged | True | 0 | 0 | 0 | 0 | 0 | 0.00% | clean |
| G2 | d03_r3 | converged | True | 0 | 0 | 0 | 0 | 0 | 0.00% | clean |
| G2 | d04_r1 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d04_r2 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G2 | d04_r3 | converged | True | 0 | 0 | 0 | 0 | 0 | n/a | clean |
| G3 | L3_r1 | converged | True | 0 | 0 | 0 | 0 | 0 | 0.00% | clean |
| G3 | L3_r2 | converged | True | 0 | 0 | 0 | 0 | 0 | 0.00% | clean |
| G3 | L3_r3 | converged | True | 0 | 0 | 0 | 0 | 0 | 0.00% | clean |
| G4 | f01_r1 | converged | True | 0 | 0 | 0 | 0 | 0 | 1.16% | clean |
| G4 | f01_r2 | converged | True | 0 | 0 | 0 | 0 | 0 | 1.16% | clean |
| G4 | f01_r3 | converged | True | 0 | 0 | 0 | 0 | 0 | 2.33% | clean |
