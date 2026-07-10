"""Dead-simple run visualizer: one HTML file per run directory.

    python3 -m src.visualize results/e1/ratd/L4_r3 [out.html]

Renders, from the run's own stored data (no interpretation added):
- the agent graph (spawn tree + dependency edges from every condition),
  embedding the existing graph.png if present;
- the CIRCUIT: the run's trigger table verbatim (id, condition phi,
  agent sigma, fired) - this is C as the runtime executed it;
- the roster: every agent's goal, capsule, assigned outputs, condition,
  self_role;
- the trajectory: every trace event in order;
- global memory: every entry (D) with author and full content.

Works on RATD runs (state.sqlite + trace.jsonl) and tree/planner
baseline runs (entries.json + trace.jsonl). Plain HTML, no CSS.
"""
from __future__ import annotations

import base64
import html
import json
import sqlite3
import sys
from pathlib import Path

from .phase1 import condition_refs


def esc(x) -> str:
    return html.escape(str(x))


def load(run_dir: Path):
    events = []
    trace = run_dir / "trace.jsonl"
    if trace.exists():
        events = [json.loads(l) for l in trace.read_text(encoding="utf-8").splitlines()]
    entries, triggers = [], []
    if (run_dir / "state.sqlite").exists():
        db = sqlite3.connect(run_dir / "state.sqlite")
        entries = db.execute("SELECT namespace_key, value, author, created_at FROM entries ORDER BY created_at").fetchall()
        triggers = db.execute("SELECT id, condition, agent_spec, fired FROM triggers").fetchall()
    elif (run_dir / "entries.json").exists():
        entries = [(k, v, "", 0) for k, v in json.loads((run_dir / "entries.json").read_text(encoding="utf-8")).items()]
    metrics = {}
    if (run_dir / "metrics.json").exists():
        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    return events, entries, triggers, metrics


def summarize_event(e: dict) -> str:
    t = e.get("event")
    if t == "spawn":
        c = e["child"]
        return f"{e['parent']} spawned {c['task_id']} (condition: {c.get('condition') or 'none - starts now'}) outputs: {[o.get('path') for o in c.get('expected_outputs', [])]}"
    if t == "route":
        return f"{e.get('agent')} decided: {e.get('action', {}).get('action')}"
    if t == "route_context":
        return f"{e.get('agent')} routing context built ({e.get('chars')} chars)"
    if t == "self_role":
        return f"{e.get('agent')} takes self_role ({e.get('kind')}) outputs {e.get('outputs')} condition: {e.get('condition') or 'none'}"
    if t == "self_role_start":
        return f"{e.get('agent')} self_role work begins"
    if t == "defer":
        return f"{e.get('agent')} DEFERS until {e.get('wake_condition')}"
    if t == "trigger_add":
        return f"circuit += rule [{e.get('id')}]: when {e.get('condition')} wake {e.get('agent')}"
    if t == "trigger_fire":
        return f"rule [{e.get('id')}] FIRED -> {e.get('agent')} enqueued"
    if t == "write":
        return f"{e.get('author')} wrote {e.get('path')} ({e.get('chars')} chars)"
    if t == "cross_branch_read":
        return f"{e.get('agent')} read {e.get('path')} (cross-branch)"
    if t == "conflict":
        return f"CONFLICT: {e.get('author')} attempted {e.get('path')}"
    if t == "planner_call":
        return f"planner call #{e.get('n')} context {e.get('context_chars')} chars, churn {e.get('churn')}, {e.get('remaining')} tasks remain"
    if t in ("agent_start", "enqueue"):
        a = e.get("agent")
        return f"{t}: {a['task_id'] if isinstance(a, dict) else a}"
    return json.dumps({k: v for k, v in e.items() if k != "ts"}, ensure_ascii=False)[:300]


def main() -> int:
    run_dir = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else run_dir / "view.html"
    events, entries, triggers, metrics = load(run_dir)
    t0 = events[0]["ts"] if events else 0

    agents: dict[str, dict] = {}
    edges: list[tuple[str, str, str]] = []
    for e in events:
        if e.get("event") == "spawn":
            c = e["child"]
            agents[c["task_id"]] = c
            edges.append((e["parent"], c["task_id"], "spawn"))
            for ref in condition_refs(c.get("condition") or ""):
                edges.append((ref, c["task_id"], "waits-on"))
        elif e.get("event") == "self_role":
            for ref in condition_refs(e.get("condition") or ""):
                edges.append((ref, f"{e['agent']} (self_role)", "waits-on"))
        elif e.get("event") == "trigger_add" and ":defer" in str(e.get("id", "")):
            for ref in condition_refs(e.get("condition") or ""):
                edges.append((ref, f"{e['agent']} (defer-wake)", "waits-on"))

    h = [f"<title>{esc(run_dir.name)}</title>", f"<h1>Run: {esc(run_dir.name)}</h1>"]

    h.append("<h2>Metrics</h2><table border=1>")
    for k, v in metrics.items():
        h.append(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>")
    h.append("</table>")

    h.append("<h2>Agent graph</h2>")
    png = run_dir / "graph.png"
    if png.exists():
        b64 = base64.b64encode(png.read_bytes()).decode()
        h.append(f'<img src="data:image/png;base64,{b64}">')
    h.append("<p>Edges (spawn = parent created child; waits-on = trigger dependency, producer path &rarr; consumer):</p><table border=1><tr><th>from</th><th>to</th><th>kind</th></tr>")
    for a, b, kind in edges:
        h.append(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(kind)}</td></tr>")
    h.append("</table>")

    if agents:
        h.append("<h2>Agent roster</h2>")
        for tid in sorted(agents):
            a = agents[tid]
            h.append(f"<details><summary><b>{esc(tid)}</b>: {esc(a.get('task', ''))[:120]}</summary><table border=1>")
            for k in ("task", "capsule", "condition", "expected_outputs"):
                h.append(f"<tr><td>{esc(k)}</td><td>{esc(a.get(k))}</td></tr>")
            h.append("</table></details>")

    if triggers:
        h.append("<h2>Circuit (trigger table C, verbatim from state.sqlite)</h2><table border=1><tr><th>rule id</th><th>condition &phi;</th><th>wakes agent &sigma;</th><th>fired</th></tr>")
        for tid, cond, spec, fired in triggers:
            agent = json.loads(spec).get("task_id", "?")
            h.append(f"<tr><td>{esc(tid)}</td><td>{esc(cond)}</td><td>{esc(agent)}</td><td>{'YES' if fired else 'no (never became true)'}</td></tr>")
        h.append("</table>")

    h.append(f"<h2>Trajectory ({len(events)} events)</h2><table border=1><tr><th>t+s</th><th>event</th><th>what happened</th></tr>")
    for e in events:
        h.append(f"<tr><td>{e.get('ts', 0) - t0:8.1f}</td><td>{esc(e.get('event'))}</td><td>{esc(summarize_event(e))}</td></tr>")
    h.append("</table>")

    h.append(f"<h2>Global memory D ({len(entries)} entries, accumulation order)</h2>")
    for path, value, author, _ in entries:
        h.append(f"<details><summary><b>{esc(path)}</b> &mdash; {len(str(value))} chars{' by ' + esc(author) if author else ''}</summary><pre>{esc(value)}</pre></details>")

    out.write_text("\n".join(h), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
