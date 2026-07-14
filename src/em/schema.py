"""Adapters over the rebuilt store schema (src.ratd.store / .circuit).

The EM scorers must read the new tables:
  entries(address, summary, body, provenance, metadata, created_at)
  pins(address, owner, status, act, note, ...)
  conflicts / fetch_log / failures
  gates(id, condition, consequence, author, mechanism, fired, dead, ...)

The frozen Figure-1 and E1 scorers were written against the old
`entries(namespace_key, value, status)` schema. Rather than edit those
(the rubric-level logic is frozen), these helpers expose the same
address->text view the scorers consume, plus the new mechanical audits
the EM spec adds (catalog integrity, stub/family completeness).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from ..ratd import addresses
from ..ratd.circuit import gate_refs


def _connect(run_dir: Path) -> sqlite3.Connection | None:
    db_path = run_dir / "state.sqlite"
    if not db_path.exists():
        return None
    return sqlite3.connect(db_path)


def done_entries(run_dir: Path) -> dict[str, str]:
    """address -> body, for every entry whose pin is `done`. This is the
    exact analogue of the old scorers' `SELECT namespace_key, value WHERE
    status='done'` — the artifact text the run actually shipped."""
    db = _connect(run_dir)
    if db is None:
        return {}
    rows = db.execute(
        "SELECT e.address, e.body FROM entries e JOIN pins p ON p.address = e.address "
        "WHERE p.status = 'done'"
    ).fetchall()
    return {str(a): str(b) for a, b in rows}


def entry_rows(run_dir: Path) -> list[dict[str, Any]]:
    db = _connect(run_dir)
    if db is None:
        return []
    rows = db.execute(
        "SELECT address, summary, body, provenance, metadata FROM entries").fetchall()
    return [{"address": r[0], "summary": r[1], "body": r[2], "provenance": r[3],
             "metadata": json.loads(r[4]) if r[4] else {}} for r in rows]


def pin_rows(run_dir: Path) -> list[dict[str, Any]]:
    db = _connect(run_dir)
    if db is None:
        return []
    rows = db.execute("SELECT address, owner, status, act, note FROM pins").fetchall()
    return [{"address": r[0], "owner": r[1], "status": r[2], "act": r[3], "note": r[4]}
            for r in rows]


def gate_rows(run_dir: Path) -> list[dict[str, Any]]:
    db = _connect(run_dir)
    if db is None:
        return []
    rows = db.execute(
        "SELECT id, condition, author, mechanism, fired, dead FROM gates").fetchall()
    return [{"id": r[0], "condition": r[1], "author": r[2], "mechanism": r[3],
             "fired": bool(r[4]), "dead": bool(r[5])} for r in rows]


def counts(run_dir: Path) -> dict[str, int]:
    db = _connect(run_dir)
    if db is None:
        return {}
    one = lambda q: db.execute(q).fetchone()[0]
    return {
        "entries": one("SELECT COUNT(*) FROM entries"),
        "pins": one("SELECT COUNT(*) FROM pins"),
        "conflicts": one("SELECT COUNT(*) FROM conflicts"),
        "failures": one("SELECT COUNT(*) FROM failures"),
        "fetches": one("SELECT COUNT(*) FROM fetch_log"),
    }


def trace_events(run_dir: Path) -> list[dict[str, Any]]:
    trace = run_dir / "trace.jsonl"
    if not trace.exists():
        return []
    out = []
    for line in trace.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


# ---- G5: catalog integrity audit (the A2 uniform-creation check) --------

def catalog_audit(run_dir: Path) -> dict[str, Any]:
    """Every entry has a summary; every done pin's line is mechanically
    derivable (pin status + entry summary); zero orphan entries (a body
    with no pin). A promised/failed/abandoned pin legitimately has no
    entry — that is not an orphan; an *entry* with no *pin* is."""
    entries = entry_rows(run_dir)
    pins = {p["address"]: p for p in pin_rows(run_dir)}
    orphan_entries = [e["address"] for e in entries if e["address"] not in pins]
    missing_summary = [e["address"] for e in entries
                       if not isinstance(e["summary"], str) or not e["summary"].strip()]
    # done pins must resolve to an entry (fallback/promotion/worker all write one)
    done_without_entry = [a for a, p in pins.items()
                          if p["status"] == "done" and a not in {e["address"] for e in entries}]
    return {
        "entry_count": len(entries),
        "pin_count": len(pins),
        "orphan_entries": orphan_entries,
        "entries_missing_summary": missing_summary,
        "done_pins_without_entry": done_without_entry,
        "clean": not orphan_entries and not missing_summary and not done_without_entry,
    }


# ---- EM2: A5 assembly audit (stubs illegal, family completeness) --------

STUB_MAX_CHARS = 120  # a "stub" interface body that carries no real content


def family_audit_entries(entries: dict[str, str],
                         provenances: dict[str, str] | None = None) -> dict[str, Any]:
    """Core A5 audit over an address->body view (works for RATD's store and
    the planner's entries.json alike):
      - stub_outputs: a done entry whose body is a near-empty placeholder
        (the failure class A5 closes), or a fallback-provenance write.
      - incomplete_families: a numeric family `stem_{1..n}` where some
        `stem_i` member is missing.
      - oversize: single emissions over the 12k cap (provenance-flagged
        for RATD; length-flagged when no provenance is available).
    A run with stub_count 0 and no incomplete families is A5-clean."""
    provenances = provenances or {}
    stub_outputs = []
    for addr, body in entries.items():
        prov = provenances.get(addr)
        if prov in ("fallback", "worker_invalid") or len(body.strip()) <= STUB_MAX_CHARS:
            stub_outputs.append({"address": addr, "chars": len(body.strip()), "provenance": prov})

    stems: dict[str, set[int]] = {}
    for addr in entries:
        base, _, key = addr.partition("/")
        idx = _family_index(key)
        if idx is not None:
            stems.setdefault(f"{base}/{key.rsplit('_', 1)[0]}", set()).add(idx)
    incomplete_families = []
    for stem, present in stems.items():
        gaps = sorted(set(range(1, max(present) + 1)) - present)
        if gaps:
            incomplete_families.append({"stem": stem, "present": sorted(present),
                                        "missing_indices": gaps})

    oversize = [a for a, b in entries.items()
                if provenances.get(a) == "oversize_fallback" or len(b) > 12_000]
    return {
        "stub_outputs": stub_outputs,
        "stub_count": len(stub_outputs),
        "families": {s: sorted(v) for s, v in stems.items()},
        "incomplete_families": incomplete_families,
        "oversize": oversize,
    }


def family_audit(run_dir: Path) -> dict[str, Any]:
    """A5 audit for a RATD run: done entries + their provenance."""
    entries = {e["address"]: e for e in entry_rows(run_dir)}
    pins = {p["address"]: p for p in pin_rows(run_dir)}
    done = {a: e["body"] for a, e in entries.items()
            if a in pins and pins[a]["status"] == "done"}
    prov = {a: e["provenance"] for a, e in entries.items()}
    return family_audit_entries(done, prov)


def _family_index(key: str) -> int | None:
    stem, _, tail = key.rpartition("_")
    if stem and tail.isdigit():
        return int(tail)
    return None


# ---- EM1: list-mediated discovery (a LIST result fetched + used) --------

def list_mediated_discoveries(run_dir: Path) -> dict[str, Any]:
    """A `list` call is load-bearing when an address it surfaced is later
    FETCHed by the same agent and that agent then wires to / writes about
    it. We use the trace: for each `list` event, collect the addresses it
    returned (from the following context is not logged, so we approximate
    by the agent's subsequent `fetch` events whose address shares a
    namespace the LIST targeted), and count discoveries where a later
    fetch by that agent hit an address outside the agent's own subtree
    and ancestry — i.e. an address it could only have found by listing."""
    events = trace_events(run_dir)
    # per-agent ordered stream
    discoveries: list[dict[str, Any]] = []
    listed_prefixes: dict[str, list[str]] = {}  # agent -> prefixes it LISTed
    for ev in events:
        e = ev.get("event")
        if e == "list":
            agent = str(ev.get("agent"))
            listed_prefixes.setdefault(agent, []).append(str(ev.get("prefix")))
        elif e == "fetch" and ev.get("found", True) is not False:
            agent = str(ev.get("agent"))
            addr = str(ev.get("path"))
            if agent not in listed_prefixes:
                continue
            ns = addr.split("/")[0]
            own_or_ancestor = ns == agent or agent.startswith(ns + ".") or ns.startswith(agent + ".") \
                or agent.startswith(ns)
            if not own_or_ancestor:
                discoveries.append({"agent": agent, "address": addr})
    return {
        "list_calls": sum(len(v) for v in listed_prefixes.values()),
        "discoveries": discoveries,
        "discovery_count": len(discoveries),
    }


def ancestry_ns(agent_id: str) -> set[str]:
    return set(addresses.ancestor_namespaces(agent_id)) | {agent_id}
