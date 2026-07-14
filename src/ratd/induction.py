"""EM3 failure induction — mechanized systemic failures for doctor validation.

The EM experiment spec (EM3) requires doctor pressure to be induced *in
the runner*, not by hand-editing state, so that every repair is
attributable to a reproducible cause. Blind defer is now unwritable
(B2), so the three reachable classes are induced here:

  H1  worker-failure injection — a designated leaf's worker call returns
      failed=true for all its pins (probability 1). Reaches the doctor
      via `failed` -> abandonment chain -> abandoned pins + dead
      downstream gates.
  H2  drop injection — a designated mid-tree agent is dropped right after
      it routes (its SPAWN side-effects stand; its own interface pins go
      unfulfilled). Reaches the doctor via abandoned interface pins ->
      unmet root pins.
  H3  fallback-write injection — a designated integrator's worker output
      is forced to miss its declared paths, driving execute()'s
      schema-mismatch fallback. Reaches the doctor via a fallback-marked
      write in the failure predicate (B5).

Selection is deterministic (temp-0 runs are reproducible): the induction
fires exactly once, on the first agent that matches the mode's rule, and
records its target for the dossier-correctness audit. Everything the
induction does is logged, so the audit can confirm the dossier names the
true cause.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .circuit import Circuit, gate_refs


@dataclass
class Induction:
    mode: str                       # "H1" | "H2" | "H3"
    fired: bool = False
    target: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    # ---- H1 / H3: replace the worker result before the model is called ----

    def worker_result(self, circuit: Circuit, agent: Any,
                      declared: list[dict[str, str]]) -> dict[str, Any] | None:
        """Return a forced worker document, or None to run the real worker.
        Fires at most once for the whole run."""
        if self.fired:
            return None
        paths = [o["path"] for o in declared]
        if self.mode == "H1":
            # first non-root executor that owns a pin some gate depends on:
            # guarantees a real dead downstream gate, not just a local fail.
            if agent.task_id == "root" or not _pins_gated(circuit, paths, agent.task_id):
                return None
            self._fire(agent.task_id, {"failed_pins": paths})
            return {"outputs": [
                {"path": p, "failed": True,
                 "reason": "[induced H1] worker failure injection"} for p in paths
            ]}
        if self.mode == "H3":
            # first gated integrator (or the root integrator): force its
            # declared paths to be missing -> execute() fallback path.
            if not (agent.worker_only and (agent.task_id == "root" or agent.condition)):
                return None
            self._fire(agent.task_id, {"forced_fallback_pins": paths})
            return {"outputs": [
                {"path": f"{agent.task_id}/_induced_mismatch",
                 "summary": "[induced H3] schema-mismatch injection",
                 "value": "[induced H3] this output deliberately misses the declared paths"}
            ]}
        return None

    # ---- H2: drop the agent immediately after it SPAWNs -------------------

    def drop_after_spawn(self, agent: Any) -> bool:
        if self.fired or self.mode != "H2":
            return False
        if agent.task_id == "root":
            return False  # a mid-tree agent, not the root
        self._fire(agent.task_id, {"dropped_after_spawn": True})
        return True

    def _fire(self, target: str, detail: dict[str, Any]) -> None:
        self.fired = True
        self.target = target
        self.detail = detail


def _pins_gated(circuit: Circuit, paths: list[str], agent_id: str) -> bool:
    """True if any live gate references one of these pins via done() or the
    owning agent via completed() — i.e. failing them kills a downstream
    gate."""
    pathset = set(paths)
    rows = circuit.db.execute(
        "SELECT condition FROM gates WHERE fired=0 AND dead=0").fetchall()
    for (condition,) in rows:
        done_refs, completed_refs = gate_refs(condition)
        if pathset.intersection(done_refs) or agent_id in completed_refs:
            return True
    return False
