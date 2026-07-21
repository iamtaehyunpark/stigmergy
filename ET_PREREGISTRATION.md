# ET_PREREGISTRATION — frozen before run 1

Frozen: 2026-07-21 12:16:32 +0900 · git 58e5b26274c4478236f0a84c4fc250b293d93234
Spec: docs/RATD_Experiment_Spec_ET.md v1.1 (verbatim excerpts below).
After the first scored run, nothing referenced here changes. If a
defect forces a change, the affected runs are discarded and rerun,
and the change is logged under Deviations.

## Predictions (verbatim from ET spec §4)

## 4. Pre-registered predictions

- **P1 (crossover):** Arm P ≥ Arm R at levels 1–2; gap closes at 3; Arm R > Arm P at 4–5 on quality, driven by adaptation events.
- **P2 (cost):** planner per-round context grows monotonically with level; Arms R and S per-activation context stay flat (within 2x of their level-1 values at level 5).
- **P3 (mechanism link):** in levels 4–5, Arm R quality correlates with adaptation-event count; Arm P failures concentrate where replanning context is largest (truncation/degradation signatures logged).
- **P4 (continuity locus, two-sided by design):** Arm S matches Arm R (within 1 judge point) on decomposition-shaped levels (1–3) at lower total tokens; Arm R leads on iteration-heavy levels (4–5). Declared readings: S ≈ R everywhere → continuity lives in the substrate; agents can be memoryless — the strongest form of the memory-is-the-machine thesis, and the cheap architecture is the right one. R > S only on iteration-heavy tasks → in-context continuity is localized to within-competence revision; hybrid architecture indicated. R > S everywhere → the agent model, not the substrate, was the binding constraint; the v2 redesign is vindicated and Arm S retires.
- **Honest readings declared in advance:** P1 fails but P2 holds → the claim is cost-scaling, not quality (the EM2 parity form, now under faithful agents — still publishable). P1 and P2 both fail → the theory's advantage does not survive faithful agent models at this scale; report as-is. Arm P's planner spontaneously *simulating* decentralization (delegating planning to workers via prose instructions) → logged as a finding about the pressure toward decentralization, arm still scored as centralized.
- **Variance rule:** within-cell sd > 3 on the judge scale → that cell reports cost + adaptation axes only.

## Fair-fight rules (verbatim from ET spec §1)

**FAIR-FIGHT RULES (pre-registered, violations invalidate the run):**
1. Same model, same temperature, same global call rail, same wall-clock rail per run. Round cap R_max applies per multi-round agent (Arms P, R); Arm S is bounded by the call rail alone.
2. Same memory planes, same tool implementations, same bounded-return caps, all three arms.
3. Same harness core text (tool docs + behavioral guidance); arm-specific text limited to describing the arm's own tool surface, activation model, and role. All three harness variants frozen and diffed in the pre-registration.
4. Same judge, same rubrics, frozen before run 1, system-blind, per-run scores published.
5. Neither arm receives task-specific hints, decomposition templates, or worked examples.

## Design (n, ladder, order)

5 levels (tasks/et_ladder.json) × 3 arms × n=4 reps = 60 runs.
Run order: interleave arms within level, level 1 → 5
(r,p,s, rep-by-rep). Judging: system-blind, fixed-seed (0) shuffled
order, per-run scores published (src/ratd_v2/judge.py).

## Model & rails (identical across arms)

- model: qwen3.6, temp 0, local vLLM, max_tokens 8000 per call
- serving (owned instance, frozen): vLLM 0.16.1rc1, single GPU,
  `vllm serve Qwen/Qwen3.6-27B --served-model-name qwen3.6 --port 8001
  --max-model-len 262144 --gpu-memory-utilization 0.92`; endpoint
  http://127.0.0.1:8001/v1/chat/completions (galaxy-05 GPU 0);
  no other workload shares the serving process
- global call rail 300, wall clock 3600s per run
- R_max 30 rounds per multi-round agent (Arms P, R);
  Arm S bounded by the call rail alone (spec rule 1)
- rolling window 8 rounds (Arms P, R); Arm S carries only
  the previous activation's op results (in-substrate continuity)
