"""EM-series experiment harness (RATD_Experiment_Spec_EM.md v1.0).

Drives the rebuilt memory/circuit runtime (src.ratd) through the four
spec-validation experiments:

  em0  Regression Gauntlet    — coverage table executed (G1-G5)
  em1  Two-Regime Test        — list-enabled vs list-disabled (Arm A/B)
  em2  Quality Completion     — L3/L4 quality crossover, A5-symmetric planner
  em3  Doctor Validation      — H1/H2/H3 induced systemic failures

`schema` adapts the new write-once store (entries: address/summary/body)
to the address->text view the frozen Figure-1 / E1 scorers expect, so
those scorers are reused untouched at the rubric level while the
plumbing reads the current schema.
"""
