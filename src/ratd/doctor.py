"""The Doctor — first occupant of the B6 system layer (C1-C5).

Trigger: quiescence AND systemic failure (B5), K-bounded per run,
inside the global call rail. The dossier is entirely mechanically
derived (C2). Privileges are additive + corrective (C3): spawn repair
agents, install wake gates, re-enqueue sleepers with corrected gates —
never retire or edit another author's gates (that action does not
exist). Accounting (C4): the failure predicate re-runs after the
repair subtree quiesces; a doctored run reports converged-with-repair,
never plain converged. Boundary (C5): systemic failures only.
"""
from __future__ import annotations

import json
from typing import Any

from . import addresses
from .circuit import Circuit
from .store import Store
from .validate import check_wiring, valid_outputs, check_output_paths

DOCTOR_K = 2  # C1: bounded doctor cycles per run
DOCTOR_NS = "_doctor"


def build_dossier(circuit: Circuit, store: Store, prior_cycles: list[dict[str, Any]]) -> dict[str, Any]:
    """C2 — all mechanical, no interpretation. Dead gates carry the
    actual pin list per referenced namespace: the string delta the
    blind-deferring agent could not see."""
    dead = circuit.dead_gates()
    for gate in dead:
        namespaces = sorted({ref.split("/")[0] for ref in gate["unresolvable_refs"] if "/" in ref})
        gate["pins_in_referenced_namespaces"] = {
            ns: [f"{p['address']} ({p['status']})" + (f" — {p['note']}" if p["note"] else "")
                 for p in circuit.pins_in_namespace(ns)]
            for ns in namespaces
        }
    return {
        "dead_gates": dead,
        "unmet_root_pins": circuit.unmet_root_pins(),
        "abandoned_pins": circuit.abandoned_pins(),
        "failed_pins": store.failures(),
        "fallback_writes": store.fallback_writes(),
        "sleepers": circuit.sleepers(),
        "prior_doctor_cycles": prior_cycles,
    }


def dossier_text(dossier: dict[str, Any]) -> str:
    return json.dumps(dossier, indent=2, ensure_ascii=False)


def validate_repair(raw: str, circuit: Circuit, next_repair_index: int) -> tuple[dict[str, Any] | None, list[str]]:
    """Structural + privilege validation of the doctor's action document.
    The doctor is a system agent: it may target the reserved _doctor
    namespace, may re-own unfulfilled pins, and nothing more."""
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"raw strict JSON parse failed: {exc.msg}"]
    if not isinstance(doc, dict):
        return None, ["raw strict JSON is not an object"]
    notes: list[str] = []
    if doc.get("action") != "REPAIR":
        notes.append('action must be "REPAIR"')
    if not isinstance(doc.get("reasoning"), str) or not doc["reasoning"].strip():
        notes.append("missing non-empty reasoning")

    repair_agents = doc.get("repair_agents") or []
    wake_overrides = doc.get("wake_overrides") or []
    if not isinstance(repair_agents, list) or not isinstance(wake_overrides, list):
        return doc, notes + ["repair_agents and wake_overrides must be lists"]
    if not repair_agents and not wake_overrides:
        notes.append("a repair must contain at least one repair_agent or wake_override")

    act_pins: set[str] = set()
    act_agents: set[str] = set()
    for idx, spec in enumerate(repair_agents):
        if not isinstance(spec, dict):
            notes.append("repair_agent must be an object")
            continue
        expected_id = f"{DOCTOR_NS}.{next_repair_index + idx}"
        if spec.get("id") != expected_id:
            notes.append(f"repair_agent id must be {expected_id}, got {spec.get('id')}")
        else:
            act_agents.add(expected_id)
        for key in ("goal", "capsule"):
            if not isinstance(spec.get(key), str) or not spec[key].strip():
                notes.append(f"repair_agent {spec.get('id')} missing {key}")
        outputs = spec.get("outputs")
        if not valid_outputs(outputs):
            notes.append(f"repair_agent {spec.get('id')} requires outputs with path/description")
            continue
        for output in outputs:
            path = str(output["path"])
            err = addresses.address_error(path, system=True)
            if err:
                notes.append(f"repair_agent {spec.get('id')}: {err}")
                continue
            for concrete in addresses.expand_family(path):
                pin = circuit.pin(concrete)
                if pin is None:
                    # new work must live in the doctor's own namespace
                    if not concrete.startswith(f"{expected_id}/"):
                        notes.append(
                            f"repair_agent {spec.get('id')}: {concrete} is neither an existing "
                            f"unfulfilled pin (corrective) nor under {expected_id}/ (additive)"
                        )
                elif pin["status"] == "done":
                    notes.append(
                        f"repair_agent {spec.get('id')}: pin {concrete} is already done — "
                        "the doctor repairs unfulfilled pins only"
                    )
                act_pins.add(concrete)
        condition = spec.get("condition")
        if condition is not None and not isinstance(condition, str):
            notes.append(f"repair_agent {spec.get('id')} condition must be null or string")
        elif isinstance(condition, str):
            notes.extend(check_wiring(condition, circuit, act_pins, act_agents, f"repair_agent {spec.get('id')}"))

    for override in wake_overrides:
        if not isinstance(override, dict):
            notes.append("wake_override must be an object")
            continue
        agent_id = override.get("agent_id")
        row = circuit.agent_row(str(agent_id)) if isinstance(agent_id, str) else None
        if row is None or row["state"] not in {"sleeping", "starved"}:
            notes.append(f"wake_override target {agent_id} is not a sleeping/starved agent")
        condition = override.get("condition")
        if condition is not None and not isinstance(condition, str):
            notes.append(f"wake_override {agent_id} condition must be null or string")
        elif isinstance(condition, str):
            notes.extend(check_wiring(condition, circuit, act_pins, act_agents, f"wake_override {agent_id}"))
    return doc, notes
