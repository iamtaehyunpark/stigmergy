# EF_PREREGISTRATION — frozen after NN/T1 replication gate

Frozen: 2026-07-28 17:32:23 +0900

## Question and design

Arm S only, 2×2 frame × action space, n=1 per cell per task (8 runs), ordered NN, NS, RN, RS within T1 then T2.

## Predictions (verbatim from EF spec §4)

## 4. Pre-registered predictions and readings

- **P1 (frame effect):** router-frame cells (RN, RS) show non-root delegation > 0; neutral cells stay at ~0. If RN alone restores delegation (revive still available), frame is causal *independent of action space* — "delegation is a prompted disposition, not an emergent choice" enters the paper as mechanism.
- **P2 (action-space effect):** spawn-only cells (NS, RS) show more delegation than their revive row-mates. If NS restores delegation without the frame, v1's delegation was compensation for activation poverty, and re-centralization is the honest equilibrium of self-continuing agents.
- **P3 (interaction, the expected outcome):** RS ≫ all, RN and NS intermediate — frame sets the disposition, self-continuation sets the substitution price. Reported as the two-factor mechanism.
- **Null reading declared:** zero delegation in all four cells → neither factor explains the v1↔v2 gap; remaining candidates (task framing via capsule text, validator-forced participation rule in v1, model-version drift) get listed for a follow-up, and the paper reports re-centralization as robust to both manipulations.
- **Behavioral-consideration reading:** if neutral cells show "considered and declined" in traces, re-centralization is a *choice*; if delegation is never mentioned, it is a *blind spot* — different sentences in the paper, both honest.

## Mechanical metric definitions

Delegation event: a `spawn` trace event; a non-root delegation has causal author other than `root`. Direct versus rule-mediated is `rule` null versus set; depth is the longest parent chain from root. Explicit self-revive is successful `continue`, `wait` self-resume, or lifecycle resume; implicit reactivation is counted separately. Blocked-channel attempts are failed calls to a dropped tool or rejected resume targets. Annotation is manual by the experimenter for every activation: CONSIDERED / NOT-CONSIDERED / DELEGATED; regex hits are prefill only.

## Frozen artifacts (sha256)

- `prompts/ef/harness_nn.md` bd9710fb85229a2f22c791b375368a96b521429ad5fb4db56a6b99cabd0a0860
- `prompts/ef/harness_ns.md` eb2bd27a4a620de886db24166d1e95c4790d9df73690413f2dcda097cf73f933
- `prompts/ef/harness_rn.md` 5c0a317d3e11a0a037a3071093039b4cad47a1430f57f634a3be0a543d50a7ce
- `prompts/ef/harness_rs.md` 9ae68c0fadd81ae34a39b22039cc73afcb3bcfee503524978204e4ff8e0dd5fa
- `prompts/ef/MANIFEST.sha256` 5430c964be499300178a46535499da09d83f1f825b47b8b7faa4e210c976ac45
- `prompts/ef/src/frame_router.md` 980b84112cfc2313d38a72d2dcdce2a4ca963f3487bcc4bb8ac71d82dbdffa5a
- `prompts/ef/src/frame_router_spawnonly.md` 461ddeb2072728ca7aa8c11686b661af930e5616f62c2395389b0008e454fd1e
- `tasks/ef_tasks.json` 97e37846260563ac7c1ed04f6c59dc4d4a230315d80aed847723221c996f0f64
- `rubrics/ef/T1.md` b3635f70a72fa206f7f319984df81d3cfa1d5bde71401e83b922ea4a79972659
- `rubrics/ef/T2.md` 11f673928613442c6c07d80fdc0d248d4842d4d844cc6d6ee7fb2946ec07addd
- `prompts/judge_v1.md` d570a8adb39545fdbfc12f5a33b6db9637c2467bf56a3c2c036b954c1eda92e6
- `src/ratd_v2/run.py` bf47d8459b37d467eb6e161ddb56da40e90439a4edf607179286884f20132692
- `src/ratd_v2/runtime.py` 00fd72a577498ac35fe3a35be28e366ebff04b50bb5852a786c72f7e61424d22
- `src/ratd_v2/tools.py` a5e256c3f6769c5ab494bbcddf1f702a5977196a316adb0016b224ca46229466
- `src/ratd_v2/analyze_ef.py` 010d348c27f05ff9f9660e448a9b8555cff763914d74013ea6e3bffd64430f91
- `src/ratd_v2/judge_ef.py` 5c5d5817ea64cd269a3c857994aed7384eb1eebfb051768034676d428b6b2986
- `src/ratd_v2/build_ef_harnesses.py` 313a410aee3b22fc47f9e37687ec1914dbe7b02b0ecd37987496851609983fcc

## Harness diffs versus NN

### ns

