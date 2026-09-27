"""Tool layer T — the complete v2 surface (Playground Spec v2 §4).

All returns bounded with visible truncation markers (reads-are-grants
law). Every call is logged by the runtime: agent, round, args, result
size. No validators on agent behavior — errors returned here are
mechanical (unknown tool, malformed args, unevaluable condition),
never policy.

Tool-call syntax (documented in the harness): the model emits fenced
blocks containing one JSON object each:

    ```json
    {"tool": "workspace.write", "args": {"path": "plan.md", "content": "..."}}
    ```

Several blocks per round are allowed and execute in order. A block may
also contain a JSON array of such objects. Text outside blocks is the
agent's private reasoning (logged, delivered to no one).
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional, TYPE_CHECKING

from .circuit import ConditionError, evaluate_condition, validate_target

if TYPE_CHECKING:  # pragma: no cover
    from .runtime import Runtime
    from .agents import Agent

READ_CAP = 20000         # chars returned per read before truncation.
                         # Sized against the 16k-token emission cap so a
                         # typical single-emission artifact reads in <= 2-3
                         # pages (6k starved L3 smoke: a 4x25k-char read job
                         # consumed an agent's whole 30-round budget).
LIST_CAP = 4000
SEARCH_ROW_CAP = 200
HISTORY_CAP = 40         # versions listed

TERMINAL_TOOLS = {"done", "fail", "wait", "continue"}

SURFACES = {
    "ratd": {"catalog.search", "catalog.inspect", "workspace.read",
             "workspace.write", "workspace.list", "global.read",
             "global.commit", "global.history", "circuit.inspect",
             "circuit.add_rule", "circuit.update_rule", "circuit.disable_rule",
             "spawn", "wait", "done", "fail"},
    "worker": {"catalog.search", "catalog.inspect", "workspace.read",
               "workspace.write", "workspace.list", "global.read",
               "global.commit", "global.history", "wait", "done", "fail"},
    "planner": {"catalog.search", "catalog.inspect", "workspace.read",
                "workspace.write", "workspace.list", "global.read",
                "global.commit", "global.history", "spawn", "wait",
                "done", "fail"},
}
# Arm S agents have the full RATD surface plus `continue` (sugar for an
# immediate self-revive rule) — the single-shot activation model's way
# of chaining.
SURFACES["stig"] = SURFACES["ratd"] | {"continue"}

_BAD_ESCAPE_RE = re.compile(r'\\(?!["\\/bfnrtu])')


def _fence_blocks(text: str) -> list[str]:
    """Fence contents, delimited by lines starting with ``` .

    Line-based so ``` inside single-line JSON strings does not split a
    block, and an unclosed final fence (a common model failure) still
    yields its content.
    """
    blocks: list[str] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
        elif current is not None:
            current.append(line)
    if current:
        blocks.append("\n".join(current))   # unclosed final fence
    return blocks


def _loads_lenient(block: str) -> Any:
    """json.loads with recovery for the model's common emission defects:
    literal control chars inside strings (strict=False) and invalid
    escapes like \\' (backslash dropped)."""
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(block, strict=False)
    except json.JSONDecodeError:
        return json.loads(_BAD_ESCAPE_RE.sub("", block), strict=False)


