"""Circuit C — Playground Spec v2 §3.

Rules are state rows (φ condition, σ target, fired flag, provenance).
Conditions are Python boolean expression strings evaluated via
restricted-namespace eval: ONLY the read-only state accessors, empty
builtins, an expression length cap, and a wall-clock evaluation
timeout. Evaluation errors are tool errors (mechanical rejection,
not policy). Authorship is unrestricted; every edit (any agent, any
rule, including fired-flag resets) is provenance-logged before/after.
Exactly-once firing per armed state via CAS on the fired flag (the
runtime is serial, so test-and-set is atomic by construction).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

CONDITION_MAX_CHARS = 2000
EVAL_TIMEOUT_S = 2.0
ACCESSOR_NAMES = ("exists", "head", "field", "state", "children", "fired",
                  "matching", "count")


class ConditionError(Exception):
    """Mechanical unevaluability — surfaced to the author as a tool error."""


@dataclass
class Rule:
    id: str
    condition: str
    target: dict[str, Any]     # {"type":"spawn",...} | {"type":"resume","agent_id":...}
    author: str
    author_round: int
    fired: bool = False
    enabled: bool = True
    fired_count: int = 0       # total times fired across re-arms
    edits: list[dict[str, Any]] = field(default_factory=list)

    def row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "condition": self.condition,
            "target": self.target,
            "fired": self.fired,
            "enabled": self.enabled,
            "author": self.author,
        }


def _eval_worker(expr: str, namespace: dict[str, Any],
                 out: dict[str, Any]) -> None:
    try:
        out["value"] = eval(expr, {"__builtins__": {}}, namespace)  # noqa: S307
    except Exception as exc:  # noqa: BLE001 — any error is a mechanical rejection
        out["error"] = f"{type(exc).__name__}: {exc}"


def evaluate_condition(expr: str, accessors: dict[str, Callable[..., Any]]) -> bool:
    """Restricted eval with timeout. Raises ConditionError on any failure."""
    if not isinstance(expr, str) or not expr.strip():
        raise ConditionError("condition must be a non-empty expression string")
    if len(expr) > CONDITION_MAX_CHARS:
        raise ConditionError(f"condition exceeds {CONDITION_MAX_CHARS} chars")
    namespace = dict(accessors)
    out: dict[str, Any] = {}
    t = threading.Thread(target=_eval_worker, args=(expr, namespace, out),
                         daemon=True)
    t.start()
    t.join(EVAL_TIMEOUT_S)
    if t.is_alive():
        raise ConditionError(f"evaluation timed out after {EVAL_TIMEOUT_S}s")
    if "error" in out:
        raise ConditionError(out["error"])
    return bool(out.get("value"))


VALID_TARGET_TYPES = {"spawn", "resume"}


def validate_target(target: Any) -> dict[str, Any]:
    """Mechanical shape check only (unevaluable targets are tool errors)."""
    if not isinstance(target, dict):
        raise ConditionError('target must be an object, e.g. {"type":"spawn",'
                             '"task":"...","capsule":"..."} or '
                             '{"type":"resume","agent_id":"..."}')
    ttype = target.get("type")
    if ttype not in VALID_TARGET_TYPES:
        raise ConditionError(f'target.type must be one of {sorted(VALID_TARGET_TYPES)}')
    if ttype == "spawn":
        if not isinstance(target.get("task"), str) or not target["task"].strip():
            raise ConditionError("spawn target requires a non-empty task string")
        target.setdefault("capsule", "")
        refs = target.setdefault("initial_refs", [])
        if not isinstance(refs, list):
            raise ConditionError("initial_refs must be a list of paths")
    else:
        if not isinstance(target.get("agent_id"), str):
            raise ConditionError("resume target requires agent_id")
    return target


class Circuit:
    def __init__(self) -> None:
        self.rules: dict[str, Rule] = {}
        self._next = 0

    def new_id(self) -> str:
        self._next += 1
        return f"r{self._next}"

    def add(self, condition: str, target: dict[str, Any], author: str,
            author_round: int) -> Rule:
        rule = Rule(id=self.new_id(), condition=condition, target=target,
                    author=author, author_round=author_round)
        self.rules[rule.id] = rule
        return rule

    def get(self, rule_id: str) -> Optional[Rule]:
        return self.rules.get(rule_id)

    def armed(self) -> list[Rule]:
        return [r for r in self.rules.values() if r.enabled and not r.fired]

    def sweep(self, accessors: dict[str, Callable[..., Any]]
              ) -> tuple[list[Rule], list[tuple[Rule, str]]]:
        """Evaluate every armed rule; CAS-fire the true ones.

        Returns (fired_rules, [(rule, error)] for eval failures).
        Errors leave the rule armed (it may become evaluable later —
        e.g. a field() over an artifact not yet written is just False,
        but a genuinely malformed expression will error every sweep;
        both are logged, neither is repaired: stance 2).
        """
        fired: list[Rule] = []
        errors: list[tuple[Rule, str]] = []
        for rule in self.armed():
            try:
                value = evaluate_condition(rule.condition, accessors)
            except ConditionError as exc:
                errors.append((rule, str(exc)))
                continue
            if value and not rule.fired:   # CAS: serial runtime, atomic
                rule.fired = True
                rule.fired_count += 1
                fired.append(rule)
        return fired, errors
