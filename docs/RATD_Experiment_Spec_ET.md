# RATD Experiment Spec — ET Series (The Theory Test)
## v1.1 — The decisive experiment: three arms, two causal variables

**Runs on:** Playground Spec v2.0 runtime.
**The questions:** (1) does distributing planning into executing agents — each deciding locally whether to continue or deploy others, with the execution structure emerging during the run — outperform or out-scale a centralized planner, *when agent capability is held identical*? (2) does agent continuity need to live in the model's context at all (multi-round ReAct), or can the substrate carry it (single-shot activations over shared memory + circuit revive) at lower cost — the memory-is-the-machine thesis, tested directly?

Everything in this file is frozen before the first run (`ET_PREREGISTRATION.md` copies the predictions and pass bars verbatim, plus frozen artifact hashes). Results go in `ET_REPORT.md` as-is.

---

## 1. The three arms (two causal variables isolated)

The design is a 2-variable ablation: **planning locus** (centralized vs distributed) and **continuity locus** (in-context vs in-substrate).

**Arm P (Centralized planner):** one planner agent + worker agents.
- The **planner** is a full multi-round ReAct agent. It decomposes, assigns tasks to workers, monitors their outputs, and replans as often as it wants. It is the only entity that may create workers or define execution order.
- **Workers** are byte-identical to Arm R agents in model, harness core, round cap, and memory tools — but their tool surface excludes `spawn` and `circuit.*` (that exclusion IS the planning treatment). They read/write the same K/W/G memory, verify their own work, and report to the planner.
- Replanning mechanics: after any worker completes/fails, the planner runs a round with accumulated state. Its context management is its own problem — exactly the theory's point — but it has the same per-round context window bounds and the same memory tools to externalize state if it chooses. A smart planner may build its own catalog discipline; that is allowed and would be an honest strong baseline.

**Arm R (RATD, multi-round):** agents have the full v2 tool surface *including* `spawn`, `circuit.*`, `wait`. The root agent receives the task; everything else emerges. Continuity lives **in-context** (the ReAct loop).

**Arm S (RATD, stigmergic single-shot):** same distributed planning as Arm R, but every agent activation is exactly **one LLM call** — emit one action document (memory ops + circuit ops + spawns + wait-condition, any combination), then the activation ends. Continuity lives **in-substrate**: re-activation via circuit rules (wake/revive), working state via workspace/global memory, "multi-round" realized as a chain of cheap stateless activations over shared state. This is the v1 agent model re-hosted on the v2 substrate — the interpretation that circuit-ruled spawn/revive IS multi-round, made testable. Activation count is bounded by the same global call rail (no per-agent round cap applies; the rail is the bound).

**What each comparison isolates:** P vs R = the theory's planning claim under faithful agents. R vs S = where continuity must live (in-context vs in-substrate) — the "memory is the machine" thesis directly. P vs S = the original E1/EM2 comparison, now on clean v2 footing.

**FAIR-FIGHT RULES (pre-registered, violations invalidate the run):**
1. Same model, same temperature, same global call rail, same wall-clock rail per run. Round cap R_max applies per multi-round agent (Arms P, R); Arm S is bounded by the call rail alone.
2. Same memory planes, same tool implementations, same bounded-return caps, all three arms.
3. Same harness core text (tool docs + behavioral guidance); arm-specific text limited to describing the arm's own tool surface, activation model, and role. All three harness variants frozen and diffed in the pre-registration.
4. Same judge, same rubrics, frozen before run 1, system-blind, per-run scores published.
5. Neither arm receives task-specific hints, decomposition templates, or worked examples.

## 2. Task ladder

Five levels, scaling size/depth/discoverability. Levels 1–3 adapted from the E1 ladder (comparability with the v1-era results, re-scored fresh). Levels 4–5 new, constructed so that **the correct decomposition is unknowable upfront**: decisive information surfaces only from intermediate work (the class the theory predicts wins on — e.g., a corpus-analysis task where the right split emerges from a survey step; a spec-then-build task where requirements discovered mid-run change structure).