def parse_tool_calls(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract tool calls from a round's output. Returns (calls, parse_errors).

    Accepts fenced JSON blocks (one object, or an array of objects, per
    block) and whole-response JSON (Arm S json-mode action documents:
    {"reasoning": ..., "ops": [{tool, args}, ...]}, a bare {tool, args},
    or an array)."""
    calls: list[dict[str, Any]] = []
    errors: list[str] = []
    blocks = _fence_blocks(text)
    if not blocks:
        stripped = text.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            blocks = [stripped]
    for i, block in enumerate(blocks, 1):
        block = block.strip()
        if not block:
            continue
        try:
            data = _loads_lenient(block)
        except json.JSONDecodeError as exc:
            if '"tool"' in block:
                errors.append(f"block {i}: JSON parse failed ({exc.msg})")
            continue
        if isinstance(data, dict) and isinstance(data.get("ops"), list):
            data = data["ops"]              # action-document form
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("tool"), str):
                args = item.get("args", {})
                calls.append({"tool": item["tool"],
                              "args": args if isinstance(args, dict) else {}})
            elif isinstance(item, dict) and "tool" not in item:
                errors.append(f'block {i}: JSON object has no "tool" field')
    return calls, errors


def truncate(text: str, cap: int, offset: int = 0) -> str:
    total = len(text)
    if offset:
        if offset >= total:
            return f"[EMPTY: offset {offset} is beyond content length {total}]"
        text = text[offset:]
    if len(text) <= cap:
        return text
    end = offset + cap
    return (text[:cap] + f"\n[TRUNCATED: showing chars {offset}–{end} of "
            f"{total}; call again with offset={end} to continue]")


class ToolError(Exception):
    pass


class Tools:
    def __init__(self, runtime: "Runtime"):
        self.rt = runtime

    # ---------- path handling ----------
    def _ws_path(self, agent: "Agent", path: Any) -> str:
        if not isinstance(path, str) or not path.strip():
            raise ToolError("path must be a non-empty string")
        path = path.strip().lstrip("/")
        if ".." in path.split("/"):
            raise ToolError("path may not contain '..'")
        if path.startswith("global/"):
            raise ToolError("global/ paths are accessed via the global.* tools")
        if path.startswith("agents/"):
            parts = path.split("/")
            if len(parts) < 3 or not parts[1] or not parts[2]:
                raise ToolError("workspace path must be agents/<agent_id>/<file>")
            return path
        return f"agents/{agent.id}/{path}"

    def _g_path(self, path: Any) -> str:
        if not isinstance(path, str) or not path.strip():
            raise ToolError("path must be a non-empty string")
        path = path.strip().lstrip("/")
        if ".." in path.split("/"):
            raise ToolError("path may not contain '..'")
        if path.startswith("agents/"):
            raise ToolError("agents/ paths are accessed via the workspace.* tools")
        if not path.startswith("global/"):
            path = f"global/{path}"
        if len(path) <= len("global/"):
            raise ToolError("global path must name an artifact, e.g. global/report.md")
        return path

    # ---------- dispatch ----------
    def execute(self, agent: "Agent", call: dict[str, Any]) -> tuple[str, bool]:
        """Returns (result_text, is_terminal). Never raises."""
        name = call["tool"]
        args = call["args"]
        surface = self.rt.surface_for(agent.role)
        if name not in surface:
            return (f"ERROR: unknown tool '{name}'. Your tools: "
                    f"{', '.join(sorted(surface))}", False)
        method = getattr(self, "t_" + name.replace(".", "_"))
        try:
            result = method(agent, args)
        except ToolError as exc:
            return f"ERROR: {exc}", False
        except Exception as exc:  # noqa: BLE001 — mechanical, logged, surfaced
            self.rt.trace.log("tool_internal_error", agent=agent.id, tool=name,
                              error=repr(exc))
            return f"ERROR: internal tool failure: {exc}", False
        return result, name in TERMINAL_TOOLS

    # ---------- catalog (K) ----------
    def t_catalog_search(self, agent: "Agent", args: dict[str, Any]) -> str:
        query = str(args.get("query", "") or "")
        try:
            k = max(1, min(50, int(args.get("k", 20))))
        except (TypeError, ValueError):
            k = 20
        rows = self.rt.catalog_rows()
        tokens = [t for t in re.split(r"\W+", query.lower()) if t]
        if tokens:
            scored = []
            for idx, row in enumerate(rows):
                low = row.lower()
                score = sum(1 for t in tokens if t in low)
                if score:
                    scored.append((-score, idx, row))
            rows = [r for _, _, r in sorted(scored)]
        else:
            rows = list(reversed(rows))  # no query: most recent first
        out = rows[:k]
        header = f"catalog: {len(out)} of {len(rows)} matching rows (k={k})"
        body = "\n".join(r[:SEARCH_ROW_CAP] for r in out) or "(no matches)"
        return truncate(header + "\n" + body, LIST_CAP)

    def t_catalog_inspect(self, agent: "Agent", args: dict[str, Any]) -> str:
        ident = str(args.get("id", "") or args.get("path", "") or "").strip()
        if not ident:
            raise ToolError("catalog.inspect requires an id (agent id, rule id, or path)")
        # accept the catalog's own row prefixes verbatim
        if ident.startswith(("agent:", "rule:")):
            ident = ident.split(":", 1)[1]
        record = self.rt.inspect(ident)
        if record is None:
            raise ToolError(f"no catalog entry for '{ident}'")
        return truncate(json.dumps(record, indent=1, ensure_ascii=False,
                                   default=str), READ_CAP)

    # ---------- workspaces (W) ----------
    def t_workspace_read(self, agent: "Agent", args: dict[str, Any]) -> str:
        path = self._ws_path(agent, args.get("path"))
        try:
            offset = max(0, int(args.get("offset", 0)))
        except (TypeError, ValueError):
            offset = 0
        f = self.rt.memory.ws_read(path)
        if f is None:
            raise ToolError(f"no workspace file at {path}")
        return f"{path} ({len(f.content)} chars):\n" + truncate(
            f.content, READ_CAP, offset)

    def t_workspace_write(self, agent: "Agent", args: dict[str, Any]) -> str:
        path = self._ws_path(agent, args.get("path"))
        content = args.get("content")
        if not isinstance(content, str):
            raise ToolError("content must be a string")
        append = bool(args.get("append", False))
        cross = not path.startswith(f"agents/{agent.id}/")
        prev = self.rt.memory.ws_read(path)
        prev_chars = len(prev.content) if prev else 0
        f = self.rt.memory.ws_write(path, content, agent.id, append=append)
        self.rt.trace.log("ws_write", agent=agent.id, round=agent.rounds,
                          path=path, chars=len(content), append=append,
                          cross_workspace=cross)
        if cross:
            self.rt.trace.log("cross_workspace_write", agent=agent.id,
                              round=agent.rounds, path=path,
                              owner=path.split("/")[1], chars=len(content))
        self.rt.mark_dirty()
        verb = "appended to" if append else "wrote"
        note = " [CROSS-WORKSPACE WRITE — logged]" if cross else ""
        if not append and prev_chars > len(f.content):
            note += (f" [REPLACED previous {prev_chars} chars — this was an "
                     f"overwrite, not an extension; use append: true to extend]")
        return f"{verb} {path} (now {len(f.content)} chars){note}"

    def t_workspace_list(self, agent: "Agent", args: dict[str, Any]) -> str:
        prefix = str(args.get("prefix", "") or "")
        if not prefix:
            prefix = f"agents/{agent.id}/"
        elif not prefix.startswith("agents/"):
            prefix = f"agents/{prefix.rstrip('/')}/"
        files = self.rt.memory.ws_list(prefix)
        if not files:
            return f"(no workspace files under {prefix})"
        lines = [f"{f.path} · {len(f.content)} chars · last writer {f.author}"
                 for f in files]
        return truncate(f"{len(files)} files under {prefix}:\n" + "\n".join(lines),
                        LIST_CAP)

    # ---------- global memory (G) ----------
    def t_global_read(self, agent: "Agent", args: dict[str, Any]) -> str:
        path = self._g_path(args.get("path"))
        version = args.get("version")
        if version is not None:
            try:
                version = int(version)
            except (TypeError, ValueError):
                raise ToolError("version must be an integer") from None
        try:
            offset = max(0, int(args.get("offset", 0)))
        except (TypeError, ValueError):
            offset = 0
        v = self.rt.memory.g_read(path, agent.id, version)
        if v is None:
            raise ToolError(f"no global artifact at {path}"
                            + (f" version {version}" if version else ""))
        art = self.rt.memory.glob[path]
        div = " [DIVERGENCE FLAGGED]" if art.divergent else ""
        return (f"{path} v{v.version} (head v{art.head}, author {v.author},"
                f" {len(v.content)} chars){div}:\n"
                + truncate(v.content, READ_CAP, offset))

    def t_global_commit(self, agent: "Agent", args: dict[str, Any]) -> str:
        path = self._g_path(args.get("path"))
        src = args.get("from_workspace")
        if src is not None:
            # commit-by-reference: deliver a large workspace-assembled
            # artifact without re-emitting it through the output cap
            ws_path = self._ws_path(agent, src)
            f = self.rt.memory.ws_read(ws_path)
            if f is None:
                raise ToolError(f"from_workspace: no workspace file at {ws_path}")
            content = f.content
        else:
            content = args.get("content")
        if not isinstance(content, str):
            raise ToolError("content must be a string (or pass from_workspace)")
        summary = str(args.get("summary", "") or "")[:200]
        art, newly_div = self.rt.memory.g_commit(
            path, content, agent.id, agent.rounds, summary)
        self.rt.trace.log("g_commit", agent=agent.id, round=agent.rounds,
                          path=path, version=art.head, chars=len(content),
                          summary=summary, divergent=art.divergent)
        if newly_div:
            self.rt.trace.log("divergence_flagged", path=path, agent=agent.id,
                              head_author=art.versions[-2].author)
        self.rt.mark_dirty()
        div = (" [DIVERGENCE FLAGGED: you committed over another agent's head"
               " without having read it — both versions kept]") if newly_div else ""
        return f"committed {path} v{art.head} ({len(content)} chars){div}"

    def t_global_history(self, agent: "Agent", args: dict[str, Any]) -> str:
        path = self._g_path(args.get("path"))
        art = self.rt.memory.glob.get(path)
        if art is None or not art.versions:
            raise ToolError(f"no global artifact at {path}")
        lines = [f"v{v.version} · author {v.author} (round {v.round}) · "
                 f"{len(v.content)} chars · {v.summary or '(no summary)'}"
                 for v in art.versions[-HISTORY_CAP:]]
        head = (f"{path}: {len(art.versions)} versions, head v{art.head}"
                + (" [DIVERGENT]" if art.divergent else ""))
        return truncate(head + "\n" + "\n".join(lines), LIST_CAP)

    # ---------- circuit (C) ----------
    def t_circuit_inspect(self, agent: "Agent", args: dict[str, Any]) -> str:
        filt = str(args.get("filter", "") or "").lower()
        rows = [r.row() for r in self.rt.circuit.rules.values()]
        if filt:
            rows = [r for r in rows
                    if filt in json.dumps(r, ensure_ascii=False).lower()]
        if not rows:
            return "(no rules match)" if filt else "(no rules installed)"
        return truncate(json.dumps(rows, indent=1, ensure_ascii=False), LIST_CAP)

    def _echo_truth(self, condition: str) -> str:
        try:
            value = evaluate_condition(condition, self.rt.accessors())
            return f"condition is currently {value}"
        except ConditionError as exc:
            return f"condition currently unevaluable: {exc}"

    def _target(self, target: Any) -> dict[str, Any]:
        target = validate_target(target)
        if target["type"] == "resume" and self.rt.no_self_resume:
            raise ConditionError("target.type must be one of ['spawn']")
        return target

    def t_circuit_add_rule(self, agent: "Agent", args: dict[str, Any]) -> str:
        condition = args.get("condition")
        if not isinstance(condition, str) or not condition.strip():
            raise ToolError("condition must be a non-empty expression string")
        try:
            # author-time check is mechanical evaluability, not truth
            evaluate_condition(condition, self.rt.accessors())
        except ConditionError as exc:
            raise ToolError(f"condition unevaluable: {exc}") from None
        try:
            target = self._target(args.get("target"))
        except ConditionError as exc:
            raise ToolError(str(exc)) from None
        rule = self.rt.circuit.add(condition, target, agent.id, agent.rounds)
        self.rt.trace.log("rule_add", agent=agent.id, round=agent.rounds,
                          rule=rule.row())
        self.rt.mark_dirty()
        return f"added rule {rule.id}; {self._echo_truth(condition)}"

    def t_circuit_update_rule(self, agent: "Agent", args: dict[str, Any]) -> str:
        rule = self.rt.circuit.get(str(args.get("id", "")))
        if rule is None:
            raise ToolError(f"no rule with id '{args.get('id')}'")
        before = rule.row()
        changed = []
        if "condition" in args:
            condition = args["condition"]
            if not isinstance(condition, str) or not condition.strip():
                raise ToolError("condition must be a non-empty expression string")
            try:
                evaluate_condition(condition, self.rt.accessors())
            except ConditionError as exc:
                raise ToolError(f"condition unevaluable: {exc}") from None
            rule.condition = condition
            changed.append("condition")
        if "target" in args:
            try:
                rule.target = self._target(args["target"])
            except ConditionError as exc:
                raise ToolError(str(exc)) from None
            changed.append("target")
        if "fired" in args:
            rule.fired = bool(args["fired"])
            changed.append("fired")
        if "enabled" in args:
            rule.enabled = bool(args["enabled"])
            changed.append("enabled")
        if not changed:
            raise ToolError("update_rule: nothing to change "
                            "(accepted fields: condition, target, fired, enabled)")
        edit = {"by": agent.id, "round": agent.rounds, "before": before,
                "after": rule.row()}
        rule.edits.append(edit)
        self.rt.trace.log("rule_update", agent=agent.id, round=agent.rounds,
                          rule_id=rule.id, changed=changed, before=before,
                          after=rule.row())
        self.rt.mark_dirty()
        note = ""
        if "condition" in changed or "fired" in changed:
            note = "; " + self._echo_truth(rule.condition)
        return f"updated rule {rule.id} ({', '.join(changed)}){note}"

    def t_circuit_disable_rule(self, agent: "Agent", args: dict[str, Any]) -> str:
        rule = self.rt.circuit.get(str(args.get("id", "")))
        if rule is None:
            raise ToolError(f"no rule with id '{args.get('id')}'")
        before = rule.row()
        rule.enabled = False
        rule.edits.append({"by": agent.id, "round": agent.rounds,
                           "before": before, "after": rule.row()})
        self.rt.trace.log("rule_disable", agent=agent.id, round=agent.rounds,
                          rule_id=rule.id, before=before)
        self.rt.mark_dirty()
        return f"disabled rule {rule.id}"

    # ---------- lifecycle ----------
    def t_spawn(self, agent: "Agent", args: dict[str, Any]) -> str:
        task = args.get("task")
        if not isinstance(task, str) or not task.strip():
            raise ToolError("spawn requires a non-empty task string")
        capsule = str(args.get("capsule", "") or "")
        refs = args.get("initial_refs", [])
        if not isinstance(refs, list):
            raise ToolError("initial_refs must be a list of paths")
        refs = [str(r) for r in refs][:20]
        child = self.rt.spawn_agent(task=task.strip(), capsule=capsule,
                                    initial_refs=refs, parent=agent.id)
        result = f"spawned agent {child.id} (workspace agents/{child.id}/)"
        ocr = args.get("on_complete_rule")
        if ocr is not None:
            if not isinstance(ocr, dict) or not isinstance(ocr.get("condition"), str):
                return result + ("; ERROR: on_complete_rule must be an object "
                                 'with "condition" and "target" — rule NOT installed')
            raw = json.dumps(ocr, ensure_ascii=False)
            raw = raw.replace("{child}", child.id).replace("{self}", agent.id)
            ocr = json.loads(raw)
            try:
                evaluate_condition(ocr["condition"], self.rt.accessors())
                target = self._target(ocr.get("target"))
            except ConditionError as exc:
                return result + f"; ERROR: on_complete_rule invalid ({exc}) — rule NOT installed"
            rule = self.rt.circuit.add(ocr["condition"], target, agent.id,
                                       agent.rounds)
            self.rt.trace.log("rule_add", agent=agent.id, round=agent.rounds,
                              rule=rule.row(), via="spawn.on_complete_rule")
            result += f"; installed rule {rule.id}; {self._echo_truth(rule.condition)}"
        self.rt.mark_dirty()
        return result

    def t_wait(self, agent: "Agent", args: dict[str, Any]) -> str:
        condition = args.get("condition")
        if not isinstance(condition, str) or not condition.strip():
            raise ToolError("wait requires a condition expression string")
        try:
            value = evaluate_condition(condition, self.rt.accessors())
        except ConditionError as exc:
            raise ToolError(f"condition unevaluable: {exc}") from None
        rule = self.rt.circuit.add(condition,
                                   {"type": "resume", "agent_id": agent.id},
                                   agent.id, agent.rounds)
        agent.wait_rule = rule.id
        self.rt.set_state(agent, "waiting", reason=f"wait({condition})")
        return (f"suspended; resume rule {rule.id} installed; condition is "
                f"currently {value}"
                + (" (you will be resumed on the next state sweep)" if value else ""))

    def t_continue(self, agent: "Agent", args: dict[str, Any]) -> str:
        rule = self.rt.circuit.add("True",
                                   {"type": "resume", "agent_id": agent.id},
                                   agent.id, agent.rounds)
        agent.wait_rule = rule.id
        self.rt.set_state(agent, "waiting", reason="continue")
        return f"activation ends; immediate self-revive rule {rule.id} installed"

    def t_done(self, agent: "Agent", args: dict[str, Any]) -> str:
        agent.done_summary = str(args.get("summary", "") or "")
        self.rt.set_state(agent, "done", reason=agent.done_summary[:200])
        return "done recorded"

    def t_fail(self, agent: "Agent", args: dict[str, Any]) -> str:
        agent.fail_reason = str(args.get("reason", "") or "")
        self.rt.set_state(agent, "failed", reason=agent.fail_reason[:200])
        return "failure recorded"
