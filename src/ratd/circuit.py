"""Circuit C — the control plane. Pins, gates, agent nodes, wiring.

Nothing in here is free-form text: pins and gates are rows, gate
conditions are a closed grammar (B1), every gate carries provenance
(B3), liveness and the failure predicate are runtime-evaluated (B4/B5),
and every agent transition is a logged event with a mechanical
signature (B7 / R2).

The single D->C edge is `fulfill`: a data-plane write flips a pin
promised -> done (or failed). Memory never triggers; it only fulfills.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from typing import Any, Callable

DONE_TERM_RE = re.compile(r'done\("([^"]+)"\)')
COMPLETED_TERM_RE = re.compile(r'completed\("([^"]+)"\)')

PIN_STATUSES = ("promised", "done", "failed", "abandoned")
LIVE_AGENT_STATES = {"promised", "queued", "routing", "executing", "sleeping"}
TERMINAL_FAILURE_STATES = {"failed", "dropped", "starved"}
AGENT_STATES = ("promised", "queued", "routing", "executing", "sleeping",
                "done", "failed", "dropped", "starved")
GATE_MECHANISMS = ("root-spawn", "deep-spawn", "self_role-gate", "defer-wake",
                   "system-default", "doctor-repair")


def gate_refs(condition: str) -> tuple[list[str], list[str]]:
    """Static scan: (done-term addresses, completed-term agent ids)."""
    return DONE_TERM_RE.findall(condition or ""), COMPLETED_TERM_RE.findall(condition or "")


class GateParser:
    """B1 grammar: done("address") | completed("agent_id"), AND/OR,
    parentheses. No fuzzy matching, ever."""

    def __init__(self, text: str, done_ok: Callable[[str], bool], completed_ok: Callable[[str], bool]):
        self.tokens = self._scan(text)
        self.done_ok = done_ok
        self.completed_ok = completed_ok
        self.i = 0

    def parse(self) -> bool:
        value = self._expr()
        if self.i != len(self.tokens):
            raise ValueError(f"unexpected token {self.tokens[self.i]}")
        return value

    def _expr(self) -> bool:
        value = self._term()
        while self._peek() == "OR":
            self.i += 1
            rhs = self._term()
            value = value or rhs
        return value

    def _term(self) -> bool:
        value = self._factor()
        while self._peek() == "AND":
            self.i += 1
            rhs = self._factor()
            value = value and rhs
        return value

    def _factor(self) -> bool:
        token = self._peek()
        if token == "(":
            self.i += 1
            value = self._expr()
            self._expect(")")
            return value
        if isinstance(token, tuple):
            self.i += 1
            kind, arg = token
            return self.done_ok(arg) if kind == "DONE" else self.completed_ok(arg)
        raise ValueError(f"expected term, got {token}")

    def _peek(self) -> Any:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _expect(self, token: str) -> None:
        if self._peek() != token:
            raise ValueError(f"expected {token}, got {self._peek()}")
        self.i += 1

    @staticmethod
    def _scan(text: str) -> list[Any]:
        tokens: list[Any] = []
        i = 0
        while i < len(text):
            if text[i].isspace():
                i += 1
            elif text.startswith("AND", i):
                tokens.append("AND")
                i += 3
            elif text.startswith("OR", i):
                tokens.append("OR")
                i += 2
            elif text[i] in "()":
                tokens.append(text[i])
                i += 1
            elif text.startswith('done("', i):
                j = text.find('")', i + 6)
                if j < 0:
                    raise ValueError("unterminated done() term")
                tokens.append(("DONE", text[i + 6 : j]))
                i = j + 2
            elif text.startswith('completed("', i):
                j = text.find('")', i + 11)
                if j < 0:
                    raise ValueError("unterminated completed() term")
                tokens.append(("COMPLETED", text[i + 11 : j]))
                i = j + 2
            else:
                raise ValueError(f"cannot tokenize condition near {text[i:i+20]!r}")
        return tokens


def check_gate_syntax(condition: str) -> str | None:
    """Syntax-only check; returns an error note or None."""
    try:
        GateParser(condition, lambda _: False, lambda _: False).parse()
    except ValueError as exc:
        return str(exc)
    return None


class Circuit:
    def __init__(self, db: sqlite3.Connection, log: Callable[..., None]):
        self.db = db
        self.log = log
        self._init_tables()

    def _init_tables(self) -> None:
        cur = self.db.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS pins("
            "address TEXT PRIMARY KEY, owner TEXT NOT NULL, status TEXT NOT NULL,"
            "act TEXT NOT NULL, note TEXT DEFAULT '', created_at REAL, updated_at REAL)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS gates("
            "id TEXT PRIMARY KEY, condition TEXT NOT NULL, consequence TEXT NOT NULL,"
            "author TEXT NOT NULL, mechanism TEXT NOT NULL,"
            "fired INTEGER DEFAULT 0, dead INTEGER DEFAULT 0, created_at REAL)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS agents("
            "agent_id TEXT PRIMARY KEY, state TEXT NOT NULL, depth INTEGER DEFAULT 0,"
            "parent TEXT, spec TEXT DEFAULT '', updated_at REAL)"
        )
        self.db.commit()

    # ---- pins (A2) -------------------------------------------------

    def create_pin(self, address: str, owner: str, act: str, note: str = "") -> bool:
        """Create at authoring time (all four acts: spawn / self_role /
        execute / promotion). Returns False if the pin already exists."""
        try:
            self.db.execute(
                "INSERT INTO pins(address, owner, status, act, note, created_at, updated_at)"
                " VALUES (?, ?, 'promised', ?, ?, ?, ?)",
                (address, owner, act, note[:160], time.time(), time.time()),
            )
        except sqlite3.IntegrityError:
            return False
        self.db.commit()
        self.log("pin_add", address=address, owner=owner, act=act)
        return True

    def pin(self, address: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT address, owner, status, act, note FROM pins WHERE address=?", (address,)
        ).fetchone()
        if row is None:
            return None
        return {"address": row[0], "owner": row[1], "status": row[2], "act": row[3], "note": row[4]}

    def pins_in_namespace(self, namespace: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT address, owner, status, note FROM pins WHERE address LIKE ? ORDER BY address",
            (f"{namespace}/%",),
        ).fetchall()
        return [{"address": r[0], "owner": r[1], "status": r[2], "note": r[3]} for r in rows]

    def pins_of_agent(self, agent_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT address, status FROM pins WHERE owner=? ORDER BY address", (agent_id,)
        ).fetchall()
        return [{"address": r[0], "status": r[1]} for r in rows]

    def set_pin_status(self, address: str, status: str) -> None:
        assert status in PIN_STATUSES
        self.db.execute(
            "UPDATE pins SET status=?, updated_at=? WHERE address=?", (status, time.time(), address)
        )
        self.db.commit()
        self.log("pin_status", address=address, status=status)

    def fulfill(self, address: str, *, failed: bool = False) -> None:
        """The only D->C edge: a conforming write flips promised -> done
        (or a reported failure flips it to failed)."""
        self.set_pin_status(address, "failed" if failed else "done")

    def reassign_pin(self, address: str, new_owner: str, mechanism: str) -> None:
        """Doctor-corrective only: re-own an unfulfilled pin (abandoned or
        promised) to a repair agent; status returns to promised."""
        self.db.execute(
            "UPDATE pins SET owner=?, status='promised', updated_at=? WHERE address=? AND status != 'done'",
            (new_owner, time.time(), address),
        )
        self.db.commit()
        self.log("pin_reassign", address=address, owner=new_owner, mechanism=mechanism)

    def done_addresses(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT address FROM pins WHERE status='done'")}

    # ---- agent nodes (B7) -------------------------------------------

    def create_agent(self, agent_id: str, state: str, depth: int, parent: str | None, spec_json: str) -> None:
        assert state in AGENT_STATES
        self.db.execute(
            "INSERT OR REPLACE INTO agents(agent_id, state, depth, parent, spec, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (agent_id, state, depth, parent, spec_json, time.time()),
        )
        self.db.commit()
        self.log("agent_state", agent=agent_id, state=state, transition="create")

    def set_agent_state(self, agent_id: str, state: str) -> None:
        """Every transition is a logged circuit event (R2). A terminal
        failure state triggers the A2 abandonment chain."""
        assert state in AGENT_STATES
        self.db.execute(
            "UPDATE agents SET state=?, updated_at=? WHERE agent_id=?", (state, time.time(), agent_id)
        )
        self.db.commit()
        self.log("agent_state", agent=agent_id, state=state)
        if state in TERMINAL_FAILURE_STATES:
            self._abandon_pins_of(agent_id)

    def set_agent_spec(self, agent_id: str, spec_json: str) -> None:
        self.db.execute("UPDATE agents SET spec=?, updated_at=? WHERE agent_id=?",
                        (spec_json, time.time(), agent_id))
        self.db.commit()

    def agent_row(self, agent_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT agent_id, state, depth, parent, spec FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
        if row is None:
            return None
        return {"agent_id": row[0], "state": row[1], "depth": row[2], "parent": row[3], "spec": row[4]}

    def agents_in_state(self, *states: str) -> list[dict[str, Any]]:
        marks = ",".join("?" for _ in states)
        rows = self.db.execute(
            f"SELECT agent_id, state, spec FROM agents WHERE state IN ({marks}) ORDER BY agent_id", states
        ).fetchall()
        return [{"agent_id": r[0], "state": r[1], "spec": r[2]} for r in rows]

    def _abandon_pins_of(self, agent_id: str) -> None:
        """Abandonment chain (A2, normative): terminal failure -> all the
        agent's promised pins flip to abandoned -> immediate liveness
        re-evaluation -> newly dead gates flagged mid-run."""
        rows = self.db.execute(
            "SELECT address FROM pins WHERE owner=? AND status='promised'", (agent_id,)
        ).fetchall()
        for (address,) in rows:
            self.set_pin_status(address, "abandoned")
        if rows:
            self.log("abandonment_chain", agent=agent_id, pins=[r[0] for r in rows])
            self.refresh_liveness(trigger="abandonment")

    # ---- gates (B1-B4) ----------------------------------------------

    def add_gate(self, gate_id: str, condition: str, consequence: dict[str, Any],
                 author: str, mechanism: str) -> None:
        assert mechanism in GATE_MECHANISMS
        self.db.execute(
            "INSERT OR REPLACE INTO gates(id, condition, consequence, author, mechanism, fired, dead, created_at)"
            " VALUES (?, ?, ?, ?, ?, 0, 0, ?)",
            (gate_id, condition, json.dumps(consequence), author, mechanism, time.time()),
        )
        self.db.commit()
        self.log("gate_add", id=gate_id, condition=condition, author=author, mechanism=mechanism)

    def _done_ok(self, address: str) -> bool:
        pin = self.pin(address)
        return pin is not None and pin["status"] == "done"

    def _completed_ok(self, agent_id: str) -> bool:
        """completed(a): the agent node is done and all its pins are done."""
        agent = self.agent_row(agent_id)
        if agent is None or agent["state"] != "done":
            return False
        return all(p["status"] == "done" for p in self.pins_of_agent(agent_id))

    def evaluate(self, condition: str) -> bool:
        return GateParser(condition, self._done_ok, self._completed_ok).parse()

    def fire_ready(self, enqueue: Callable[[dict[str, Any], str], None]) -> int:
        """Evaluate every unfired live gate; exactly-once firing is an
        atomic check-and-set on the fired flag (rowcount-guarded CAS —
        the invariant B1 requires under concurrency, honored today)."""
        fired = 0
        rows = self.db.execute(
            "SELECT id, condition, consequence FROM gates WHERE fired=0 AND dead=0"
        ).fetchall()
        for gate_id, condition, consequence in rows:
            try:
                ready = self.evaluate(str(condition))
            except ValueError as exc:
                # unreachable for validated wiring; logged, never silent
                self.log("gate_error", id=gate_id, condition=condition, error=str(exc))
                continue
            if not ready:
                continue
            cur = self.db.execute("UPDATE gates SET fired=1 WHERE id=? AND fired=0", (gate_id,))
            self.db.commit()
            if cur.rowcount == 1:
                self.log("gate_fire", id=gate_id, condition=condition)
                enqueue(json.loads(consequence), gate_id)
                fired += 1
        return fired

    def _ref_satisfiable(self, kind: str, arg: str) -> bool:
        """B4: a done() ref is satisfiable if its pin is done, or promised
        with a live/sleeping owner. A completed() ref is satisfiable if
        the agent is live, or already done with all pins done."""
        if kind == "DONE":
            pin = self.pin(arg)
            if pin is None:
                return False
            if pin["status"] == "done":
                return True
            if pin["status"] != "promised":
                return False
            owner = self.agent_row(pin["owner"])
            return owner is not None and owner["state"] in LIVE_AGENT_STATES
        agent = self.agent_row(arg)
        if agent is None:
            return False
        if agent["state"] in LIVE_AGENT_STATES:
            return True
        if agent["state"] == "done":
            return all(p["status"] == "done" for p in self.pins_of_agent(arg))
        return False

    def refresh_liveness(self, trigger: str) -> list[str]:
        """Recompute the dead flag for every unfired gate. Newly dead
        gates log a warning event mid-run (consumption happens at
        quiescence, via the doctor). Returns newly dead gate ids."""
        newly_dead: list[str] = []
        rows = self.db.execute("SELECT id, condition, dead FROM gates WHERE fired=0").fetchall()
        for gate_id, condition, was_dead in rows:
            done_refs, completed_refs = gate_refs(str(condition))
            satisfiable = all(self._ref_satisfiable("DONE", a) for a in done_refs) and all(
                self._ref_satisfiable("COMPLETED", a) for a in completed_refs
            )
            if not satisfiable and not was_dead:
                self.db.execute("UPDATE gates SET dead=1 WHERE id=?", (gate_id,))
                self.log("gate_dead", id=gate_id, condition=condition, trigger=trigger)
                newly_dead.append(str(gate_id))
            elif satisfiable and was_dead:
                self.db.execute("UPDATE gates SET dead=0 WHERE id=?", (gate_id,))
                self.log("gate_revive", id=gate_id, condition=condition, trigger=trigger)
        self.db.commit()
        return newly_dead

    def dead_gates(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT id, condition, consequence, author, mechanism FROM gates WHERE fired=0 AND dead=1"
        ).fetchall()
        out = []
        for gate_id, condition, consequence, author, mechanism in rows:
            done_refs, completed_refs = gate_refs(str(condition))
            unresolvable = [a for a in done_refs if not self._ref_satisfiable("DONE", a)] + [
                f"completed({a})" for a in completed_refs if not self._ref_satisfiable("COMPLETED", a)
            ]
            out.append({
                "id": gate_id, "condition": condition, "author": author,
                "mechanism": mechanism, "unresolvable_refs": unresolvable,
                "consequence_agent": json.loads(consequence).get("agent", {}).get("task_id"),
            })
        return out

    def fireable_exists(self) -> bool:
        rows = self.db.execute("SELECT condition FROM gates WHERE fired=0 AND dead=0").fetchall()
        for (condition,) in rows:
            try:
                if self.evaluate(str(condition)):
                    return True
            except ValueError:
                continue
        return False

    def gates_waking(self, agent_id: str) -> list[dict[str, Any]]:
        """Unfired gates whose consequence re-enqueues the given agent."""
        rows = self.db.execute(
            "SELECT id, condition, dead, consequence FROM gates WHERE fired=0"
        ).fetchall()
        out = []
        for gate_id, condition, dead, consequence in rows:
            if json.loads(consequence).get("agent", {}).get("task_id") == agent_id:
                out.append({"id": gate_id, "condition": condition, "dead": bool(dead)})
        return out

    # ---- B5: quiescence and the failure predicate --------------------

    def quiescent(self, queue_empty: bool, in_flight: int = 0) -> bool:
        """queue empty AND no agent in-flight AND no fireable gates.
        in_flight is 0 in the sequential runtime; the parameter exists
        because the definition must already be race-safe (B5)."""
        return queue_empty and in_flight == 0 and not self.fireable_exists()

    def unmet_root_pins(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT address, owner, status, note FROM pins WHERE address LIKE 'root/%' AND status != 'done'"
            " ORDER BY address"
        ).fetchall()
        return [{"address": r[0], "owner": r[1], "status": r[2], "note": r[3]} for r in rows]

    def abandoned_pins(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT address, owner FROM pins WHERE status='abandoned' ORDER BY address"
        ).fetchall()
        out = []
        for address, owner in rows:
            agent = self.agent_row(str(owner))
            out.append({"address": address, "owner": owner,
                        "owner_state": agent["state"] if agent else "(no node)"})
        return out

    def sleepers(self) -> list[dict[str, Any]]:
        """Sleeping agents with their wake gates; a sleeper whose every
        wake gate is dead is starved (B7)."""
        out = []
        for agent in self.agents_in_state("sleeping"):
            gates = self.gates_waking(agent["agent_id"])
            starved = bool(gates) and all(g["dead"] for g in gates)
            out.append({"agent_id": agent["agent_id"], "wake_gates": gates, "starved": starved})
        return out

    def mark_starved(self) -> list[str]:
        starved = [s["agent_id"] for s in self.sleepers() if s["starved"]]
        for agent_id in starved:
            self.set_agent_state(agent_id, "starved")
        return starved

    def failure_report(self, fallback_writes: list[dict[str, Any]]) -> dict[str, Any]:
        """B5: systemic failure := unmet root pins OR dead gates OR
        fallback-marked writes OR abandoned pins. Circuit spec, not
        doctor-private logic; fallback writes come from the store."""
        report = {
            "unmet_root_pins": self.unmet_root_pins(),
            "dead_gates": self.dead_gates(),
            "abandoned_pins": self.abandoned_pins(),
            "fallback_writes": fallback_writes,
        }
        report["failing"] = any(bool(v) for v in report.values())
        return report

    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for status in PIN_STATUSES:
            c[f"pins_{status}"] = self.db.execute(
                "SELECT COUNT(*) FROM pins WHERE status=?", (status,)
            ).fetchone()[0]
        c["pins_total"] = sum(c[f"pins_{s}"] for s in PIN_STATUSES)
        c["gates_total"] = self.db.execute("SELECT COUNT(*) FROM gates").fetchone()[0]
        c["gates_fired"] = self.db.execute("SELECT COUNT(*) FROM gates WHERE fired=1").fetchone()[0]
        c["gates_dead"] = self.db.execute("SELECT COUNT(*) FROM gates WHERE fired=0 AND dead=1").fetchone()[0]
        return c
