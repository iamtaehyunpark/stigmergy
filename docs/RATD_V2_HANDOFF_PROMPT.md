# HANDOFF PROMPT — RATD v2 Rebuild + ET Series

## Context

I am Taehyun Park, University of Wisconsin–Madison. RATD ("Recursive Autonomous Task Distribution") is a decentralized multi-agent architecture: no central planner; agents decide locally whether to execute, spawn other agents, or wait; a shared, agent-authored circuit of trigger rules grows the execution graph during the run.

The previous experimental chain (probe, E-series, EM-series — see `PROBE_REPORT.md`, `EXPERIMENT_REPORT.md`, `EM_REPORT.md`) validated the mechanical substrate but implemented agents as single-shot QA calls, which failed to isolate the theory's causal variable. This build is the corrected realization: **persistent multi-round agents on a redesigned memory/circuit substrate**, followed by the decisive three-arm theory experiment.

## Ground truth documents (read in full, in this order, before writing any code)

1. `RATD_Playground_Spec_v2.md` — the architecture. Authoritative for the runtime.
2. `RATD_Experiment_Spec_ET.md` (v1.1) — the three-arm experiment. Authoritative for the runs.
3. `RATD_Theory.md` — background rationale only; do not implement from it.

This handoff is a summary; the specs win wherever they differ.

## What you are building

**A fresh runtime (`src/ratd_v2/`), not a patch of the v1 code.** Reuse v1 code freely where it matches the new spec (HTTP client, trace/event logging patterns, judge runner), but the agent loop, memory planes, and circuit are new designs — port concepts, not modules.

Core components, per Playground Spec v2:

1. **Agent loop:** persistent multi-round ReAct agents. Each round: build prompt (harness + task/capsule + bounded rolling window + workspace-loaded state) → one LLM call → parse tool calls → execute → append observations. Agent self-declares `done | failed | waiting(condition)`. R_max=30 rounds per agent (rail).
2. **Memory:** K catalog (mechanical index over everything below, bounded queries); W per-agent workspace filesystems (open read across agents); G global memory with linear versioning + head pointers + provenance + divergence flagging (no branch/merge); E external — NOT built.
3. **Circuit:** rules (condition, target, fired-flag, provenance). Conditions are Python boolean expression strings evaluated via restricted-namespace `eval` — namespace contains ONLY the state accessors (`exists`, `head`, `field`, `state`, `children`, `fired`, `matching`, `count`), empty builtins, evaluation timeout. `add_rule` echoes the expression's current truth value back to the author. Firing: re-evaluate on every state event; exactly-once per armed state via atomic CAS; all edits (any agent, any rule, including fired-flag resets) allowed and provenance-logged.
4. **Tools:** exactly the surface in Playground Spec §4. All returns bounded with visible truncation markers. Every call logged (agent, round, args, result size).
5. **Runtime:** serial round-robin over runnable agents. Rails: R_max per agent, global call cap, wall clock (set generous defaults; hitting a rail is a finding, not an error). Quiescence and failure predicate exactly as spec §5 — evaluate and log every run's health verdict. **No doctor. No validators on agent behavior.** Freedom + logging is the design, not an omission.

## The experiment (after the runtime passes smoke tests)

Three arms per `RATD_Experiment_Spec_ET.md`:
- **Arm P:** centralized — one full ReAct planner + ReAct workers (workers = Arm R agents minus `spawn`/`circuit.*`).
- **Arm R:** RATD, multi-round ReAct agents, full tool surface.
- **Arm S:** RATD, single-shot activations (one LLM call per activation, any combination of ops in the emission; continuity via circuit revive + memory only).

5-level task ladder (levels 1–3 adapted from `tasks/e1_ladder.json`; levels 4–5 you construct per spec §2 — decomposition must be unknowable upfront; propose them for my review before freezing). n=4 per arm per level = 60 runs.

## Hard rules

1. **Pre-registration gate:** before the first scored run, write `ET_PREREGISTRATION.md`: the predictions and fair-fight rules copied verbatim from the ET spec, plus hashes/paths of frozen artifacts (all three harness variants + diffs, judge prompt, rubrics, task files, model config). After the first run, none of these change. If a defect forces a change, the affected runs are discarded and rerun; the change is logged in the deviations section.
2. **Fair fight:** same model (`qwen3.6`, temp 0, local vLLM per existing config), same tool implementations, same caps, same harness core across arms. Arm-specific harness text describes only that arm's surface/role. Diff the variants in the pre-registration.
3. **Smoke tests before the ladder:** one level-1 task through each arm end-to-end. Verify: multi-round continuity (an agent using round-2+ information), a circuit rule authored by an agent firing correctly, Arm S revive working, workspace persistence, catalog queries, bounded returns with truncation markers, health verdict logged. Fix and iterate freely here — this phase is exempt from the freeze.
4. **Logging is the product:** full per-round traces (prompt sizes, tool calls, results), every circuit edit with before/after, every state event. The ET metrics (§3) and the emergence inventory must be computable from traces alone.
5. **Maintain `results/THEORY_VS_REALITY.md` continuously** — every place the spec under-determined something you had to decide, every model behavior contrary to assumption. Highest-value deliverable, as always.
6. **Judging:** reuse the frozen E1 judge/rubrics for levels 1–3; write rubrics for 4–5 before the freeze; system-blind; per-run scores published.
7. Never overwrite harness/prompt versions. Version everything, keep the iteration log.

## Order of work

1. Read the three ground-truth docs end to end.
2. Build the v2 runtime; smoke tests (rule 3).
3. Construct level 4–5 tasks + rubrics; submit for review.
4. Freeze: write `ET_PREREGISTRATION.md`.
5. Run the 60-run ladder (order: interleave arms within level, level 1 → 5).
6. Judge; compute metrics; render `crossover_v2.png` (quality + cost panels, v2 measurement definition stated on-figure).
7. Write `ET_REPORT.md`: verdict per prediction (P1–P4), as-is; `EMERGENCE_LOG.md`: the observational inventory of what unrestricted agents actually did.

## Success definition

Not "RATD wins." Success = all four pre-registered predictions receive evidence-backed verdicts from a fair fight, plus a complete emergence inventory. A clean documented miss is a successful experiment — this time it happens to the theory's actual mechanism.