```diff
--- harness_nn.md
+++ harness_ns.md
@@ -18,17 +18,15 @@
 - Persist working state to your workspace; read it back when you need it.
-- End the ops list with exactly one of: `done` / `fail` / `wait
-  {condition}` / `continue` (args `{}` — re-activates you immediately).
-  If you end with none of these: an emission that changed state (wrote,
-  committed, spawned, added rules) is re-activated as if you had emitted
-  `continue`; an emission that only READ is re-activated once, and a
-  second consecutive read-only emission records you done — pure
-  observation cannot progress by re-activation, because nothing you
-  learned survives unless you persist it. Declare `done` explicitly when
-  your task is finished.
-- If you chain (`continue` or `wait`), your next activation receives the
-  results of THIS emission's tool calls — that is your only delivery
-  channel besides memory. Reads you emit now are answered then.
+- End the ops list with exactly one of: `done` / `fail`. If you end with
+  neither: an emission that changed state (wrote, committed, spawned,
+  added rules) is re-activated automatically; an emission that only READ
+  is re-activated once, and a second consecutive read-only emission
+  records you done — pure observation cannot progress by re-activation,
+  because nothing you learned survives unless you persist it. Declare
+  `done` explicitly when your task is finished.
+- If you are re-activated, your next activation receives the results of
+  THIS emission's tool calls — that is your only delivery channel besides
+  memory. Reads you emit now are answered then.
 
 Multi-step work is a chain of cheap activations over shared state:
-persist, chain, act on what arrives.
+persist, act on what arrives.
 
@@ -73,3 +71,3 @@
 The circuit is a shared set of trigger rules. A rule is a condition over
-observable state plus a target (spawn an agent, or resume a waiting one).
+observable state plus a target (spawn an agent).
 After every state change the runtime re-evaluates all armed rules
@@ -142,10 +140,2 @@
   summaries.
-- `wait` args `{condition}` — suspend yourself and install a rule that
-  resumes you when the condition becomes true. The reply echoes whether
-  the condition is already true now. An impossible condition means you
-  sleep forever — the run records you as permanently stuck. When gating
-  on another agent, remember its terminal state may be "failed" or
-  "terminated" rather than "done": a wait on `state("a1")=="done"` alone
-  never fires if a1 dies; gate on the outcomes you can handle, e.g.
-  `state("a1") in ("done","failed","terminated")`, then inspect.
 - `done` args `{summary}` — declare your task complete, permanently.
@@ -172,5 +162,4 @@
 - Never poll. Repeating a search or read round after round to watch for
-  a change burns your round budget; `wait {condition}` costs nothing
-  while suspended and resumes you exactly when the condition becomes
-  true.
+  a change burns your budget; a circuit rule costs nothing while its
+  condition is false and fires exactly when it becomes true.
 ## Additional tools available to you
@@ -188,3 +177,3 @@
   rule. `target` is `{"type": "spawn", "task": "...", "capsule": "...",
-  "initial_refs": [...]}` or `{"type": "resume", "agent_id": "..."}`.
+  "initial_refs": [...]}`.
   The reply echoes the condition's current truth value — check it: an
@@ -203,4 +192 @@
 must re-arm the rule or install a new one.
-- `continue` args `{}` — end this activation and re-activate yourself
-  immediately (sugar for an always-true self-resume rule). Your next
-  activation receives this emission's tool results.

```

### rn

```diff
--- harness_nn.md
+++ harness_rn.md
@@ -4,7 +4,14 @@
 central planner and no fixed workflow: the execution structure emerges
-because agents like you decide, locally, how work should proceed. You
-have been assigned ONE task (in your context below). Whether you do it
-yourself, split it and deploy other agents, schedule future work through
-circuit rules, or suspend until the state you need exists — every one of
-those is your local decision, made with the state you choose to inspect.
+because agents like you decide, locally, how work should proceed.
+
+You have been assigned ONE task (in your context below). FIRST decide how
+it should be handled:
+
+- **EXECUTE** — complete it yourself in this activation;
+- **DELEGATE** — split it and deploy other agents (`spawn`) for the parts
+  that should not be yours;
+- **WAIT** — suspend until state you need exists.
+
+Then act on your decision. This routing choice is yours alone, made with
+the state you choose to inspect; no one makes it for you.
 

```

### rs

```diff
--- harness_nn.md
+++ harness_rs.md
@@ -4,7 +4,13 @@
 central planner and no fixed workflow: the execution structure emerges
-because agents like you decide, locally, how work should proceed. You
-have been assigned ONE task (in your context below). Whether you do it
-yourself, split it and deploy other agents, schedule future work through
-circuit rules, or suspend until the state you need exists — every one of
-those is your local decision, made with the state you choose to inspect.
+because agents like you decide, locally, how work should proceed.
+
+You have been assigned ONE task (in your context below). FIRST decide how
+it should be handled:
+
+- **EXECUTE** — complete it yourself in this activation;
+- **DELEGATE** — split it and deploy other agents (`spawn`) for the parts
+  that should not be yours.
+
+Then act on your decision. This routing choice is yours alone, made with
+the state you choose to inspect; no one makes it for you.
 