n = 4 runs per arm per level (temp-0 nondeterminism gives natural variance; distributions reported). 60 runs + judging.

## 3. Metrics

- **Quality:** frozen judge, 10-pt rubric per level (headline).
- **Cost (now three-way, and central):** per-activation context size distribution; total LLM calls; **total tokens per run** (the S-vs-R economics: many cheap calls vs fewer growing-window calls); wall-clock.
- **Scaling signature:** planner per-round context growth vs level (the O(n) curve) against Arm R and Arm S per-activation context vs level — under the §6 v2 measurement definition, stated on the figure. Arm S's per-activation context is the strictest bounded form; report it on the same panel.
- **Adaptation:** count + timing of structure changes after new information (Arms R/S: spawns/rule-edits after the first activation of any agent; Arm P: replans that alter remaining assignments). Levels 4–5 exist to make this metric decisive.
- **Continuity-locus diagnostics (R vs S):** where iteration happens — within-agent rounds (R) vs circuit-expressed loops (S: reviewer/reviser chains, self-revive patterns); externalized-state size per agent; content-delivery metrics on every cross-activation handoff (the reads-are-grants law applies with full force to Arm S, whose every "round boundary" is a delivery channel).
- **Emergence inventory (observational, no prediction):** circuit edits by non-authors, cross-workspace writes, spontaneous coordination patterns, duplicate work incidents, divergent G versions and how agents resolved them. Raw material for the next design cycle — logged, not judged.
- **Health:** convergence, failure-predicate verdicts (doctor off, predicate logging on), rail hits.

## 4. Pre-registered predictions

- **P1 (crossover):** Arm P ≥ Arm R at levels 1–2; gap closes at 3; Arm R > Arm P at 4–5 on quality, driven by adaptation events.
- **P2 (cost):** planner per-round context grows monotonically with level; Arms R and S per-activation context stay flat (within 2x of their level-1 values at level 5).
- **P3 (mechanism link):** in levels 4–5, Arm R quality correlates with adaptation-event count; Arm P failures concentrate where replanning context is largest (truncation/degradation signatures logged).
- **P4 (continuity locus, two-sided by design):** Arm S matches Arm R (within 1 judge point) on decomposition-shaped levels (1–3) at lower total tokens; Arm R leads on iteration-heavy levels (4–5). Declared readings: S ≈ R everywhere → continuity lives in the substrate; agents can be memoryless — the strongest form of the memory-is-the-machine thesis, and the cheap architecture is the right one. R > S only on iteration-heavy tasks → in-context continuity is localized to within-competence revision; hybrid architecture indicated. R > S everywhere → the agent model, not the substrate, was the binding constraint; the v2 redesign is vindicated and Arm S retires.
- **Honest readings declared in advance:** P1 fails but P2 holds → the claim is cost-scaling, not quality (the EM2 parity form, now under faithful agents — still publishable). P1 and P2 both fail → the theory's advantage does not survive faithful agent models at this scale; report as-is. Arm P's planner spontaneously *simulating* decentralization (delegating planning to workers via prose instructions) → logged as a finding about the pressure toward decentralization, arm still scored as centralized.
- **Variance rule:** within-cell sd > 3 on the judge scale → that cell reports cost + adaptation axes only.

## 5. Deliverables

```
ET_PREREGISTRATION.md          (frozen predictions + artifact hashes, before run 1)
results/et/{arm}_{level}_{rep}/ (full traces: every round, every tool call, every circuit edit)
results/et/judge_scores.json
results/et/crossover_v2.png    (quality + cost panels, v2 measurement definition stated)
results/et/EMERGENCE_LOG.md    (the observational inventory)
ET_REPORT.md                   (verdict vs each prediction, as-is)
results/THEORY_VS_REALITY.md   (continuous)
```

A clean documented miss on P1 is a successful experiment. The point is that whatever happens, it happens to *the theory's actual mechanism* this time.
