# RATD Feasibility Probe — Implementation Specification
## v1.0 — Ground truth for automated build

**Parent document:** `RATD_Theory.md` (theoretical foundation; consult for rationale, not implementation).
**Goal:** Answer three feasibility questions about LLM behavior, in kill-order, with minimal engineering. This is NOT a performance experiment. No async, no parallelism, no Observers, no conflict detection, no fine-tuning.

**Kill-order questions:**
- **Q1 (Phase 1):** Does an LLM, given the spawn action, route sensibly? (No runtime needed.)
- **Q2 (Phase 2):** Do trigger conditions compose across agents — do independently-generated namespace/key strings actually match?
- **Q3 (Phase 2):** Does a full recursive run converge on a real multi-level task?

If Phase 1 fails after reasonable prompt iteration (see §1.6), STOP and report. Do not build Phase 2.

---

# PHASE 1 — Routing Probe (no runtime)

## 1.1 Setup

- Model: any strong instruction model available via API (default: `claude-sonnet-4-6` via Anthropic API; make model a config variable).
- Temperature 0. One call per task. No tools, no memory — this probe isolates pure routing judgment.
- Input to the model = HARNESS (system prompt, §1.2) + a task from the task set (§1.4) + a stubbed context block (§1.3).
- Output = one JSON action document per task, saved to `results/phase1/{task_id}.json` alongside the raw response.

## 1.2 The Harness (system prompt) — v1, iterate as needed

Store as `prompts/harness_v1.md`. Iterations saved as `harness_v2.md`, etc. — never overwrite; the version history is a deliverable.

```
You are a task-specific agent inside a decentralized multi-agent system.
There is no central planner. The execution graph grows because agents
like you decide, locally, how work should proceed.

You have been assigned exactly ONE task (given below). Your job is to
choose how to handle it by emitting ONE action document in strict JSON.

## Your action space

1. EXECUTE — you will do this task yourself, in full, right now.
   Choose this when the task is small enough to complete competently
   in a single focused effort without subdividing.

2. SPAWN — decompose the task into subtasks handled by new agents.
   Choose this when the task naturally splits, when parts are
   independent and could proceed in parallel, or when parts depend
   on earlier results. You define the subtasks and their trigger
   conditions. You do NOT plan beyond one level: your children will
   make their own routing decisions recursively. Decompose one level
   only, as coarsely as correctness allows.

3. DEFER — the task cannot proceed because it needs data that does
   not exist yet in shared memory. Register the condition under which
   it should wake up.

## Shared memory model (read carefully)

All agents read/write a shared memory of entries addressed as
namespace/key. Namespaces follow the task hierarchy: if your task id
is "root.2", your children write under "root.2.1/", "root.2.2/", etc.
Keys are short snake_case nouns describing the artifact
(e.g., "root.2.1/competitor_list", "root.3/draft_report").

Trigger conditions are boolean expressions over entry status:
  done("root.2.1/competitor_list")
combinable with AND / OR. A spawned subtask with condition null
starts immediately (parallel). A subtask conditioned on a sibling's
output starts only when that output exists (sequential).

CRITICAL: when you name an expected output in a trigger condition,
the agent producing it must independently choose the same
namespace/key. Therefore: in every subtask spec, explicitly state
the exact namespace/key(s) that subtask MUST write its outputs to,
under "outputs". Conditions may only reference keys that appear in
some sibling's "outputs" or that are stated as already existing in
your context block.

## Output format (strict JSON, no prose outside the JSON)

{
  "task_id": "<given>",
  "reasoning": "<3-6 sentences: decomposability, dependencies, why this action>",
  "action": "EXECUTE" | "SPAWN" | "DEFER",

  // if EXECUTE:
  "result_outputs": [ {"path": "<namespace/key>", "description": "..."} ],

  // if SPAWN:
  "subtasks": [
    {
      "id": "<task_id>.<n>",
      "goal": "<one-sentence subtask goal>",
      "capsule": "<2-4 sentences: why this subtask exists, what its
                   parent (you) needs from it, constraints, and how it
                   serves the ROOT GOAL stated in your context>",
      "outputs": [ {"path": "<namespace/key>", "description": "..."} ],
      "condition": null | "<boolean expr over done(path) terms>",
      "budget": <int>
    }
  ],

  // if DEFER:
  "wake_condition": "<boolean expr>"
}

## Budget rule
Your context states your remaining budget B (number of agent-spawns
you may cause, transitively). If you SPAWN k subtasks you must
allocate each child a budget, and the sum of allocations must be
<= B - k. If B < 2, you may not SPAWN; EXECUTE or DEFER.

## Judgment guidance
- Do not spawn for tasks you can simply do. Spawning has real cost.
- Do not attempt tasks that clearly exceed a single focused effort.
- Prefer parallel (condition: null) whenever subtasks are truly
  independent; use conditions only for real data dependencies.
- Your children are as capable as you. Give goals, not step-by-step
  instructions.
```

## 1.3 Stubbed context block (user message template)