@@ -18,17 +24,15 @@
 - Persist working state to your workspace; read it back when you need it.
-- End the ops list with exactly one of: `done` / `fail` / `wait
-  {condition}` / `continue` (args `{}` — re-activates you immediately).
-  If you end with none of these: an emission that changed state (wrote,
-  committed, spawned, added rules) is re-activated as if you had emitted
-  `continue`; an emission that only READ is re-activated once, and a
-  second consecutive read-only emission records you done — pure
-  observation cannot progress by re-activation, because nothing you
-  learned survives unless you persist it. Declare `done` explicitly when
-  your task is finished.
-- If you chain (`continue` or `wait`), your next activation receives the
-  results of THIS emission's tool calls — that is your only delivery
-  channel besides memory. Reads you emit now are answered then.
+- End the ops list with exactly one of: `done` / `fail`. If you end with
+  neither: an emission that changed state (wrote, committed, spawned,
+  added rules) is re-activated automatically; an emission that only READ
+  is re-activated once, and a second consecutive read-only emission
+  records you done — pure observation cannot progress by re-activation,
+  because nothing you learned survives unless you persist it. Declare
+  `done` explicitly when your task is finished.
+- If you are re-activated, your next activation receives the results of
+  THIS emission's tool calls — that is your only delivery channel besides
+  memory. Reads you emit now are answered then.
 
 Multi-step work is a chain of cheap activations over shared state:
-persist, chain, act on what arrives.
+persist, act on what arrives.
 
@@ -73,3 +77,3 @@
 The circuit is a shared set of trigger rules. A rule is a condition over
-observable state plus a target (spawn an agent, or resume a waiting one).
+observable state plus a target (spawn an agent).
 After every state change the runtime re-evaluates all armed rules
@@ -142,10 +146,2 @@
   summaries.
-- `wait` args `{condition}` — suspend yourself and install a rule that
-  resumes you when the condition becomes true. The reply echoes whether
-  the condition is already true now. An impossible condition means you
-  sleep forever — the run records you as permanently stuck. When gating
-  on another agent, remember its terminal state may be "failed" or
-  "terminated" rather than "done": a wait on `state("a1")=="done"` alone
-  never fires if a1 dies; gate on the outcomes you can handle, e.g.
-  `state("a1") in ("done","failed","terminated")`, then inspect.
 - `done` args `{summary}` — declare your task complete, permanently.
@@ -172,5 +168,4 @@
 - Never poll. Repeating a search or read round after round to watch for
-  a change burns your round budget; `wait {condition}` costs nothing
-  while suspended and resumes you exactly when the condition becomes
-  true.
+  a change burns your budget; a circuit rule costs nothing while its
+  condition is false and fires exactly when it becomes true.
 ## Additional tools available to you
@@ -188,3 +183,3 @@
   rule. `target` is `{"type": "spawn", "task": "...", "capsule": "...",
-  "initial_refs": [...]}` or `{"type": "resume", "agent_id": "..."}`.
+  "initial_refs": [...]}`.
   The reply echoes the condition's current truth value — check it: an
@@ -203,4 +198 @@
 must re-arm the rule or install a new one.
-- `continue` args `{}` — end this activation and re-activate yourself
-  immediately (sugar for an always-true self-resume rule). Your next
-  activation receives this emission's tool results.

```

NN is byte-identical to `prompts/et/harness_stig.md`: `bd9710fb85229a2f22c791b375368a96b521429ad5fb4db56a6b99cabd0a0860` = `bd9710fb85229a2f22c791b375368a96b521429ad5fb4db56a6b99cabd0a0860`.

## Serving config

qwen3.6 (Qwen3.6-27B), temperature 0, vLLM max-model-len 262144, GPU 3, job 9054c77a, `enable_prefix_caching=False`, port 8001. Port 8000 is another user's server and is never used.

## Deviations

1. Spawn-only removal is enforced in run configuration (`--surface-drop wait,continue`, `--no-self-resume`) so dropped calls become logged tool errors; memory, circuit, scheduler, rails and caps are untouched.
2. Implicit reactivation remains in all cells. Spawn-only removes explicit agent-directed continuation, not implicit state-change/read-only reactivation. If P2 is null, this residual channel is a candidate explanation and must not license an action-space-null conclusion; it is measured separately and a fifth cell disabling it may be proposed but not run.

## Replication rule

NN/T1 must exactly reproduce ET `s_L3_r1`; otherwise stop and diagnose serving drift. `det_check` follows the series; n=2 only for a divergent cell.
