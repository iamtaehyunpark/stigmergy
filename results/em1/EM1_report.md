# EM1 — Two-Regime Test results

- Arm A delivery mean: 3.6%  consistency mean: 1.8%  (n=12)
- Arm B delivery mean: 56.8%  consistency mean: 74.3%  (n=12)
- list-mediated discoveries (Arm A): 28
- conflicts total: 0 (all in Arm A: False)
- doctor fires total: 0

## Pre-registered predictions
1. Arm A delivery >= 85%: **False** (3.6%)
2. Arm A >= Arm B (delivery): **False**; (consistency): **False**; discovery load-bearing: **False**
3. Any conflict occurs in Arm A on an unnameable-address run: **no conflicts (null result — scopes E5 to concurrency)**

| run | arm | task | conv | delivery | consist | list-disc | confl | doctor | defers |
|---|---|---|---|---|---|---|---|---|---|
| m01_r1 | A | m01 | True | 0.0% | 1.2% | 3 | 0 | 0 | 0 |
| m01_r2 | A | m01 | True | 0.0% | 1.2% | 3 | 0 | 0 | 0 |
| m01_r3 | A | m01 | True | 0.0% | 1.2% | 3 | 0 | 0 | 0 |
| m01_r4 | A | m01 | True | 0.0% | 1.2% | 3 | 0 | 0 | 0 |
| m02_r1 | A | m02 | True | 3.3% | 0.0% | 2 | 0 | 0 | 0 |
| m02_r2 | A | m02 | True | 0.0% | 0.0% | 2 | 0 | 0 | 0 |
| m02_r3 | A | m02 | True | 0.0% | 0.0% | 2 | 0 | 0 | 15 |
| m02_r4 | A | m02 | True | 0.0% | 0.0% | 2 | 0 | 0 | 15 |
| m03_r1 | A | m03 | True | 11.5% | 5.7% | 2 | 0 | 0 | 0 |
| m03_r2 | A | m03 | True | 11.5% | 5.7% | 2 | 0 | 0 | 0 |
| m03_r3 | A | m03 | True | 11.5% | 5.7% | 2 | 0 | 0 | 0 |
| m03_r4 | A | m03 | True | 5.8% | 0.0% | 2 | 0 | 0 | 0 |
| m01_r1 | B | m01 | True | 46.9% | 93.0% | 0 | 0 | 0 | 0 |
| m01_r2 | B | m01 | True | 46.9% | 93.0% | 0 | 0 | 0 | 0 |
| m01_r3 | B | m01 | True | 46.9% | 93.0% | 0 | 0 | 0 | 0 |
| m01_r4 | B | m01 | True | 2.9% | 11.6% | 0 | 0 | 0 | 0 |
| m02_r1 | B | m02 | True | 100.0% | 100.0% | 0 | 0 | 0 | 0 |
| m02_r2 | B | m02 | True | 100.0% | 100.0% | 0 | 0 | 0 | 0 |
| m02_r3 | B | m02 | True | 93.8% | 85.7% | 0 | 0 | 0 | 0 |
| m02_r4 | B | m02 | True | 57.1% | 75.0% | 0 | 0 | 0 | 0 |
| m03_r1 | B | m03 | True | 46.9% | 61.4% | 0 | 0 | 0 | 19 |
| m03_r2 | B | m03 | True | 40.6% | 56.1% | 0 | 0 | 0 | 19 |
| m03_r3 | B | m03 | True | 69.0% | 70.0% | 0 | 0 | 0 | 19 |
| m03_r4 | B | m03 | True | 31.2% | 52.6% | 0 | 0 | 0 | 19 |
