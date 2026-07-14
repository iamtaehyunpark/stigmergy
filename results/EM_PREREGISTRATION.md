# EM-Series Pre-Registration (frozen 2026-07-13, before the first run)

Per `docs/RATD_Experiment_Spec_EM.md` v1.0: "Every prediction above is
written before the first run and is not edited after. Disagreement
between prediction and result is reported as-is." This file freezes the
predictions and the frozen artifacts; results go in `EM_REPORT.md`, never
here.

## Frozen artifacts (versioned before first run)

- Runtime: `src/ratd/` (spec v1.0 rebuild) + `src/ratd/induction.py`.
- Harnesses: `prompts/harness_v7.md` (Arm A / default), `prompts/harness_v7_nolist.md` (Arm B).
- Worker: `prompts/worker_v7.md`. Doctor: `prompts/doctor_v1.md`.
- Judge: `prompts/judge_v1.md` + `rubrics/L1..L4.md` — reused **frozen and untouched** from E1.
- Figure-1 consistency scorer: `src/figure1_score.py` (rubric-level logic frozen; EM reads it via `src/em/schema.py`).
- Model: local `qwen3.6`, temp 0, JSON-constrained.
- Tasks: `tasks/em1_tasks.json` (m01=fig1-v3 f01 verbatim, m02 genomics, m03 smart-building), `tasks/e1_ladder.json` (L3/L4), `tasks/phase1_tasks.json`, `tasks/e0_tasks.json`, `tasks/figure1_v3.json`.

## EM0 — Regression Gauntlet (pass bars)

- **G1** (t06/t15/t09): converge, plain `converged`, no doctor fire; schema agreement stays 100% via pin flow.
- **G2** (d01–d04): convergence 12/12-equivalent; no new failure modes from pin machinery; depth distributions overlap E0's.
- **G3** (L3): the guessed-address wake gate is **rejected at authoring (B2)**; zero blind-defer occurrences; 100% authoring-time rejection; converges with zero doctor involvement.
- **G4** (fig1 v3 f01): promotion legal (pin + catalog line); consistency ≥ the 94–96% band; no extralegal writes.
- **G5** (catalog audit, piggyback): zero orphan entries; every entry has a summary; every catalog line mechanically derivable.
- **Failure protocol:** any regression → fix runtime, rerun EM0 in full; do not proceed on a partial pass.

## EM1 — Two-Regime Test (pre-registered predictions)

1. Arm A closes the delivery gap on unnameable-address runs to **≥85%** (vs 51% historical emergent / 96–100% promoted).
2. Arm A ≥ Arm B on delivery and consistency. If Arm B matches Arm A, discovery wasn't load-bearing → A6 demoted to convenience, logged honestly.
3. Coupled-regime (falsifiable): any conflict that occurs, occurs in **Arm A on an unnameable-address run**. Zero conflicts in both arms = the nameable-regime prevention result extends further than theorized; §4 threshold statement strengthens.
- **Honest scoping:** serial execution reduces conflict pressure; a null conflict result scopes E5 to "requires concurrency" — itself a finding, not a closure.

## EM2 — Quality Completion (pre-registered readings)

- Quality crossover at L3/L4 (RATD leads) → theory §3 fully confirmed, both axes.
- Quality parity + flat-vs-O(n) context → "equal quality at an order of magnitude lower, non-degrading context cost" — complete, publishable theorem form.
- Planner leads at depth with stubs eliminated → §3's quality prediction is wrong as stated; scope to the cost axis permanently.
- **Symmetry (mandatory):** planner receives identical A5 mechanics (`src/em/em2_planner.py`: numeric families + 12k cap + visible truncation). **stub_count must be 0** for both systems.
- **Variance rule (inherited from E1):** within-cell sd > 3 on the 10-pt judge scale → that cell reports the cost axis only.

## EM3 — Doctor Validation (pass bar)

- Doctor fire rate 9/9; **≥7/9** healed to `converged-with-repair`; **9/9** dossiers mechanically correct; K-bound (≤2) respected everywhere.
- **False-positive check:** across all EM0–EM2 healthy runs, doctor fires = **0**.
- Induction is mechanized in the runner (`src/ratd/induction.py`), not hand-edited state: H1 worker-failure, H2 drop-after-spawn, H3 fallback-write.
- Failures of healing (doctor fired, repair didn't converge) are **findings**, not bugs — they scope C3's privilege level for the next iteration.

## Kill-order

EM0 gates everything; if the rebuild regresses, stop. EM1–EM3 are independent and may run in any order after EM0.