- Arm S decodes under response_format=json_object (single action
  document; the v1 single-shot model re-hosted). Arms P/R emit free
  text with fenced tool blocks. Same parser, same tools, same caps.

## Mechanical metric definitions (fixed before run 1)

- Context per decision (v2 definition): per-round prompt size in
  chars (system + identity + window + delivered observations),
  logged per llm_call; token counts logged per llm_reply.
- Adaptation event: structure-changing tool call (spawn /
  circuit.add_rule / circuit.update_rule) by an agent at round or
  activation > 1 (Arms R/S); planner spawn at round > 1 (Arm P).
- Arm S chain: maximal run of consecutive activations of one agent
  linked by self-resume rules (continue / wait-self).
- Cross-activation handoff: read whose target was last written by a
  different agent; delivered chars = bounded result size,
  truncation flagged.
- Judge artifact: concatenated heads under global/final/* in path
  order; fallback to all global heads is recorded per run.
- Health verdict: quiescence + failure predicate per Playground
  Spec §5, logged mechanically every run (doctor off).
- Variance rule (spec §4): within-cell sd > 3 on the judge scale →
  that cell reports cost + adaptation axes only.

## Frozen artifacts (sha256)

- `prompts/et/harness_ratd.md` eefa3b3710a0b4252e3ad8a70fdfbb78b6e4290349e4d385c2281403d9f21243
- `prompts/et/harness_planner.md` 360736432dcb4b4adf2c491153b5cdc41e8f7c194660b17bbf0a974baf544aca
- `prompts/et/harness_worker.md` e7c7df2be4c9dd513a21fa03968b6137b52daccf45414a60f2662c9b2cdef363
- `prompts/et/harness_stig.md` bd9710fb85229a2f22c791b375368a96b521429ad5fb4db56a6b99cabd0a0860
- `prompts/et/src/core.md` 45e25e1ab6a6fe33b6d567527a8465ae59311fbe177654be76a2b580ee3638fe
- `prompts/et/src/role_ratd.md` 137fec036bb6d4462c920682d0fb6cc03907a307c03ed1dc6dbe71e467b1d3a1
- `prompts/et/src/role_planner.md` ecdb164e0f0996be4f9ee9d0a6935ffe6d9c7dc8b66a0498f2ab26fac32508a8
- `prompts/et/src/role_worker.md` 73af5294d4a570b373f5ca48b7c72cb5c0948c0a0ae484adeec7cb6fe7f8f390
- `prompts/et/src/role_stig.md` f764b25baca47522a3dbadf78ffd9d1850d2af128aede210019b98ad80975d8b
- `prompts/et/src/surface_circuit.md` 966aa23ab520709e2df226e575f96bb73e141e0382954b3098180c5ccd8aa72c
- `prompts/et/src/surface_planner.md` 9e29fae9c91a30e83e2744dd1724756462607eeab82cabc8082421723b93c757
- `prompts/et/src/surface_stig.md` 0cec6c21fd574dbec2524dacdedbfbcd8627d7386ac813a965ddb7640dd3d6f8
- `prompts/judge_v1.md` d570a8adb39545fdbfc12f5a33b6db9637c2467bf56a3c2c036b954c1eda92e6
- `rubrics/et/L1.md` b4fdc667c986f9d7c465b2c18c4a9790e09d3c3a98935a194467af78d083d64b
- `rubrics/et/L2.md` 973d80573c9c0c10a7a926db737ec8b156d74fbe3c93895dc04ec9aed97741a0
- `rubrics/et/L3.md` b3635f70a72fa206f7f319984df81d3cfa1d5bde71401e83b922ea4a79972659
- `rubrics/et/L4.md` e17b50cbaa16bedd82926a66d3f0d3c0244d6fbca77e210218ec4ce9c40587c8
- `rubrics/et/L5.md` 351a88564a981a7df9d35cd07bf990e014f7dc3688a8195d9dcd38c185675374
- `tasks/et_ladder.json` 3144d9430aaf163c7f35236f89a34588b64058fdf064342e52e99238f6660f48

### Runtime (reference, not judge-visible)

- `src/ratd_v2/__init__.py` bfe7f2e472309ffb27799290d125d0a54f5847c98e818d256b5f70aa2f8976cc
- `src/ratd_v2/agents.py` 738c566afb0e9a2a597085a1855a53538a6dd2da6780daeba886703efa9e7e09
- `src/ratd_v2/analyze.py` 08037e27c1f4930f2ad905148684737b136b685796482ed255feb956ee185d0e
- `src/ratd_v2/build_harnesses.py` 3c8fd31f91b1528ea0982ddd611379dc50098ebcce448e1d3e93672e06bbe873
- `src/ratd_v2/circuit.py` 3902238f32fc874b7cfae38e232f2d8715942997b37ab9679d13447642725fdf
- `src/ratd_v2/client.py` a685401633c644f82d2ec1728edaae963c93f14ace98a229011b00639586c6a4
- `src/ratd_v2/freeze.py` eaf7562aa379bf940dec9dd1e3e93e93ddee615f0992f3900ba9014976a6d663
- `src/ratd_v2/judge.py` e5e98dad2fe8357659f2e88a7b98b3dcc08f95e456bcdff7612696b18b173dc8
- `src/ratd_v2/memory.py` 96beabe7e30852411bcee640559b4019e6afe43b92710af39e316bd8d7c8a078
- `src/ratd_v2/run.py` 0a14db3b5b11a6d571d9944f07c7195e4c3e008627bb1b07dfad11a593435e5c
- `src/ratd_v2/runtime.py` dffe9243b7039a12819ea44aae0bfeb35424ed0e421ef659b77fe164db45711c
- `src/ratd_v2/smoke_check.py` a35cfc93b7e716c0abae31de7065c2e637d140d554fcc2a635e4825af6c807d0
- `src/ratd_v2/test_offline.py` e0033c01088f498535bdfb365645eaef3f922b384ea531bbd64590a3aa3e0915
- `src/ratd_v2/tools.py` 6bbae8a6b801ed0c6c1dafee23182c43551a42c89f66d969875cdf21029a9d74
- `src/ratd_v2/trace.py` 7e009095891da77a0a1c2575a1a8a809ad3c46b2aab49822dfbc7aaba0cd97a3

## Harness variants: composition + diffs

Variants are generated by src/ratd_v2/build_harnesses.py by
concatenating role/core/surface sources; the CORE
(prompts/et/src/core.md — tool docs + behavioral guidance) is
byte-identical across all four variants by construction.

| variant | composition |
|---|---|
| harness_ratd.md | role_ratd + core + surface_circuit |
| harness_planner.md | role_planner + core + surface_planner |
| harness_worker.md | role_worker + core |
| harness_stig.md | role_stig + core + surface_circuit + surface_stig |

### Unified diffs vs harness_ratd.md

#### harness_planner.md

```diff
--- prompts/et/harness_ratd.md
+++ prompts/et/harness_planner.md
@@ -2,9 +2,11 @@
 
-You are an agent in a decentralized multi-agent system. There is no
-central planner and no fixed workflow: the execution structure emerges
-because agents like you decide, locally, how work should proceed. You
-have been assigned ONE task (in your context below). Whether you do it
-yourself, split it and deploy other agents, schedule future work through
-circuit rules, or suspend until the state you need exists — every one of
-those is your local decision, made with the state you choose to inspect.
+You are the central planner of a multi-agent system. You are the only
+entity that may create agents or define execution order: you decompose
+the ROOT GOAL, assign tasks to workers via `spawn`, monitor their states
+and outputs, and replan as often as you judge useful — adding, changing,
+or abandoning remaining work as the state evolves. Workers are as capable
+as you and use the same shared memory, but they cannot spawn agents or
+author circuit rules — all planning is yours. How you manage your own
+context across a long run is your problem to solve; the shared memory is
+available to externalize whatever you choose.
 
@@ -16,4 +18,5 @@
 your context as a bounded rolling window; older rounds scroll away, so
-durable state belongs in your workspace. You end your own run by
-declaring `done` or `fail`, or suspend with `wait`.
+durable state belongs in your workspace. Suspend with `wait` (e.g. until
+a worker finishes) instead of spending rounds polling; declare `done`
+only when the ROOT GOAL's deliverable is committed.
 # The environment (shared substrate)
@@ -152,27 +155,9 @@
 
-- `spawn` args `{task, capsule, initial_refs?, on_complete_rule?}` —
-  create a new agent immediately. It is as capable as you, receives your
-  `task` text and your `capsule` (2–4 sentences: why it exists, what you
-  need from it, constraints, how it serves the ROOT GOAL), and starts
-  with no context beyond that plus the shared memory — point it at
-  concrete paths via `initial_refs`. Optional `on_complete_rule`
-  `{condition, target}` installs a rule in the same step; the strings
-  `{child}` and `{self}` inside it are replaced by the new agent's id and
-  yours.
-- `circuit.add_rule` args `{condition, target}` — install a trigger
-  rule. `target` is `{"type": "spawn", "task": "...", "capsule": "...",
-  "initial_refs": [...]}` or `{"type": "resume", "agent_id": "..."}`.
-  The reply echoes the condition's current truth value — check it: an
-  already-true condition fires immediately; an unevaluable one is
-  rejected as an error.
-- `circuit.update_rule` args `{id, condition?, target?, fired?,
-  enabled?}` — edit any rule, including other agents'. Rules are
-  ordinary state: setting `fired` back to false re-arms a rule (it can
-  then fire exactly once again). Every edit is provenance-logged.
-- `circuit.disable_rule` args `{id}` — switch a rule off.
-- `circuit.inspect` args `{filter?}` — list installed rules
-  (substring filter optional).
-
-Rules fire exactly once per arming: when a rule's condition is true and
-the target agent should run again later under the same condition, someone
-must re-arm the rule or install a new one.
+- `spawn` args `{task, capsule, initial_refs?}` — create a worker agent
+  immediately. It receives your `task` text and your `capsule` (2–4
+  sentences: why this work exists, what you need back, constraints, how
+  it serves the ROOT GOAL), and starts with no context beyond that plus
+  the shared memory — point it at concrete paths via `initial_refs`.
+  Workers cannot spawn or author rules; they report by writing to memory
+  and declaring done/failed, which you can observe via the catalog and
+  `state(...)` conditions in `wait`.

```

#### harness_worker.md

```diff
--- prompts/et/harness_ratd.md
+++ prompts/et/harness_worker.md
@@ -2,9 +2,10 @@
 
-You are an agent in a decentralized multi-agent system. There is no
-central planner and no fixed workflow: the execution structure emerges
-because agents like you decide, locally, how work should proceed. You
-have been assigned ONE task (in your context below). Whether you do it
-yourself, split it and deploy other agents, schedule future work through
-circuit rules, or suspend until the state you need exists — every one of
-those is your local decision, made with the state you choose to inspect.
+You are a worker agent in a centrally planned multi-agent system. The
+planner created you for the ONE task in your context below and monitors
+your lifecycle state and your writes to memory. Do the task: produce the
+deliverables it names (or, if it names none, commit your results to
+global memory with summaries that say what they contain), verify your own
+work, then declare `done` — or `fail` honestly if you cannot. You cannot
+create agents or author circuit rules; if you are blocked on state that
+does not exist yet, `wait` on it or fail with a clear reason.
 
@@ -16,4 +17,3 @@
 your context as a bounded rolling window; older rounds scroll away, so
-durable state belongs in your workspace. You end your own run by
-declaring `done` or `fail`, or suspend with `wait`.
+durable state belongs in your workspace.
 # The environment (shared substrate)
@@ -150,29 +150 @@
   true.
-## Additional tools available to you
-
-- `spawn` args `{task, capsule, initial_refs?, on_complete_rule?}` —
-  create a new agent immediately. It is as capable as you, receives your
-  `task` text and your `capsule` (2–4 sentences: why it exists, what you
-  need from it, constraints, how it serves the ROOT GOAL), and starts
-  with no context beyond that plus the shared memory — point it at
-  concrete paths via `initial_refs`. Optional `on_complete_rule`
-  `{condition, target}` installs a rule in the same step; the strings
-  `{child}` and `{self}` inside it are replaced by the new agent's id and
-  yours.
-- `circuit.add_rule` args `{condition, target}` — install a trigger
-  rule. `target` is `{"type": "spawn", "task": "...", "capsule": "...",
-  "initial_refs": [...]}` or `{"type": "resume", "agent_id": "..."}`.
-  The reply echoes the condition's current truth value — check it: an
-  already-true condition fires immediately; an unevaluable one is
-  rejected as an error.
-- `circuit.update_rule` args `{id, condition?, target?, fired?,
-  enabled?}` — edit any rule, including other agents'. Rules are
-  ordinary state: setting `fired` back to false re-arms a rule (it can
-  then fire exactly once again). Every edit is provenance-logged.
-- `circuit.disable_rule` args `{id}` — switch a rule off.
-- `circuit.inspect` args `{filter?}` — list installed rules
-  (substring filter optional).
-
-Rules fire exactly once per arming: when a rule's condition is true and
-the target agent should run again later under the same condition, someone
-must re-arm the rule or install a new one.

```

#### harness_stig.md

```diff
--- prompts/et/harness_ratd.md
+++ prompts/et/harness_stig.md
@@ -12,8 +12,33 @@
 
-You are a persistent multi-round agent. Each round you receive the
-results of your previous round's tool calls, reason, and act again — as
-many rounds as you need up to your round cap. Your recent rounds stay in
-your context as a bounded rolling window; older rounds scroll away, so
-durable state belongs in your workspace. You end your own run by
-declaring `done` or `fail`, or suspend with `wait`.
+You are activated for exactly ONE emission at a time. This message is
+your whole context: you emit one action document — any combination of
+tool calls — and the activation ends. You carry no memory between
+activations; continuity lives in the substrate:
+
+- Persist working state to your workspace; read it back when you need it.
+- End the ops list with exactly one of: `done` / `fail` / `wait
+  {condition}` / `continue` (args `{}` — re-activates you immediately).
+  If you end with none of these: an emission that changed state (wrote,
+  committed, spawned, added rules) is re-activated as if you had emitted
+  `continue`; an emission that only READ is re-activated once, and a
+  second consecutive read-only emission records you done — pure
+  observation cannot progress by re-activation, because nothing you
+  learned survives unless you persist it. Declare `done` explicitly when
+  your task is finished.
+- If you chain (`continue` or `wait`), your next activation receives the
+  results of THIS emission's tool calls — that is your only delivery
+  channel besides memory. Reads you emit now are answered then.
+
+Multi-step work is a chain of cheap activations over shared state:
+persist, chain, act on what arrives.
+
+**Your emission format (overrides the fenced-block format described
+below, which applies to multi-round agents):** your ENTIRE response must
+be one JSON object:
+
+    {"reasoning": "<your thinking, private>",
+     "ops": [ {"tool": "<name>", "args": {...}}, ... ]}
+
+The tool names, args, and everything else in the tool documentation
+below apply unchanged; only the wrapper differs.
 # The environment (shared substrate)
@@ -178 +203,4 @@
 must re-arm the rule or install a new one.
+- `continue` args `{}` — end this activation and re-activate yourself
+  immediately (sugar for an always-true self-resume rule). Your next
+  activation receives this emission's tool results.

```

## Deviations

- **2026-07-21 (during L2, outcome-blind — no ladder run judged): adaptive
  replication.** The owned serial endpoint is byte-deterministic at temp 0:
  all L1/L2 replicates were token-identical (r_L1 17118×4, p_L1 16082×4,
  s_L1 3680×4; L2 likewise across executed reps), invalidating the spec §2
  assumption that temp-0 nondeterminism supplies natural variance. Amended
  design: reps 1–2 always run; a cell whose reps 1–2 match exactly on
  llm_calls, total_tokens, n_agents, and judge-artifact sha256
  (src/ratd_v2/det_check.py) is recorded deterministic with effective n=1;
  any divergent cell runs the full pre-registered n=4. Approved by Taehyun
  before any level-3+ run. Distinct-outcome counts are reported alongside
  all cell statistics; the §4 variance rule applies to executed reps.