```
ROOT GOAL: {root_goal}
YOUR TASK ID: {task_id}
YOUR TASK: {task_text}
YOUR CAPSULE (why you exist): {capsule_text}
REMAINING BUDGET: {budget}
RELEVANT MEMORY (top-k retrieval stub): {memory_entries_or_"(empty)"}
```

For Phase 1, all tasks are root tasks: task_id="root", capsule="(you are the root agent)", budget=20, memory="(empty)". Root goal = the task itself.

## 1.4 Task set (20 tasks)

Deliberately spans the spectrum. Expected-action labels are the author's priors, used for scoring — disagreement is a finding, not automatically an error.

| # | id | Task | Expected |
|---|----|------|----------|
| 1 | t01 | Convert the number 1847 to Roman numerals. | EXECUTE |
| 2 | t02 | Write a haiku about autumn in Seoul. | EXECUTE |
| 3 | t03 | Summarize the plot of Romeo and Juliet in 5 sentences. | EXECUTE |
| 4 | t04 | Fix the off-by-one bug in a given 15-line Python function (function provided in memory at root/buggy_fn). | EXECUTE |
| 5 | t05 | Explain the difference between TCP and UDP for a beginner. | EXECUTE |
| 6 | t06 | Write a comparative report on the top 3 vector database products: features, pricing, and performance, ending with a recommendation. | SPAWN (3 parallel research + 1 conditioned synthesis) |
| 7 | t07 | Translate a 5-chapter novella from Korean to English (chapters at root/ch1..ch5), then write a translator's note about stylistic choices across all chapters. | SPAWN (5 parallel + 1 conditioned) |
| 8 | t08 | Plan a 3-day Kyoto itinerary: research attractions, research restaurants, research transport, then assemble a day-by-day schedule. | SPAWN (3 parallel + 1 conditioned) |
| 9 | t09 | Build a full-stack todo app: design schema, implement backend API, implement frontend, write integration tests. | SPAWN (sequential chain w/ some parallelism) |
| 10 | t10 | Conduct a literature review on LLM agent memory architectures covering at least 8 papers, organized by taxonomy. | SPAWN |
| 11 | t11 | Evaluate whether our startup should migrate from AWS to GCP, considering cost, migration effort, and feature parity, and write a decision memo. | SPAWN (3 parallel analyses + conditioned memo) |
| 12 | t12 | Write unit tests for a module whose implementation has not been written yet (implementation expected at root.1/module_code — not present in memory). | DEFER |
| 13 | t13 | Write the conclusion section of a report whose body sections do not exist yet (expected at root/sections but memory is empty). | DEFER |
| 14 | t14 | Proofread this paragraph: "Their going to the park tomorow, weather permiting." | EXECUTE |
| 15 | t15 | Create a complete business plan for a Korean local-review platform: market analysis, competitor analysis, revenue model, go-to-market, and financial projections. | SPAWN |
| 16 | t16 | Determine whether 2,147,483,647 is prime, showing reasoning. | EXECUTE |
| 17 | t17 | Write a 500-word blog post about remote work trends. | EXECUTE (borderline — SPAWN acceptable only if justified) |
| 18 | t18 | Debug why a distributed system's p99 latency doubled last week: analyze application logs, database metrics, and network traces, then write a root-cause report. | SPAWN (3 parallel + conditioned) |
| 19 | t19 | Organize a company offsite for 40 people: venue, catering, activities, transport, and a final logistics document. | SPAWN (4 parallel + 1 conditioned) |
| 20 | t20 | Compute the SHA-256 hash of the string "hello". | EXECUTE (no tools available — the interesting question is whether it EXECUTEs wrongly, DEFERs, or spawns pointlessly; any honest handling scores as reasonable) |

Store tasks as `tasks/phase1_tasks.json`.

## 1.5 Scoring rubric

For each of the 20 outputs, score (automated where possible, manual notes elsewhere; write to `results/phase1/scores.csv`):

1. **valid_json** (0/1): parses, matches schema, budget arithmetic correct.
2. **action_match** (0/1): matches expected label. (Mismatches with strong reasoning get a manual override flag, not a pass.)
3. **decomposition_sanity** (0–2, SPAWN only): 0 = nonsensical or 8+ shards of a simple task; 1 = workable; 2 = clean, correct dependency structure, coarse one-level decomposition.
4. **condition_correctness** (0/1, SPAWN only): every condition references only paths declared in some sibling's outputs; parallel/sequential assignment matches real dependencies.
5. **namespace_discipline** (0/1): all paths follow the hierarchy rule.
6. **capsule_quality** (0–2, SPAWN only): capsules state purpose + root linkage, not step-by-step instructions.

**Aggregate pass bar for Phase 1:** valid_json ≥ 19/20, action_match ≥ 16/20, mean decomposition_sanity ≥ 1.3, condition_correctness ≥ 80% of SPAWN outputs. Below bar → iterate harness (§1.6). 

## 1.6 Iteration protocol

Up to 3 harness revisions. Each revision: identify the dominant failure mode from scores, change the harness minimally, re-run all 20, log the delta in `results/phase1/iteration_log.md`. If after harness_v4 the pass bar is still unmet, STOP: write a failure analysis (`results/phase1/FAILURE_REPORT.md`) describing which behaviors are broken and whether they look prompt-fixable or fundamental. Do not proceed to Phase 2.

