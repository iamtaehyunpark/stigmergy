# RATD Experiment Spec — EF Series (The Frame Experiment)
## v1.0 — What controls delegation propensity: harness frame, action space, or both?

**Runs on:** v2 playground runtime, Arm S architecture only (single-shot activations). No runtime changes; both factors are harness/tool-surface configurations.
**Motivating anomaly (ET + E0, same model):** v1 single-shot agents delegated richly (E0: 69/69 SPAWNs valid, depth to 8, 25-agent graphs). v2 Arm S single-shot agents: zero non-root spawns in all runs. Two things changed simultaneously: (1) the **frame** — v1's harness posed routing as the agent's identity ("choose EXECUTE / SPAWN / DEFER" as the mandatory first decision); v2's harness lists spawn as one tool among many and says "work on your task." (2) the **action space** — v2 added self-continuation (wait/self-revive via circuit), a substitute channel for acquiring more compute that v1 lacked. This experiment disentangles them.

**Question:** is delegation at this model scale a prompted disposition (frame-causal), a compensation for activation poverty (action-space-causal), or an interaction?

---

## 1. Design: 2×2, Arm S only

| | **Revive available** (v2 S as-run) | **Spawn-only** (revive/wait removed from tool surface) |
|---|---|---|
| **Neutral frame** (v2 harness as-run) | Cell NN — ET baseline, replicates s_L3/s_L4 behavior | Cell NS |
| **Router frame** (routing posed first) | Cell RN | Cell RS — closest analog to v1's regime |

- **Router frame text (the treatment):** the harness opens each activation with the routing question, v1-style: "You have been assigned ONE task. First decide how it should be handled: complete it yourself in this activation, DELEGATE parts to new agents (spawn), or WAIT on missing state. Then act on your decision." Tool surface identical to the cell's column; only the frame differs. Full harness diffs frozen in pre-registration.
- **Spawn-only column:** `wait` and self-targeting rule authorship removed from the documented tool surface (runtime unchanged; undocumented calls would be tool errors, logged if attempted — itself a finding).
- All other conditions frozen at ET values: qwen3.6, temp 0, owned serial endpoint, same caps/rails, same memory planes.

## 2. Tasks (2, chosen for historical anchors)

- **T1 = ET L3 task verbatim** — the level where S ran 34 self-revives and zero spawns; direct continuity with the anomaly.
- **T2 = E0 d02 (business plan) adapted to v2 memory conventions** — the task class where v1 produced its richest delegation (depth 8); the strongest historical delegation anchor.

n=1 per cell per task (byte-determinism verified on this endpoint; det_check re-run per cell) = **8 runs**. If any cell shows nondeterminism, n=2 for that cell.

## 3. Metrics

- **Headline: delegation behavior** — non-root spawn count; spawn events at any depth; resulting graph shape (agents, depth, rule-spawned waves vs direct spawns). Quality is secondary (the assembly wall flattens it at T1; record judge scores for completeness but no prediction rides on them).
- **Substitution diagnostics:** self-revive count (where available); attempted-but-undocumented tool calls (NS/RS cells); per-activation context; total tokens.
- **Behavioral trace reads:** for each root and each non-root agent, does the activation *consider* delegation (mentions/weighs it in output) even where it doesn't spawn? Manual annotation, all 8 runs — cheap at this scale and it separates "considered and declined" from "never considered."

## 4. Pre-registered predictions and readings

- **P1 (frame effect):** router-frame cells (RN, RS) show non-root delegation > 0; neutral cells stay at ~0. If RN alone restores delegation (revive still available), frame is causal *independent of action space* — "delegation is a prompted disposition, not an emergent choice" enters the paper as mechanism.
- **P2 (action-space effect):** spawn-only cells (NS, RS) show more delegation than their revive row-mates. If NS restores delegation without the frame, v1's delegation was compensation for activation poverty, and re-centralization is the honest equilibrium of self-continuing agents.
- **P3 (interaction, the expected outcome):** RS ≫ all, RN and NS intermediate — frame sets the disposition, self-continuation sets the substitution price. Reported as the two-factor mechanism.
- **Null reading declared:** zero delegation in all four cells → neither factor explains the v1↔v2 gap; remaining candidates (task framing via capsule text, validator-forced participation rule in v1, model-version drift) get listed for a follow-up, and the paper reports re-centralization as robust to both manipulations.
- **Behavioral-consideration reading:** if neutral cells show "considered and declined" in traces, re-centralization is a *choice*; if delegation is never mentioned, it is a *blind spot* — different sentences in the paper, both honest.

## 5. Deliverables

```
EF_PREREGISTRATION.md           (this file's predictions + frozen harness diffs + det_check)
results/ef/{cell}_{task}/        (full traces)
results/ef/EF_REPORT.md          (verdict per prediction; delegation table; annotation sheet)
results/THEORY_VS_REALITY.md     (continuous)
```

## 6. Placement

Runs before the theory v2.0 rewrite and the paper. Whatever the outcome, the re-centralization section upgrades from observation to mechanism — the ET story's one loose thread, closed for ~8 runs.
