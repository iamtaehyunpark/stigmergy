# EM-Series Runbook

Implements `docs/RATD_Experiment_Spec_EM.md` v1.0. All runs need the local
`qwen3.6` endpoint (set `RATD_LOCAL_ENDPOINT`, or pass `--local-endpoint`).
Predictions are frozen in `results/EM_PREREGISTRATION.md` (do not edit after
the first run). Every runner is resumable — a completed run leaves a
`metrics.json` sentinel and is skipped on rerun; delete its dir to redo it.

Kill-order: **EM0 gates everything.** EM1–EM3 are independent after EM0.

## EM0 — Regression Gauntlet (n=3 each)
```
python3 -m src.em.em0 --out-dir results/em0            # G1–G4 run + G5 audit
python3 -m src.em.em0 --out-dir results/em0 --audit-only   # re-audit, no model
```
Pass: G1/G2 no regression; G3 zero blind-defer + 100% authoring-time rejection;
G4 promotion legal, consistency ≥94%; G5 zero orphan entries; doctor false fires 0.

## EM1 — Two-Regime Test (Arm A vs Arm B, n=4 × 3 tasks = 24)
```
python3 -m src.em.em1 --out-dir results/em1            # both arms
python3 -m src.em.em1 --out-dir results/em1 --score-only
```
Arm A = `harness_v7.md` + list on; Arm B = `harness_v7_nolist.md` + list off.
Headline: decisive-artifact delivery (Arm A ≥85%, Arm A ≥ Arm B), consistency,
list-mediated discoveries, conflicts, doctor fires.

## EM2 — Quality Completion (L3/L4, both systems, n=3 = 12)
```
python3 -m src.em.em2 --out-dir results/em2           # RATD + A5-symmetric planner + judge
python3 -m src.em.em2 --out-dir results/em2 --score-only   # re-judge only
```
Planner gets identical A5 mechanics (`em2_planner.py`). Judge + rubrics frozen
from E1. Reports quality crossover / parity / planner-leads per the variance
rule; stub_count must be 0.

## EM3 — Doctor Validation (H1/H2/H3, n=3 = 9)
```
python3 -m src.em.em3 --out-dir results/em3           # induced failures, on L3
python3 -m src.em.em3 --out-dir results/em3 --audit-only
```
Inductions are mechanized in `src/ratd/induction.py`. Pass: ≥7/9 healed to
`converged-with-repair`, 9/9 dossiers mechanically correct, K-bound ≤2, and
**zero** doctor false fires across every healthy EM0–EM2 run.

## Assemble the report
```
python3 -m src.em.report --results-dir results        # writes results/EM_REPORT.md
```
Maintain `results/THEORY_VS_REALITY.md` continuously as findings surface.