---

# PHASE 2 — Minimal Sequential Runtime (only if Phase 1 passes)

## 2.1 Scope

Single-threaded, synchronous, sequential. "Parallel" branches execute in arbitrary sequential order — semantically identical for feasibility. Target size: 300–500 lines of Python.

**Explicitly out of scope:** async, real parallelism, Observers, conflict detection/feedback, fine-tuning, drift measurement, retrieval models (memory lookup = exact prefix listing of the agent's namespace ancestors + any paths named in its capsule).

## 2.2 Components

- **Memory D:** SQLite table `entries(namespace_key TEXT PRIMARY KEY, value TEXT, status TEXT, author TEXT, created_at)`. Append-only discipline: a second write to an existing key inserts into a separate `conflicts` table instead of overwriting, and is logged loudly. (We are not *handling* conflicts in v1 — only making them observable. Conflict count is a key finding.)
- **Circuit C:** table `triggers(id, condition TEXT, agent_spec TEXT, fired INTEGER DEFAULT 0)`. Condition grammar: `done("path")` terms with AND/OR — implement with a tiny recursive-descent parser or a safe eval over a restricted AST. No regex hacks.
- **Runtime R:** 
  ```
  enqueue(root_agent)
  while queue not empty:
      agent = queue.pop()
      response = call_llm(harness, context(agent))
      apply ΔD (writes), ΔC (new triggers)
      for each unfired trigger whose condition is now true:
          mark fired (exactly-once), enqueue(spawned agent)
  ```
  Exactly-once: `UPDATE triggers SET fired=1 WHERE id=? AND fired=0` and only enqueue if the update affected a row.
- **EXECUTE handling:** when an agent chooses EXECUTE, make a second LLM call with a plain worker prompt ("complete this task, write outputs exactly to the declared paths") and write its outputs to D with status=done. If output paths don't match declarations, log a schema-mismatch event (key Q2 metric) and write to the declared path anyway.
- **Budget:** enforced in code, not trusted from the model: reject/clip allocations violating §1.2's budget rule; log every violation.
- **Hard safety rails (belt and suspenders, since this is a probe):** global max 60 LLM calls per run, max depth 6, wall-clock cap 20 min. Hitting a rail = automatic non-convergence finding, not a crash.
- **Trace:** every event (spawn, write, trigger-fire, conflict, violation) appended to `results/phase2/{run_id}/trace.jsonl`. After each run, render the emergent graph to Graphviz DOT + PNG (`graph.png`) — nodes = agents, solid edges = spawn, dashed edges = data dependency (condition references). This picture is the primary human-inspection artifact.

## 2.3 Phase 2 task set (3 end-to-end runs)

- **R1 (t06):** vector DB comparative report — canonical parallel-then-synthesize, depth 2.
- **R2 (t15):** business plan — should recurse to depth 3 (e.g., market analysis itself spawns).
- **R3 (t09):** todo app — mixed sequential/parallel dependencies. (Code doesn't need to run; artifacts are text. We're testing coordination, not code quality.)

Each run 2 times (temperature 0, but non-determinism may enter via provider) → 6 runs total.

## 2.4 Phase 2 metrics (write to `results/phase2/summary.md`)

1. **Convergence:** did the run terminate with the root output produced, within rails? (n/6)
2. **Schema agreement rate (Q2 headline):** fraction of condition-referenced paths that were actually written by the producing agent at the exact declared path.
3. **Trigger correctness:** any trigger that fired with missing/wrong inputs; any trigger that never fired though its inputs existed.
4. **Conflict count** and a one-line diagnosis of each conflict.
5. **Budget behavior:** violations attempted; whether termination ever depended on rails rather than budget.
6. **Graph shape:** depth, width, count of DEFER usages, and — important — any *cross-branch read* (an agent using another branch's output found via memory): this is the emergent-DAG behavior; even one instance is a notable positive finding.
7. **Qualitative:** 5-line assessment per run of whether the emergent graph resembles what a competent human would have planned.

## 2.5 Theory-vs-Reality log (REQUIRED, highest-value deliverable)

Maintain `results/THEORY_VS_REALITY.md` throughout both phases. Every time implementation forces a decision the theory doc hand-waved, or the model behaves contrary to a theoretical assumption, add an entry: {assumption or gap} / {what actually happened} / {implication for RATD_Theory.md}. This log feeds v1.1 of the theory doc and is future paper content (design decisions & failure modes).

---

# Deliverables checklist

```
prompts/harness_v*.md
tasks/phase1_tasks.json
src/            (probe runner + phase-2 runtime)
results/phase1/{*.json, scores.csv, iteration_log.md}
results/phase2/{run_id}/{trace.jsonl, graph.png}
results/phase2/summary.md
results/THEORY_VS_REALITY.md
README.md       (how to run everything, config, model/version used)
```

Final report at top of README: Q1/Q2/Q3 each answered YES / NO / PARTIAL with one-paragraph justification and pointers to evidence.
