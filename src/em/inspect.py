"""Circuit inspector — render a run's control + data plane as a raw file.

For any RATD run dir (state.sqlite + trace.jsonl) emits, alongside the run:
  circuit.dot  — Graphviz digraph: agent nodes (colored by B7 state), pin
                 nodes (colored by A2 status), ownership edges, gate wiring
                 (done()/completed() refs -> the agent the gate enqueues;
                 dead gates red-dashed, fired gates green), and the failure
                 summary as the graph caption.
  circuit.png  — rendered if Graphviz `dot` is on PATH.
  circuit.txt  — plain-text dump (pins / gates / agents / failures / events)
                 for raw grep-able inspection with no renderer at all.

Single run:  python3 -m src.em.inspect results/em0/G2/d03_r1
Whole tree:  python3 -m src.em.inspect results/em0 --all
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from ..ratd.circuit import gate_refs
from . import schema

PIN_COLOR = {"done": "#bfe3c6", "promised": "#e6e6e6", "failed": "#f2b8b8",
             "abandoned": "#f4d2a8"}
AGENT_COLOR = {"done": "#bfe3c6", "failed": "#f2b8b8", "dropped": "#f2b8b8",
               "starved": "#e2b6e8", "sleeping": "#cfe0f5", "queued": "#eeeeee",
               "routing": "#fff2c4", "executing": "#ffe0b0", "promised": "#e6e6e6"}


def agent_rows(run_dir: Path) -> list[dict[str, Any]]:
    db = sqlite3.connect(run_dir / "state.sqlite")
    rows = db.execute("SELECT agent_id, state, depth, parent FROM agents").fetchall()
    return [{"agent_id": r[0], "state": r[1], "depth": r[2], "parent": r[3]} for r in rows]


def failure_rows(run_dir: Path) -> list[dict[str, Any]]:
    db = sqlite3.connect(run_dir / "state.sqlite")
    rows = db.execute("SELECT address, reason, author FROM failures").fetchall()
    return [{"address": r[0], "reason": r[1], "author": r[2]} for r in rows]


def _load_metrics(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _nid(prefix: str, name: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in name)
    return f"{prefix}_{safe}"


def _esc(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def build_dot(run_dir: Path) -> str:
    pins = schema.pin_rows(run_dir)
    gates = schema.gate_rows(run_dir)
    agents = agent_rows(run_dir)
    failures = failure_rows(run_dir)
    metrics = _load_metrics(run_dir)
    agent_ids = {a["agent_id"] for a in agents}

    L = ['digraph circuit {', '  rankdir=LR;', '  compound=true;',
         '  node [fontname="Helvetica", fontsize=10, style="filled,rounded"];',
         '  edge [fontname="Helvetica", fontsize=8, color="#888888"];']

    # agent nodes (box) + spawn hierarchy
    L.append('  subgraph cluster_agents { label="agents (control plane)"; color="#cccccc";')
    for a in agents:
        color = AGENT_COLOR.get(a["state"], "#eeeeee")
        L.append(f'    {_nid("a", a["agent_id"])} [shape=box, fillcolor="{color}", '
                 f'label="{_esc(a["agent_id"])}\\n[{a["state"]}]"];')
    L.append('  }')
    for a in agents:
        if a["parent"] and a["parent"] in agent_ids:
            L.append(f'  {_nid("a", a["parent"])} -> {_nid("a", a["agent_id"])} '
                     f'[style=dotted, color="#bbbbbb", arrowhead=empty];')

    # pin nodes (ellipse) + ownership edges (agent -> pin)
    for p in pins:
        color = PIN_COLOR.get(p["status"], "#eeeeee")
        L.append(f'  {_nid("p", p["address"])} [shape=ellipse, fillcolor="{color}", '
                 f'label="{_esc(p["address"])}\\n({p["status"]})"];')
        if p["owner"] in agent_ids:
            L.append(f'  {_nid("a", p["owner"])} -> {_nid("p", p["address"])} '
                     f'[style=solid, color="#7aa7d0", arrowhead=none];')

    # gate wiring: referenced pin/agent -> the agent the gate enqueues
    pin_ids = {p["address"] for p in pins}
    for g in gates:
        done_refs, completed_refs = gate_refs(g["condition"])
        try:
            cons = json.loads(_gate_consequence(run_dir, g["id"]))
            target = cons.get("agent", {}).get("task_id")
        except Exception:
            target = None
        if g["dead"]:
            estyle, ecolor = "dashed", "#d1454a"
        elif g["fired"]:
            estyle, ecolor = "solid", "#3a9a52"
        else:
            estyle, ecolor = "solid", "#c9a020"
        tgt_node = _nid("a", target) if target in agent_ids else None
        for ref in done_refs:
            src = _nid("p", ref) if ref in pin_ids else None
            if src and tgt_node:
                L.append(f'  {src} -> {tgt_node} [style={estyle}, color="{ecolor}", '
                         f'label="{_esc(g["mechanism"])}"];')
        for ref in completed_refs:
            src = _nid("a", ref) if ref in agent_ids else None
            if src and tgt_node:
                L.append(f'  {src} -> {tgt_node} [style={estyle}, color="{ecolor}", '
                         f'label="completed"];')

    # caption: outcome + failure summary
    cap = [f'run {run_dir.name}',
           f'outcome: {metrics.get("outcome", "?")}',
           f'pins {metrics.get("pins_done", "?")}/{metrics.get("pins_total", "?")} done, '
           f'gates {metrics.get("gates_fired", "?")} fired/{metrics.get("gates_dead", "?")} dead, '
           f'doctor {metrics.get("doctor_cycles", "?")}']
    if failures:
        cap.append("failed pins: " + ", ".join(f["address"] for f in failures))
    L.append(f'  label="{_esc(chr(10).join(cap))}"; labelloc="b"; fontsize=11;')
    L.append('}')
    return "\n".join(L)


def _gate_consequence(run_dir: Path, gate_id: str) -> str:
    db = sqlite3.connect(run_dir / "state.sqlite")
    row = db.execute("SELECT consequence FROM gates WHERE id=?", (gate_id,)).fetchone()
    return row[0] if row else "{}"


def build_txt(run_dir: Path) -> str:
    pins = schema.pin_rows(run_dir)
    gates = schema.gate_rows(run_dir)
    agents = agent_rows(run_dir)
    failures = failure_rows(run_dir)
    cat = schema.catalog_audit(run_dir)
    metrics = _load_metrics(run_dir)
    out = [f"# {run_dir.name}", f"outcome: {metrics.get('outcome')}  qualitative: {metrics.get('qualitative')}", ""]
    out.append("## agents (state)")
    for a in sorted(agents, key=lambda x: x["agent_id"]):
        out.append(f"  {a['agent_id']:16} {a['state']:10} depth={a['depth']} parent={a['parent']}")
    out.append("\n## pins (status · owner · note)")
    for p in sorted(pins, key=lambda x: x["address"]):
        out.append(f"  {p['address']:34} {p['status']:10} {p['owner']:14} {p['note'][:60]}")
    out.append("\n## gates (fired/dead · mechanism · condition)")
    for g in gates:
        flag = "DEAD" if g["dead"] else ("fired" if g["fired"] else "open")
        out.append(f"  [{flag:5}] {g['mechanism']:14} {g['condition']}")
    if failures:
        out.append("\n## failed pins (reason)")
        for f in failures:
            out.append(f"  {f['address']:34} by {f['author']}: {f['reason'][:100]}")
    out.append(f"\n## catalog audit: {'CLEAN' if cat['clean'] else 'DIRTY ' + str(cat)}")
    return "\n".join(out) + "\n"


def inspect_run(run_dir: Path, render: bool = True) -> None:
    if not (run_dir / "state.sqlite").exists():
        return
    (run_dir / "circuit.dot").write_text(build_dot(run_dir), encoding="utf-8")
    (run_dir / "circuit.txt").write_text(build_txt(run_dir), encoding="utf-8")
    if render and shutil.which("dot"):
        try:
            subprocess.run(["dot", "-Tpng", str(run_dir / "circuit.dot"),
                            "-o", str(run_dir / "circuit.png")], check=True,
                           capture_output=True, timeout=60)
        except (subprocess.SubprocessError, OSError) as exc:
            print(f"  {run_dir.name}: dot render failed ({exc})", flush=True)
    print(f"  wrote {run_dir.name}/circuit.{{dot,txt,png}}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render RATD run circuits (dot/png/txt)")
    parser.add_argument("run", help="a run dir, or a tree of runs with --all")
    parser.add_argument("--all", action="store_true", help="recurse: inspect every run under the path")
    parser.add_argument("--no-render", action="store_true", help="skip png (dot + txt only)")
    args = parser.parse_args(argv)
    base = Path(args.run)
    targets = (sorted(p.parent for p in base.rglob("state.sqlite")) if args.all
               else [base])
    for run_dir in targets:
        inspect_run(run_dir, render=not args.no_render)
    print(f"inspected {len(targets)} run(s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
