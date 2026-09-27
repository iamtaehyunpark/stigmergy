"""Runtime R — Playground Spec v2 §5.

Mechanical only: tool execution, persistence, catalog maintenance,
condition evaluation, CAS firing, activation/scheduling, lifecycle
tracking, rails, full event trace. Serial round-robin over runnable
agents, one round per turn. No doctor; no validators on agent
behavior. Quiescence := no agent runnable ∧ no rule true-and-unfired.
Systemic failure := root not done ∨ any agent waiting at quiescence ∨
any failed agent (v2.0 has no handling mechanism, so every failed
agent counts as unhandled — logged in THEORY_VS_REALITY).
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .agents import Agent, WindowEntry
from .circuit import Circuit, Rule
from .client import Config, ModelReply, call_model, write_json
from .memory import Memory
from .tools import Tools, parse_tool_calls
from .trace import Trace


@dataclass(frozen=True)
class ArmSpec:
    name: str                  # "p" | "r" | "s"
    root_role: str             # planner | ratd | stig
    child_role: str            # worker | ratd | stig
    single_shot: bool          # Arm S activation model


ARMS = {
    "p": ArmSpec("p", "planner", "worker", False),
    "r": ArmSpec("r", "ratd", "ratd", False),
    "s": ArmSpec("s", "stig", "stig", True),
}


@dataclass
class Rails:
    max_llm_calls: int = 300
    wall_clock_s: float = 3600.0
    r_max: int = 30            # per multi-round agent; Arm S exempt (call rail only)
    window_rounds: int = 8     # rolling window size (multi-round agents)
    # last-resort prompt roof (chars): if a prompt would exceed this, the
    # oldest window rounds are dropped WITH a visible marker (logged) so the
    # request stays sendable under the model's context length. ~200k tokens.
    prompt_char_cap: int = 800_000


class Runtime:
    def __init__(self, run_id: str, arm: str, task: dict[str, Any],
                 harnesses: dict[str, str], config: Config, out_dir: Path,
                 rails: Optional[Rails] = None,
                 model_fn: Optional[Callable[[list[dict[str, str]], bool], ModelReply]] = None,
                 dropped_tools: frozenset[str] = frozenset(),
                 no_self_resume: bool = False):
        self.run_id = run_id
        self.arm = ARMS[arm]
        self.task = task
        self.harnesses = harnesses          # role -> system prompt text
        self.config = config
        self.out_dir = out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        self.rails = rails or Rails()
        # EF run-configuration layer: the lifecycle mechanism remains intact.
        self.dropped_tools = frozenset(dropped_tools)
        self.no_self_resume = bool(no_self_resume)
        self.trace = Trace(out_dir / "trace.jsonl")
        self.memory = Memory()
        self.circuit = Circuit()
        self.tools = Tools(self)
        self.agents: dict[str, Agent] = {}
        self.order: list[str] = []           # spawn order (round-robin order)
        self._catalog_keys: list[str] = []   # creation-order index for K
        self._next_agent = 0
        self._dirty = False
        self._rule_last_error: dict[str, str] = {}
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.rail_hit = ""
        self.started = 0.0
        self.quiescent = False
        self._model_fn = model_fn or (
            lambda messages, json_mode=False: call_model(messages, self.config, json_mode))

    # ------------------------------------------------------------------ state
    def mark_dirty(self) -> None:
        self._dirty = True

    def set_state(self, agent: Agent, state: str, reason: str = "") -> None:
        old = agent.state
        agent.state = state
        self.trace.log("lifecycle", agent=agent.id, **{"from": old},
                       to=state, round=agent.rounds, reason=reason[:300])
        self.mark_dirty()

    def spawn_agent(self, task: str, capsule: str, initial_refs: list[str],
                    parent: Optional[str], rule: Optional[str] = None,
                    role: Optional[str] = None, root: bool = False) -> Agent:
        if root:
            aid = "root"
        else:
            self._next_agent += 1
            aid = f"a{self._next_agent}"
        agent = Agent(id=aid,
                      role=role or (self.arm.root_role if root else self.arm.child_role),
                      task=task, capsule=capsule,
                      root_goal=self.task["task"],
                      parent=parent, initial_refs=initial_refs,
                      spawned_by_rule=rule)
        self.agents[aid] = agent
        self.order.append(aid)
        self._catalog_keys.append(f"agent:{aid}")
        self.trace.log("spawn", agent=aid, role=agent.role, parent=parent,
                       rule=rule, task=task[:400], capsule=capsule[:400],
                       initial_refs=initial_refs)
        self.mark_dirty()
        return agent

    # ------------------------------------------------------------------ K
    def _remember_path(self, path: str) -> None:
        if path not in self._catalog_keys:
            self._catalog_keys.append(path)

    def catalog_rows(self) -> list[str]:
        # refresh index keys for artifacts and rules created since last call
        for p in self.memory.all_paths():
            self._remember_path(p)
        for rid in self.circuit.rules:
            self._remember_path(f"rule:{rid}")
        rows = []
        for key in self._catalog_keys:
            if key.startswith("agent:"):
                a = self.agents.get(key[6:])
                if a:
                    rows.append(f"agent:{a.id} · {a.state} · role {a.role} · "
                                f"parent {a.parent or '-'} · rounds {a.rounds} · "
                                f"{a.task[:100]}")
            elif key.startswith("rule:"):
                r = self.circuit.rules.get(key[5:])
                if r:
                    status = ("disabled" if not r.enabled
                              else "fired" if r.fired else "armed")
                    tgt = (f"spawn:{r.target.get('task', '')[:40]}"
                           if r.target.get("type") == "spawn"
                           else f"resume:{r.target.get('agent_id')}")
                    rows.append(f"rule:{r.id} · {status} · by {r.author} · "
                                f"when {r.condition[:80]} · -> {tgt}")
            elif key.startswith("agents/"):
                f = self.memory.ws.get(key)
                if f:
                    rows.append(f"{f.path} · workspace · {len(f.content)} chars · "
                                f"last writer {f.author}")
            elif key.startswith("global/"):
                art = self.memory.glob.get(key)
                if art and art.head:
                    v = art.head_version()
                    div = " · DIVERGENT" if art.divergent else ""
                    rows.append(f"{art.path} · global v{art.head} · "
                                f"{len(v.content)} chars · author {v.author} · "
                                f"{v.summary or '(no summary)'}{div}")
        return rows

    def inspect(self, ident: str) -> Optional[dict[str, Any]]:
        if ident in self.agents:
            a = self.agents[ident]
            return {
                **a.public_row(),
                "capsule": a.capsule,
                "initial_refs": a.initial_refs,
                "spawned_by_rule": a.spawned_by_rule,
                "children": [c.id for c in self.agents.values() if c.parent == ident],
                "workspace_files": [
                    {"path": f.path, "chars": len(f.content)}
                    for f in self.memory.ws_list(f"agents/{ident}/")],
                "done_summary": a.done_summary,
                "fail_reason": a.fail_reason,
            }
        rule = self.circuit.get(ident)
        if rule:
            return {**rule.row(), "author_round": rule.author_round,
                    "fired_count": rule.fired_count, "edits": rule.edits[-10:]}
        path = ident if "/" in ident else None
        if path:
            if path in self.memory.ws:
                f = self.memory.ws[path]
                return {"path": f.path, "kind": "workspace",
                        "chars": len(f.content), "writes": f.writes,
                        "last_writer": f.author}
            if not path.startswith(("agents/", "global/")):
                path = f"global/{path}"
            art = self.memory.glob.get(path)
            if art:
                return {"path": art.path, "kind": "global", "head": art.head,
                        "divergent": art.divergent,
                        "versions": [{"version": v.version, "author": v.author,
                                      "round": v.round, "chars": len(v.content),
                                      "summary": v.summary}
                                     for v in art.versions[-20:]]}
        return None

    # ------------------------------------------------------------------ C
    def accessors(self) -> dict[str, Callable[..., Any]]:
        def state(agent_id: Any) -> Optional[str]:
            a = self.agents.get(str(agent_id))
            return a.state if a else None

        def children(agent_id: Any) -> list[str]:
            return [a.id for a in self.agents.values()
                    if a.parent == str(agent_id)]

        def fired(rule_id: Any) -> bool:
            r = self.circuit.get(str(rule_id))
            return bool(r and r.fired)

        def count(x: Any) -> int:
            if isinstance(x, str):
                return len(self.memory.matching(x))
            if isinstance(x, (list, tuple, set)):
                return len(x)
            return 0

        return {
            "exists": lambda p: self.memory.exists(str(p)),
            "head": lambda p: self.memory.head_no(str(p)),
            "field": lambda p, k: self.memory.field(str(p), str(k)),
            "state": state,
            "children": children,
            "fired": fired,
            "matching": lambda g: self.memory.matching(str(g)),
            "count": count,
        }

    def surface_for(self, role: str) -> set[str]:
        from .tools import SURFACES
        return set(SURFACES[role]) - self.dropped_tools

    def sweep(self) -> None:
        """Re-evaluate the circuit until no rule fires (state events cascade)."""
        while self._dirty:
            self._dirty = False
            fired, errors = self.circuit.sweep(self.accessors())
            for rule, err in errors:
                # dedup: a malformed rule errors on every sweep; log changes only
                if self._rule_last_error.get(rule.id) != err:
                    self._rule_last_error[rule.id] = err
                    self.trace.log("rule_eval_error", rule_id=rule.id,
                                   condition=rule.condition[:200], error=err)
            for rule in fired:
                self._fire(rule)

    def _fire(self, rule: Rule) -> None:
        self.trace.log("rule_fired", rule_id=rule.id,
                       condition=rule.condition[:300], target=rule.target,
                       author=rule.author, fired_count=rule.fired_count)
        target = rule.target
        if target.get("type") == "spawn":
            self.spawn_agent(task=target["task"],
                             capsule=str(target.get("capsule", "")),
                             initial_refs=list(target.get("initial_refs", [])),
                             parent=rule.author, rule=rule.id)
        elif target.get("type") == "resume":
            agent = self.agents.get(str(target.get("agent_id")))
            if agent is None or agent.state != "waiting":
                self.trace.log("rule_target_invalid", rule_id=rule.id,
                               target=target,
                               agent_state=agent.state if agent else None)
                return
            agent.pending_obs.append(
                f"[resumed by rule {rule.id}: condition `{rule.condition}` "
                f"became true]")
            agent.wait_rule = None
            self.set_state(agent, "running", reason=f"resumed by {rule.id}")

    # ------------------------------------------------------------------ rails
    def _check_rails(self) -> bool:
        if self.rail_hit:
            return True
        if self.llm_calls >= self.rails.max_llm_calls:
            self.rail_hit = "max_llm_calls"
        elif time.time() - self.started > self.rails.wall_clock_s:
            self.rail_hit = "wall_clock"
        if self.rail_hit:
            self.trace.log("rail_hit", rail=self.rail_hit,
                           llm_calls=self.llm_calls)
            return True
        return False

    # ------------------------------------------------------------------ prompts
    def _identity_block(self, agent: Agent) -> str:
        lines = [
            f"AGENT ID: {agent.id}   (workspace: agents/{agent.id}/)",
            f"ROOT GOAL: {agent.root_goal}",
            f"YOUR TASK: {agent.task}",
            f"CAPSULE (why you exist): {agent.capsule or '(you are the root agent)'}",
            f"PARENT: {agent.parent or '(none — you are the root)'}",
        ]
        if agent.initial_refs:
            lines.append("INITIAL REFERENCES (paths you were pointed at — "
                         "read what you need): " + ", ".join(agent.initial_refs))
        if agent.spawned_by_rule:
            rule = self.circuit.get(agent.spawned_by_rule)
            if rule:
                lines.append(f"SPAWNED BY RULE {rule.id}: condition "
                             f"`{rule.condition}` (authored by {rule.author})")
        return "\n".join(lines)

    def _status_line(self, agent: Agent) -> str:
        parts = [f"[round {agent.rounds} for you"]
        if not self.arm.single_shot:
            parts.append(f" of max {self.rails.r_max}")
        parts.append(f"; global LLM calls {self.llm_calls}/"
                     f"{self.rails.max_llm_calls}]")
        return "".join(parts)

    def _build_messages(self, agent: Agent) -> list[dict[str, str]]:
        system = self.harnesses[agent.role]
        identity = self._identity_block(agent)
        # NOTE: does not consume pending_obs — run_round may rebuild under
        # the prompt roof; the caller clears pending after the final build.
        pending = "\n".join(agent.pending_obs)
        if self.arm.single_shot:
            # Arm S: stateless activation — no transcript. The prompt carries
            # identity, why it was activated, and the results of the previous
            # activation's ops (the delivery channel), nothing else.
            parts = [identity]
            if agent.window:
                parts.append("RESULTS OF YOUR PREVIOUS ACTIVATION'S OPERATIONS:\n"
                             + agent.window[-1].observation)
            if pending:
                parts.append(pending)
            parts.append(self._status_line(agent) + " Emit your action document now.")
            return [{"role": "system", "content": system},
                    {"role": "user", "content": "\n\n".join(parts)}]
        msgs = [{"role": "system", "content": system}]
        first_user = identity
        dropped = agent.rounds - 1 - len(agent.window)
        if dropped > 0:
            first_user += (f"\n\n[rounds 1–{dropped} have scrolled out of your "
                           f"window; durable state belongs in your workspace]")
        if not agent.window:
            tail = [first_user]
            if pending:
                tail.append(pending)
            tail.append(self._status_line(agent) + " Begin.")
            return msgs + [{"role": "user", "content": "\n\n".join(tail)}]
        msgs.append({"role": "user", "content": first_user})
        for i, entry in enumerate(agent.window):
            msgs.append({"role": "assistant", "content": entry.assistant})
            obs = entry.observation
            if i == len(agent.window) - 1:
                extra = ("\n\n" + pending if pending else "") + \
                    "\n\n" + self._status_line(agent)
                obs = obs + extra
            msgs.append({"role": "user", "content": obs})
        return msgs

    # ------------------------------------------------------------------ rounds
    def run_round(self, agent: Agent) -> None:
        if agent.state == "spawned":
            self.set_state(agent, "running", reason="first round")
        if (not self.arm.single_shot) and agent.rounds >= self.rails.r_max:
            self.trace.log("agent_round_rail", agent=agent.id,
                           rounds=agent.rounds, r_max=self.rails.r_max)
            self.set_state(agent, "terminated",
                           reason=f"R_max={self.rails.r_max} rounds exhausted")
            return
        agent.rounds += 1
        messages = self._build_messages(agent)
        dropped = 0
        while (sum(len(m["content"]) for m in messages) >
               self.rails.prompt_char_cap and len(agent.window) > 1):
            agent.window.pop(0)
            dropped += 1
            messages = self._build_messages(agent)
        if dropped:
            self.trace.log("window_truncated", agent=agent.id,
                           round=agent.rounds, dropped_rounds=dropped)
            messages[1]["content"] += (
                f"\n\n[context roof: the runtime dropped your {dropped} oldest "
                f"window round(s) to keep this prompt sendable]")
        agent.pending_obs = []
        prompt_chars = sum(len(m["content"]) for m in messages)
        agent.prompt_chars.append(prompt_chars)
        self.llm_calls += 1
        self.trace.log("llm_call", agent=agent.id, round=agent.rounds,
                       call_no=self.llm_calls, prompt_chars=prompt_chars,
                       messages=len(messages),
                       window=len(agent.window))
        # Arm S emissions are decoded under response_format=json_object
        # (the v1 single-shot action-document model re-hosted); multi-round
        # arms emit free text with fenced tool blocks.
        reply = self._model_fn(messages, self.arm.single_shot)
        agent.prompt_tokens += reply.prompt_tokens
        agent.completion_tokens += reply.completion_tokens
        self.prompt_tokens += reply.prompt_tokens
        self.completion_tokens += reply.completion_tokens
        self.trace.log("llm_reply", agent=agent.id, round=agent.rounds,
                       chars=len(reply.text),
                       prompt_tokens=reply.prompt_tokens,
                       completion_tokens=reply.completion_tokens,
                       finish_reason=reply.finish_reason,
                       text=reply.text)
        calls, parse_errors = parse_tool_calls(reply.text)
        if reply.finish_reason == "length":
            agent.pending_obs.append(
                f"[YOUR PREVIOUS EMISSION WAS CUT at the "
                f"{self.config.max_tokens}-token output cap — any unterminated "
                f"tool block was not executed. Emit large content in smaller "
                f"pieces (workspace.write with append: true).]")
        if parse_errors:
            self.trace.log("parse_errors", agent=agent.id, round=agent.rounds,
                           errors=parse_errors, n_calls_parsed=len(calls))
        obs_parts: list[str] = []
        for err in parse_errors:
            obs_parts.append(f"[parse] {err}")
        terminal_hit = False
        state_changed = False
        for n, call in enumerate(calls, 1):
            if terminal_hit:
                self.trace.log("tool_skipped_after_terminal", agent=agent.id,
                               round=agent.rounds, tool=call["tool"])
                obs_parts.append(f"[{n}] {call['tool']}: SKIPPED "
                                 "(a terminal tool already ended this round)")
                continue
            result, terminal = self.tools.execute(agent, call)
            self.trace.log("tool_call", agent=agent.id, round=agent.rounds,
                           tool=call["tool"], args=call["args"],
                           result_chars=len(result),
                           result=result[:2000],
                           truncated_return="[TRUNCATED" in result,
                           error=result.startswith("ERROR"))
            obs_parts.append(f"[{n}] {call['tool']}: {result}")
            if not result.startswith("ERROR") and call["tool"] in (
                    "workspace.write", "global.commit", "spawn",
                    "circuit.add_rule", "circuit.update_rule",
                    "circuit.disable_rule"):
                state_changed = True
            if terminal and not result.startswith("ERROR"):
                terminal_hit = True
            # tool effects may have fired rules that affect later calls
            self.sweep()
        if not calls and not parse_errors:
            obs_parts.append("(no tool calls parsed from your output — text "
                             "outside tool blocks is private reasoning and is "
                             "delivered to no one; act via tools)")
        observation = "\n".join(obs_parts) or "(no observations)"
        agent.window.append(WindowEntry(round=agent.rounds,
                                        assistant=reply.text,
                                        observation=observation))
        limit = 1 if self.arm.single_shot else self.rails.window_rounds
        if len(agent.window) > limit:
            agent.window = agent.window[-limit:]
        if terminal_hit:
            agent.readonly_chain = 0   # conscious terminal resets the grace
        if self.arm.single_shot and not terminal_hit and agent.state == "running":
            # Arm S: the activation ended without done/fail/wait/continue.
            # (terminal_hit guards the case where an in-round sweep already
            # resumed this agent from its own immediately-true wait/continue.)
            # No terminal op. Auto-chain (implicit continue) if the emission
            # changed state — chaining delivers the results of work — or was
            # cut at the output cap. A READ-ONLY no-terminal emission gets ONE
            # grace chain (orientation reads before drafting are the normal
            # first activation), then ends: two consecutive read-only
            # activations externalize nothing, so the context is a
            # deterministic fixed point (smoke round 5: a glossary agent
            # looped read/read for 92 activations, zero writes, into the call
            # rail; round 6: zero grace killed orientation reads). Explicit
            # continue/wait chains are never restricted.
            if state_changed or reply.finish_reason == "length":
                agent.readonly_chain = 0
                reason = ("emission cut at output cap; auto-chained"
                          if reply.finish_reason == "length"
                          else "no terminal op; state changed; auto-chained")
                nudge = ("[your previous activation ended without done/fail/"
                         "wait/continue — you were re-activated automatically "
                         "because it changed state. Declare `done` explicitly "
                         "when your task is finished.]")
            elif agent.readonly_chain < 1:
                agent.readonly_chain += 1
                reason = "read-only, no terminal op; one grace chain"
                nudge = ("[your previous activation only read and set no "
                         "terminal op — you were re-activated once. Persist "
                         "what you learned (workspace.write) or end with an "
                         "explicit terminal op; a second consecutive "
                         "read-only activation records you done.]")
            else:
                self.trace.log("implicit_done_readonly", agent=agent.id,
                               round=agent.rounds)
                self.set_state(agent, "done",
                               reason="two consecutive read-only activations "
                                      "with no terminal op (observation "
                                      "without externalization cannot "
                                      "progress by re-activation)")
                return
            self.trace.log("implicit_continue", agent=agent.id,
                           round=agent.rounds,
                           finish_reason=reply.finish_reason,
                           readonly_chain=agent.readonly_chain)
            rule = self.circuit.add(
                "True", {"type": "resume", "agent_id": agent.id},
                agent.id, agent.rounds)
            agent.wait_rule = rule.id
            agent.pending_obs.append(nudge)
            self.set_state(agent, "waiting", reason=reason)

    # ------------------------------------------------------------------ run
    def run(self) -> dict[str, Any]:
        self.started = time.time()
        self.trace.log("run_start", run_id=self.run_id, arm=self.arm.name,
                       task_id=self.task.get("id"), task=self.task["task"],
                       rails=vars(self.rails),
                       surface_drop=sorted(self.dropped_tools),
                       no_self_resume=self.no_self_resume,
                       config={"provider": self.config.provider,
                               "model": self.config.model,
                               "temperature": self.config.temperature,
                               "max_tokens": self.config.max_tokens})
        self.spawn_agent(task=self.task["task"], capsule="", initial_refs=[],
                         parent=None, root=True)
        self.sweep()
        while not self._check_rails():
            progressed = False
            for aid in list(self.order):
                agent = self.agents[aid]
                if not agent.runnable():
                    continue
                if self._check_rails():
                    break
                self.run_round(agent)
                self.sweep()
                progressed = True
            if self.rail_hit:
                break
            if not progressed:
                self.sweep()
                if not any(a.runnable() for a in self.agents.values()):
                    self.quiescent = True
                    break
        verdict = self._health_verdict()
        metrics = self._metrics(verdict)
        self._dump_state()
        write_json(self.out_dir / "metrics.json", metrics)
        self.trace.log("run_end", **{k: v for k, v in metrics.items()
                                     if k not in ("per_agent",)})
        self.trace.close()
        return metrics

    def _health_verdict(self) -> dict[str, Any]:
        waiting = [a.id for a in self.agents.values() if a.state == "waiting"]
        failed = [a.id for a in self.agents.values() if a.state == "failed"]
        root_state = self.agents["root"].state if "root" in self.agents else None
        reasons = []
        if root_state != "done":
            reasons.append(f"root agent state is {root_state}, not done")
        if self.quiescent and waiting:
            reasons.append(f"agents waiting at quiescence (permanently stuck "
                           f"by definition): {waiting}")
        if failed:
            reasons.append(f"failed agents (v2.0 counts every failed agent as "
                           f"unhandled): {failed}")
        verdict = {
            "quiescent": self.quiescent,
            "rail_hit": self.rail_hit,
            "root_state": root_state,
            "waiting_at_end": waiting,
            "failed_agents": failed,
            "systemic_failure": bool(reasons),
            "failure_reasons": reasons,
        }
        self.trace.log("health_verdict", **verdict)
        return verdict

    def _metrics(self, verdict: dict[str, Any]) -> dict[str, Any]:
        per_agent = {}
        for a in self.agents.values():
            per_agent[a.id] = {
                "role": a.role, "state": a.state, "rounds": a.rounds,
                "parent": a.parent,
                "prompt_tokens": a.prompt_tokens,
                "completion_tokens": a.completion_tokens,
                "prompt_chars_per_round": a.prompt_chars,
            }
        all_prompt_chars = [c for a in self.agents.values()
                            for c in a.prompt_chars]
        rules = list(self.circuit.rules.values())
        return {
            "run_id": self.run_id,
            "arm": self.arm.name,
            "task_id": self.task.get("id"),
            "wall_clock_s": round(time.time() - self.started, 1),
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "n_agents": len(self.agents),
            "n_rules": len(rules),
            "rules_fired": sum(r.fired_count for r in rules),
            "rule_edits_by_nonauthor": sum(
                1 for r in rules for e in r.edits if e["by"] != r.author),
            "global_artifacts": len(self.memory.glob),
            "divergent_artifacts": sum(
                1 for a in self.memory.glob.values() if a.divergent),
            "mean_prompt_chars": (sum(all_prompt_chars) / len(all_prompt_chars))
                if all_prompt_chars else 0,
            "max_prompt_chars": max(all_prompt_chars, default=0),
            "health": verdict,
            "per_agent": per_agent,
        }

    def _dump_state(self) -> None:
        state = {
            "agents": {a.id: {
                "role": a.role, "state": a.state, "parent": a.parent,
                "task": a.task, "capsule": a.capsule,
                "initial_refs": a.initial_refs,
                "spawned_by_rule": a.spawned_by_rule,
                "rounds": a.rounds, "done_summary": a.done_summary,
                "fail_reason": a.fail_reason,
            } for a in self.agents.values()},
            "workspaces": {f.path: {"content": f.content, "author": f.author,
                                    "writes": f.writes}
                           for f in self.memory.ws.values()},
            "global": {art.path: {
                "head": art.head, "divergent": art.divergent,
                "versions": [{"version": v.version, "author": v.author,
                              "round": v.round, "summary": v.summary,
                              "content": v.content}
                             for v in art.versions]}
                for art in self.memory.glob.values()},
            "rules": {r.id: {**r.row(), "author_round": r.author_round,
                             "fired_count": r.fired_count, "edits": r.edits}
                      for r in self.circuit.rules.values()},
        }
        write_json(self.out_dir / "state.json", state)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
