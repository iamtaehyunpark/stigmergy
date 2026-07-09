# HANDOFF PROMPT — RATD Feasibility Probe

## Context

I am Taehyun Park, University of Wisconsin–Madison. I am validating the feasibility of a decentralized multi-agent architecture ("Recursive Autonomous Task Distribution") in which there is no central planner: agents choose EXECUTE / SPAWN / DEFER locally, and an executable shared memory (trigger conditions over entry status) grows the execution graph recursively.

**Ground truth specification:** `RATD_Probe_Spec.md` in the project root. Read it in full before writing any code — it contains the complete harness prompt, the 20-task probe set, scoring rubrics, the minimal runtime design, metrics, and the deliverables checklist. This handoff prompt is a summary; the spec is authoritative wherever they differ.

**Theory background (consult for rationale only, do not implement from it):** `RATD_Theory.md`.

## What this is and is not

This is a FEASIBILITY probe, not a performance experiment. The purpose is to answer three kill-order questions about LLM behavior:

- **Q1:** Given the spawn action, does an LLM route sensibly? (Phase 1 — no runtime, just prompted calls + scoring.)
- **Q2:** Do trigger conditions compose across independently-generated agents — do namespace/key strings actually match? (Phase 2.)
- **Q3:** Does a full recursive run converge on a multi-level task within budget? (Phase 2.)

Accordingly: NO async, NO real parallelism, NO Observers, NO conflict resolution (only conflict *logging*), NO retrieval models, NO fine-tuning. Sequential single-threaded execution is correct and intended. Keep Phase 2 at 300–500 lines.

## Hard rules

1. **Phase gating:** Build and fully evaluate Phase 1 first. If Phase 1 fails its pass bar after at most 3 harness iterations (spec §1.6), STOP, write `results/phase1/FAILURE_REPORT.md`, and do not build Phase 2.
2. **Never overwrite harness versions** — save `harness_v1.md`, `v2.md`, ... with an iteration log.
3. **Safety rails are mandatory:** max 60 LLM calls per Phase-2 run, max depth 6, 20-minute wall clock. Hitting a rail is a recorded finding, not an error to engineer around.
4. **Budget is enforced in code**, never trusted from model output.
5. **Exactly-once trigger firing** via atomic `UPDATE ... WHERE fired=0` (spec §2.2).
6. **Maintain `results/THEORY_VS_REALITY.md` continuously.** Every place the spec/theory hand-waved something the implementation forced you to decide, or the model behaved contrary to assumption, gets an entry. This file is the single highest-value deliverable — treat it as first-class, not an afterthought.
7. Model calls: temperature 0, model name in one config variable (default `claude-sonnet-4-6`). Log model + version in README.

## Order of work

1. Read `RATD_Probe_Spec.md` end to end.
2. Implement the Phase 1 probe runner (harness + 20 tasks → 20 JSON action documents + automated scoring per spec §1.5).
3. Run, score, iterate the harness per §1.6 until pass bar or v4.
4. If passed: implement the Phase 2 minimal runtime (SQLite memory + trigger table + sequential loop + Graphviz trace rendering, spec §2.2).
5. Run the 3 Phase-2 tasks × 2 repetitions; compute metrics per §2.4.
6. Produce final README with Q1/Q2/Q3 verdicts (YES / NO / PARTIAL, one paragraph each, evidence pointers) and the full deliverables checklist from the spec.

## Success definition

Not "the system performs well" — success is that all three questions receive an evidence-backed answer, whatever the answer is. A clean, well-documented NO on Q1 is a fully successful outcome of this probe.
