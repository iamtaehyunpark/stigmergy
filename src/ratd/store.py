"""Memory D — the data plane: catalog + store.

A3: write-once, first-writer-wins; a second write lands in the
conflicts table (observability for theory §4) and never modifies the
entry. A4: open-read — any agent may fetch any done entry; the only
constraints are budgets (R1), the only record is the fetch log. A5:
structured entries (summary <= 160 / body / metadata) and two bounded
read primitives, list and fetch, with visible truncation (fig1 v1's
silent slice is prohibited). A6: the catalog is the circuit's
mechanical shadow — address + status from pins, summary from entries.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Callable

from .circuit import Circuit

SUMMARY_MAX = 160
DEFAULT_LIST_K = 20
MAX_LIST_K = 50
ROUTING_FETCH_BUDGET = 8_000    # chars, per routing step, across fetches
WORKER_FETCH_BUDGET = 24_000    # chars, per worker step
SINGLE_EMISSION_MAX = 12_000    # A5 output rule: larger artifacts must be numeric families
# B5 failure predicate inputs. oversize_fallback is deliberately NOT here:
# a single artifact over the 12k A5 cap is still delivered (full body stored,
# tagged oversize_fallback on the entry, visibly truncated on FETCH) — it's
# observable (see schema.family_audit), not a systemic failure. Only a
# substituted/omitted body (fallback, worker_invalid) counts as failing.
# (Design call, 2026-07-13: oversize = observable, not failure.)
FALLBACK_PROVENANCES = ("fallback", "worker_invalid")


class Store:
    def __init__(self, db: sqlite3.Connection, log: Callable[..., None]):
        self.db = db
        self.log = log
        self._init_tables()

    def _init_tables(self) -> None:
        cur = self.db.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS entries("
            "address TEXT PRIMARY KEY, summary TEXT NOT NULL, body TEXT NOT NULL,"
            "provenance TEXT NOT NULL, metadata TEXT NOT NULL, created_at REAL)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS conflicts("
            "address TEXT, summary TEXT, body TEXT, author TEXT, created_at REAL)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS fetch_log("
            "agent TEXT, address TEXT, chars INTEGER, truncated INTEGER, ts REAL)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS failures("
            "address TEXT, reason TEXT, author TEXT, created_at REAL)"
        )
        self.db.commit()

    # ---- writes (A3) -------------------------------------------------

    def write(self, address: str, summary: str, body: str, author: str,
              provenance: str, extra: dict[str, Any] | None = None) -> str:
        """Returns 'written' or 'conflict'. Summary over-length is clamped
        mechanically and recorded in metadata (runtime-derived guarantee,
        R4 — never left to agent discipline)."""
        now = time.time()
        summary = summary or ""
        clamped = len(summary) > SUMMARY_MAX
        metadata = {
            "author": author,
            "created_at": now,
            "content_length": len(body),
            "provenance": provenance,
            **({"summary_clamped": True} if clamped else {}),
            **(extra or {}),
        }
        try:
            self.db.execute(
                "INSERT INTO entries(address, summary, body, provenance, metadata, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (address, summary[:SUMMARY_MAX], body, provenance, json.dumps(metadata), now),
            )
        except sqlite3.IntegrityError:
            self.db.execute(
                "INSERT INTO conflicts(address, summary, body, author, created_at) VALUES (?, ?, ?, ?, ?)",
                (address, summary[:SUMMARY_MAX], body, author, now),
            )
            self.db.commit()
            self.log("conflict", path=address, author=author)
            return "conflict"
        self.db.commit()
        self.log("write", path=address, author=author, chars=len(body), provenance=provenance)
        return "written"

    def record_failure(self, address: str, reason: str, author: str) -> None:
        """A2: a failed pin's reason is retained for reflection — but in
        the failures table, NOT as the entry. The address stays free for
        a conforming (e.g. doctor-repair) write; write-once is absolute."""
        self.db.execute("INSERT INTO failures VALUES (?, ?, ?, ?)",
                        (address, reason, author, time.time()))
        self.db.commit()
        self.log("pin_failure", path=address, author=author, reason=reason[:300])

    def failures(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT address, reason, author FROM failures ORDER BY created_at"
        ).fetchall()
        return [{"address": r[0], "reason": r[1], "author": r[2]} for r in rows]

    def entry(self, address: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT address, summary, body, provenance, metadata FROM entries WHERE address=?",
            (address,),
        ).fetchone()
        if row is None:
            return None
        return {"address": row[0], "summary": row[1], "body": row[2],
                "provenance": row[3], "metadata": json.loads(row[4])}

    def exists(self, address: str) -> bool:
        return self.db.execute("SELECT 1 FROM entries WHERE address=?", (address,)).fetchone() is not None

    # ---- reads (A4/A5): open-read, budget-bounded, always logged ------

    def fetch(self, address: str, agent: str, budget: int) -> tuple[str, int]:
        """Returns (delivered text, chars consumed). Over-budget bodies
        deliver head + tail with an explicit marker — truncation is
        always visible to the reader (A5)."""
        row = self.entry(address)
        if row is None:
            text = f"[no entry at {address}]"
            self.log("fetch", agent=agent, path=address, chars=0, found=False)
            return text, 0
        body = row["body"]
        if len(body) <= budget:
            self.db.execute("INSERT INTO fetch_log VALUES (?, ?, ?, 0, ?)",
                            (agent, address, len(body), time.time()))
            self.db.commit()
            self.log("fetch", agent=agent, path=address, chars=len(body), truncated=False)
            return body, len(body)
        marker = f"\n[truncated: full length {len(body)}]\n"
        if budget <= len(marker) + 40:
            text = f"[truncated: full length {len(body)}; fetch budget exhausted]"
            self.db.execute("INSERT INTO fetch_log VALUES (?, ?, 0, 1, ?)",
                            (agent, address, time.time()))
            self.db.commit()
            self.log("fetch", agent=agent, path=address, chars=0, truncated=True)
            return text, 0
        head = (budget - len(marker)) * 2 // 3
        tail = budget - len(marker) - head
        text = body[:head] + marker + body[-tail:]
        self.db.execute("INSERT INTO fetch_log VALUES (?, ?, ?, 1, ?)",
                        (agent, address, budget, time.time()))
        self.db.commit()
        self.log("fetch", agent=agent, path=address, chars=budget, truncated=True)
        return text, budget

    # ---- catalog (A6): the circuit's shadow ---------------------------

    def catalog_lines(self, circuit: Circuit, prefix: str | None = None,
                      k: int = DEFAULT_LIST_K) -> list[str]:
        """One line per pin: `address · status · summary`. Status comes
        from the circuit, summaries from entries; a promised pin shows
        its declared note and owner — the in-flight reservation signal
        (A2: pins double as reservations)."""
        k = max(1, min(int(k), MAX_LIST_K))
        if prefix:
            rows = self.db.execute(
                "SELECT p.address, p.status, p.owner, p.note, e.summary FROM pins p"
                " LEFT JOIN entries e ON e.address = p.address"
                " WHERE p.address LIKE ? ORDER BY p.address LIMIT ?",
                (f"{prefix.rstrip('/')}/%", k),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT p.address, p.status, p.owner, p.note, e.summary FROM pins p"
                " LEFT JOIN entries e ON e.address = p.address ORDER BY p.address LIMIT ?",
                (k,),
            ).fetchall()
        lines = []
        for address, status, owner, note, summary in rows:
            if summary:
                lines.append(f"{address} · {status} · {summary}")
            else:
                described = f" — {note}" if note else ""
                lines.append(f"{address} · {status} · ({status} by {owner}{described})")
        return lines

    # ---- failure-predicate input (B5) ---------------------------------

    def fallback_writes(self) -> list[dict[str, Any]]:
        marks = ",".join("?" for _ in FALLBACK_PROVENANCES)
        rows = self.db.execute(
            f"SELECT address, provenance FROM entries WHERE provenance IN ({marks}) ORDER BY address",
            FALLBACK_PROVENANCES,
        ).fetchall()
        return [{"address": r[0], "provenance": r[1]} for r in rows]

    def counts(self) -> dict[str, int]:
        return {
            "entries": self.db.execute("SELECT COUNT(*) FROM entries").fetchone()[0],
            "conflicts": self.db.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0],
            "fetches": self.db.execute("SELECT COUNT(*) FROM fetch_log").fetchone()[0],
        }
