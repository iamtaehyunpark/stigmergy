# EM3 — Doctor Validation results

- doctor fire rate: 9/9
- healed (converged-with-repair): 6/9
- dossier mechanically correct: 9/9
- K-bound (<=2) respected: True
- false fires across healthy EM0-EM2 runs: 0 (of 63 scanned)
- **pass bar met: False**

| run | mode | target | fired | outcome | healed | dossier✓ | K✓ | subtree calls |
|---|---|---|---|---|---|---|---|---|
| L3_H1_r1 | H1 | root.1 | True | converged-with-repair | True | True | True | 2 |
| L3_H1_r2 | H1 | root.5 | True | converged-with-repair | True | True | True | 2 |
| L3_H1_r3 | H1 | root.5 | True | converged-with-repair | True | True | True | 2 |
| L3_H2_r1 | H2 | root.1 | True | converged-with-repair | True | True | True | 8 |
| L3_H2_r2 | H2 | root.1 | True | converged-with-repair | True | True | True | 10 |
| L3_H2_r3 | H2 | root.1 | True | converged-with-repair | True | True | True | 9 |
| L3_H3_r1 | H3 | root.4 | True | failed | False | True | True | 8 |
| L3_H3_r2 | H3 | root.4 | True | failed | False | True | True | 12 |
| L3_H3_r3 | H3 | root.4 | True | failed | False | True | True | 12 |
