"""Action-document validation, including B2 wiring validity.

A gate (spawn condition, self_role condition, wake condition) may
reference only pins / agent nodes that exist at authoring time — plus,
for a SPAWN act, the pins and agent nodes that same act creates. Hard
reject otherwise; the repair feedback lists the actual pins in the
referenced namespaces (the one-round-trip fix L3_r1 needed).
Consequence: blind defer is unwritable.
"""
from __future__ import annotations

import json
from typing import Any

from . import addresses
from .circuit import Circuit, check_gate_syntax, gate_refs

READ_ACTIONS = {"LIST", "FETCH"}
FINAL_ACTIONS = {"EXECUTE", "SPAWN", "DEFER"}
MAX_FETCH_ADDRESSES = 8


def valid_outputs(outputs: Any) -> bool:
    if not isinstance(outputs, list) or not outputs:
        return False
    for output in outputs:
        if not isinstance(output, dict):
            return False
        if not isinstance(output.get("path"), str) or not output["path"].strip():
            return False
        if not isinstance(output.get("description"), str) or not output["description"].strip():
            return False
    return True


def pins_feedback(circuit: Circuit, ref: str) -> str:
    """B2 repair feedback: the actual pins in the referenced namespace."""
    namespace = ref.split("/")[0]
    pins = circuit.pins_in_namespace(namespace)
    if not pins:
        return f"no pins exist in namespace {namespace}/"
    listing = "; ".join(f"{p['address']} ({p['status']})" for p in pins[:12])
    return f"actual pins in {namespace}/: {listing}"


def check_wiring(condition: str, circuit: Circuit, act_pins: set[str],
                 act_agents: set[str], owner: str) -> list[str]:
    """B2: syntax, then every ref must resolve to an existing pin/agent
    node or one created by this same act."""
    notes: list[str] = []
    syntax = check_gate_syntax(condition)
    if syntax:
        return [f"{owner} condition uses unsupported syntax: {syntax}"]
    done_refs, completed_refs = gate_refs(condition)
    if not done_refs and not completed_refs:
        notes.append(f"{owner} condition has no done()/completed() terms")
    for ref in done_refs:
        if ref in act_pins or circuit.pin(ref) is not None:
            continue
        notes.append(
            f"{owner} condition references done(\"{ref}\") but no such pin exists; "
            + pins_feedback(circuit, ref)
        )
    for ref in completed_refs:
        if ref not in act_agents and circuit.agent_row(ref) is None:
            notes.append(
                f"{owner} condition references completed(\"{ref}\") but no such agent node exists"
            )
    return notes


def check_output_paths(outputs: list[dict[str, Any]], producer_ns: str, owed: set[str],
                       circuit: Circuit, *, system: bool, label: str) -> list[str]:
    """A1 grammar + A3 ownership: paths sit under the producer's own
    namespace or are one of its owed (inherited interface) pins. A path
    whose pin already exists and is not owed is a wiring error — pins
    are created by exactly one authoring act."""
    notes: list[str] = []
    for output in outputs:
        path = str(output["path"])
        err = addresses.address_error(path, system=system)
        if err:
            notes.append(f"{label}: {err}")
            continue
        if not path.startswith(f"{producer_ns}/") and path not in owed:
            notes.append(
                f"{label}: output {path} must be under {producer_ns}/ or one of the assigned interface pins"
            )
            continue
        for concrete in addresses.expand_family(path):
            pin = circuit.pin(concrete)
            if pin is not None and concrete not in owed:
                notes.append(
                    f"{label}: pin {concrete} already exists (owner {pin['owner']}, {pin['status']}) — "
                    "declare a different key or reference the existing pin instead"
                )
    return notes


