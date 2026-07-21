# EMERGENCE_LOG — observational inventory (ET series, 26 runs)

What unrestricted agents actually did. Logged, not judged; computed from
traces (`results/et/analysis.json` + per-run `trace.jsonl`). Raw material
for the next design cycle.

## Structure

- **Zero non-root spawn edges in all 26 runs.** Every agent in every arm
  was created by root (directly or via a root-authored rule). v1's
  recursive delegation did not reappear once agents became multi-round:
  children absorb pipelines into rounds. Distributed planning authority
  went entirely unused where granted (R, S).
- **Rule-spawned agent waves (root-authored):** r_L4 grew six agents via
  condition-triggered rules (surveys → standard → chapters), s_L3 two.
  The execution graph does grow mid-run through the circuit — authorship
  just never leaves root.
- **Solo solves at the extremes:** L1/L2 (R, S) and L5 (R: 18 rounds solo;
  S: 10 activations solo). Facing the most intricate task, both
  decentralized arms chose zero delegation.

## Coordination & failure events

- **Organic blind-wait (r_L4, systemic failure):** root gated assembly on
  guessed workspace paths with an off-by-one agent mapping
  (`agents/a5/chapter_1_final.md`; a5 was the standard synthesizer). The
  discovery flow it awaited had succeeded. The v1 E1 blind-defer class,
  reproduced organically on v2 — address uncertainty is untouched by
  `exists()` gating, and the authoring-time truth echo ("currently False")
  cannot distinguish wrong-address-forever from not-yet.
- **P degradation signature (p_L4, wall-clock rail):** planner reached
  264k-char single-round prompts; 27 of 51 cross-agent handoffs arrived
  truncated (vs R 14/29, S 0/5 at the same level). Reads-are-grants
  pressure concentrates in the centralized arm exactly as context grows.
- **Arm S self-revive chains as the coordination fabric:** 34/27/9 resumes
  at L3/L4/L5; externalized state in up to 7 workspaces per run. S's
  entire continuity ran through the circuit + workspaces; it is also the
  only arm with zero systemic failures across the ladder.
- **Delivery-location drift:** s_L3, s_L4, and p_L4 published deliverables
  outside `global/final/` (judged via the flagged fallback extraction).

## Dogs that did not bark (ladder runs)

- Zero cross-workspace writes (the one smoke-phase cross-workspace repair
  did not recur), zero divergence flags, zero duplicate-commit paths, zero
  rule edits by non-authors, zero rule-evaluation errors, zero
  fired-flag resets. The permissive surfaces (edit anyone's rules, write
  anywhere) went unused under fair-fight conditions — the anticipated
  anarchy never materialized.
- Zero rail hits except p_L4's wall clock; no run touched the 300-call
  rail (post-freeze).

## Infrastructure observations

- **Byte-determinism** of every multi-rep cell on the owned serial
  endpoint (det_check: 8/8 multi-rep cells, 1 distinct outcome each) —
  v1-era replicate variance is now attributed to shared-server batching.
- Judge pipeline: 26/26 runs scored, 0 auto-1 fallbacks for invalid judge
  output; 3 runs used fallback artifact extraction (flagged above).
