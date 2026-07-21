# ET_REPORT — The three-arm theory test (v2 substrate)

**Date:** 2026-07-21 · **Runs:** 26 executed (60 pre-registered; two logged
deviations reduced replication after byte-determinism was verified — see
`ET_PREREGISTRATION.md` Deviations) · **Model:** qwen3.6 (Qwen3.6-27B),
temp 0, owned vLLM instance, serial · **Judge:** frozen `prompts/judge_v1.md`
+ `rubrics/et/L1–L5`, system-blind, per-run scores in
`results/et/judge_scores.json` · **Figure:** `results/et/crossover_v2.png`
· **Traces:** `results/et/{arm}_{level}_{rep}/` · **Metrics:**
`results/et/analysis.json`

## Headline table (judge overall · total tokens, per cell)

| Level | P centralized | R RATD multi-round | S RATD single-shot |
|---|---|---|---|
| L1 | 10 · 16k | 10 · 17k | 10 · **3.7k** |
| L2 | 10 · 171k | 10 · 36k | 10 · **11k** |
| L3 | 3 · 2,544k | **5** · 834k | 3 · **313k** |
| L4 | 5† · 3,557k | 3† · 2,215k | 3 · **204k** |
| L5 | 10 · 212k | 10 · 178k | 10 · **94k** |

† systemic failure (P: wall-clock rail, root never done; R: root permanently
stuck on a blind wait). S is the only arm with a clean health sheet (0/9
systemic failures).

## Verdicts on the pre-registered predictions

### P1 (quality crossover: P ≥ R at 1–2, gap closes at 3, R > P at 4–5) — REFUTED

P ≥ R holds trivially at L1–L2 (all arms tie at 10). The rest of the
predicted shape does not occur: R *leads* P at L3 (5 vs 3), P out-scores R
at L4 (5 vs 3, both runs systemic failures), and every arm ties at 10 on
L5. There is no monotone quality crossover in either direction. The quality
axis is dominated by two arm-independent effects: a **completeness wall at
L3–L4** (all arms ship partial assemblies of the book-shaped deliverable;
accuracy/consistency stay at 8–9 while completeness falls to 2–4 — the E1
assembly wall reproduced even though append + commit-by-reference existed
and were used) and a **ceiling at L5** (see honest note below).

### P2 (cost: planner context grows monotonically; R/S stay within 2× of L1 at L5) — CONFIRMED THROUGH L4, REFUTED IN STRICT FORM

Planner per-decision context grows 12.3k → 29.3k → 83.5k → 95.6k chars
(7.8×, monotone L1→L4), with the degradation signature logged (27 truncated
handoffs at L4, max single prompt 264k chars). It then *falls* at L5 (28.4k)
because L5 collapsed to an easy task (below). S ends at 1.73× its L1
context (within the pre-registered 2× bar); R ends at 2.55× (outside the
bar — its L5 window filled with its own solo drafting, not coordination
state). Total tokens separate the arms at every level, S < R < P without
exception: at L4 the spread is **17.5× (P) and 10.9× (R) over S**. The
cost claim survives where coordination was actually exercised (L2–L4); the
strict monotonicity form does not survive a ladder whose difficulty is not
itself monotone.

### P3 (mechanism link: R quality tracks adaptation; P fails where replanning context is largest) — HALF CONFIRMED

The P half holds exactly: P's only hard failure (L4, wall-clock rail) is
its largest-context run, with the most truncated handoffs — the predicted
degradation signature, directly observed. The R half is refuted: R's
adaptation events are 5 at L3 (score 5), 0 at L4 (score 3 — its structure
grew via rules armed *before* new information arrived, and its failure was
a blind wait, not a missing adaptation), 0 at L5 (score 10, solo). R
quality tracked task tractability, not adaptation count.

### P4 (continuity locus, two-sided) — SUBSTRATE READING, WITH ONE LOCALIZED EXCEPTION

S matches R exactly (Δ=0) at four of five levels — L1, L2, L4, L5 — at
1.9–10.9× lower total tokens, and is the only arm never to fail
systemically. R leads S only at L3 (+2, driven by structure/assembly: S
also delivered outside `global/final/`, scored via the flagged fallback).
Of the pre-declared readings this is closest to **"S ≈ R everywhere →
continuity lives in the substrate; agents can be memoryless — the strongest
form of the memory-is-the-machine thesis, and the cheap architecture is the
right one,"** qualified by the L3 exception, which matches the declared
hybrid reading ("in-context continuity is localized to within-competence
revision"). Continuity diagnostics: S ran 34/27/9 self-revive resumes at
L3/L4/L5 with externalized state in up to 7 workspaces — its "rounds" are
visible in the circuit, as designed.

## Honest notes (pre-registered classes and construction misses)

1. **L5 failed as a difficulty step.** Designed for
   decomposition-unknowable-upfront discovery, it was solved at 10/10 by
   all arms — two of them (R, S) *solo, with zero spawns*. The
   contradiction-reconciliation load sits within single-agent competence at
   this model scale, so the intended L4–L5 regime was effectively tested
   only at L4. Any future ET iteration needs a discovery task that exceeds
   solo working-set capacity.
2. **Re-centralization.** Zero non-root spawn edges in all 26 runs. v1's
   recursive delegation was forced by single-shot agent poverty; v2's
   multi-round agents absorb pipelines into rounds, and distributed
   planning *authority* goes unused (details: EMERGENCE_LOG, and
   THEORY_VS_REALITY "rounds substitute for depth").
3. **The r_L4 failure is the v1 blind-defer class, organic on v2:** root's
   wake rule gated on guessed workspace addresses with a wrong agent
   mapping; the surveys→standard→chapters discovery flow it was waiting on
   actually *worked*. Address uncertainty, not timing uncertainty — the
   Figure-1 nameability boundary as scored data.
4. **Byte-determinism:** every multi-rep cell identical (`det_check`);
   replicate variance of the v1 era is now attributed to shared-server
   batching. n=1-equivalent cells are marked in the pre-registration
   deviations; distributional claims are not made.
5. **Success definition:** per the handoff, this is a successful
   experiment: all four predictions received evidence-backed verdicts from
   a fair fight — P1 refuted, P2 confirmed-through-L4/strictly-refuted, P3
   half-confirmed, P4 resolved toward the substrate reading. The clean
   documented miss lands on the theory's quality-crossover mechanism; the
   cost mechanism and the continuity-locus thesis are the survivors.