def validate_action(raw: str, agent: Any, circuit: Circuit) -> tuple[dict[str, Any] | None, list[str]]:
    """agent needs: task_id, expected_outputs, system (bool). Returns the
    parsed document plus validation notes (empty notes = accepted)."""
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"raw strict JSON parse failed: {exc.msg}"]
    if not isinstance(doc, dict):
        return None, ["raw strict JSON is not an object"]

    notes: list[str] = []
    owed = {str(o["path"]) for o in agent.expected_outputs if isinstance(o, dict) and "path" in o}
    action = doc.get("action")

    if action in READ_ACTIONS:
        if action == "LIST":
            prefix = doc.get("namespace_prefix")
            if prefix is not None and not isinstance(prefix, str):
                notes.append("LIST namespace_prefix must be null or a namespace string")
            if "k" in doc and not isinstance(doc.get("k"), int):
                notes.append("LIST k must be an integer")
        else:
            addrs = doc.get("addresses")
            if not isinstance(addrs, list) or not addrs or not all(isinstance(a, str) for a in addrs):
                notes.append("FETCH requires a non-empty addresses list of strings")
            elif len(addrs) > MAX_FETCH_ADDRESSES:
                notes.append(f"FETCH is capped at {MAX_FETCH_ADDRESSES} addresses per call")
        return doc, notes

    if doc.get("task_id") != agent.task_id:
        notes.append(f"task_id must be {agent.task_id}")
    reasoning = doc.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        notes.append("missing non-empty reasoning")
    if action not in FINAL_ACTIONS:
        notes.append("action must be EXECUTE, SPAWN, DEFER, LIST, or FETCH")
        return doc, notes

    if action == "EXECUTE":
        outputs = doc.get("result_outputs")
        if not valid_outputs(outputs):
            notes.append("EXECUTE requires result_outputs with path/description")
        else:
            notes.extend(check_output_paths(outputs, agent.task_id, owed, circuit,
                                            system=agent.system, label="EXECUTE"))

    elif action == "SPAWN":
        subtasks = doc.get("subtasks")
        role = doc.get("self_role")
        if not isinstance(subtasks, list) or not subtasks:
            notes.append("SPAWN requires non-empty subtasks")
            return doc, notes
        expected_ids = [f"{agent.task_id}.{i}" for i in range(1, len(subtasks) + 1)]
        act_pins: set[str] = set()
        act_agents: set[str] = {agent.task_id}
        declared_outputs: set[str] = set()
        for idx, subtask in enumerate(subtasks):
            if not isinstance(subtask, dict):
                notes.append("subtask must be an object")
                continue
            sid = subtask.get("id")
            if sid != expected_ids[idx]:
                notes.append(f"subtask id must be {expected_ids[idx]}, got {sid}")
            if isinstance(sid, str):
                act_agents.add(sid)
            for key in ("goal", "capsule"):
                if not isinstance(subtask.get(key), str) or not subtask[key].strip():
                    notes.append(f"subtask {sid} missing {key}")
            outputs = subtask.get("outputs")
            if not valid_outputs(outputs):
                notes.append(f"subtask {sid} requires outputs with path/description")
            elif isinstance(sid, str):
                notes.extend(check_output_paths(outputs, sid, owed, circuit,
                                                system=agent.system, label=f"subtask {sid}"))
                for output in outputs:
                    for concrete in addresses.expand_family(str(output["path"])):
                        act_pins.add(concrete)
                        declared_outputs.add(concrete)
            condition = subtask.get("condition")
            if condition is not None and not isinstance(condition, str):
                notes.append(f"subtask {sid} condition must be null or string")

        self_paths: set[str] = set()
        if not isinstance(role, dict):
            notes.append(
                "SPAWN requires a self_role object: the job you yourself take "
                "(a parallel share, the gated integrating job, or a review job) with at least one output"
            )
        else:
            if not isinstance(role.get("goal"), str) or not role["goal"].strip():
                notes.append("self_role missing non-empty goal")
            role_outputs = role.get("outputs")
            if not valid_outputs(role_outputs):
                notes.append("self_role requires outputs with path/description (declare at least one output YOU will write)")
            else:
                notes.extend(check_output_paths(role_outputs, agent.task_id, owed, circuit,
                                                system=agent.system, label="self_role"))
                for output in role_outputs:
                    for concrete in addresses.expand_family(str(output["path"])):
                        self_paths.add(concrete)
                        act_pins.add(concrete)
            if role.get("condition") is not None and not isinstance(role["condition"], str):
                notes.append("self_role condition must be null or string")

        missing_interface = owed - declared_outputs - self_paths
        if missing_interface:
            notes.append(
                "your assigned interface pins "
                + ", ".join(sorted(missing_interface))
                + " are not produced by any subtask or by your self_role; assign each to exactly one producer"
                " (usually your own integrating self_role)"
            )
        # B2 over every condition in the act, with same-act pins visible
        conditions = [(str(s.get("id")), s["condition"]) for s in subtasks
                      if isinstance(s, dict) and isinstance(s.get("condition"), str)]
        if isinstance(role, dict) and isinstance(role.get("condition"), str):
            conditions.append(("self_role", role["condition"]))
        for owner, condition in conditions:
            notes.extend(check_wiring(condition, circuit, act_pins | owed, act_agents, owner))

    elif action == "DEFER":
        wake = doc.get("wake_condition")
        if not isinstance(wake, str) or not wake.strip():
            notes.append("DEFER requires wake_condition")
        else:
            # B2 with no same-act pins: a wake may only wire to what exists.
            notes.extend(check_wiring(wake, circuit, set(), set(), "wake"))
    return doc, notes
