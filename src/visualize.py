"""Interactive run-replay visualizer (v3).

    python3 -m src.visualize <run_dir> [out.html]

One self-contained dark HTML page per run (inline CSS/JS, no network):

- a TIME SCRUBBER with play/step/keyboard that replays the whole run
  event by event; every panel below reflects the state at the cursor;
- the agent circuit graph, live: nodes appear when spawned and are
  colored by lifecycle state (waiting / active / sleeping / done /
  starved / dropped); edges appear as the rules that create them are
  authored; click a node for its full contract and writes;
- per-agent SWIMLANES over the event axis - who was doing what, when,
  in parallel with whom - with write ticks and a synced cursor, plus a
  cumulative memory-growth sparkline on the same axis;
- the circuit rule table with armed/fired/dead fate and jump-to-event;
- a filterable, seekable trajectory (click a row to jump the replay);
- global memory as of the cursor, searchable.

State colors are status roles (validated palette); edge kinds are
categorical slots with dash patterns as secondary encoding. Works on
RATD runs (state.sqlite + trace.jsonl) and tree/planner baseline runs.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from .phase1 import condition_refs


def ns_owner(path: str) -> str:
    return path.split("/")[0]


def summarize_event(e: dict) -> str:
    t = e.get("event")
    if t == "spawn":
        c = e["child"]
        return f"{e['parent']} spawned {c['task_id']} — condition: {c.get('condition') or 'none (starts now)'} — outputs {[o.get('path') for o in c.get('expected_outputs', [])]}"
    if t == "route":
        return f"{e.get('agent')} decided: {e.get('action', {}).get('action')}"
    if t == "route_context":
        return f"{e.get('agent')} routing context built ({e.get('chars'):,} chars)"
    if t == "route_repair":
        return f"{e.get('agent')} document rejected (attempt {e.get('attempt')}): {'; '.join(str(n)[:80] for n in e.get('notes', [])[:2])}"
    if t == "route_invalid":
        return f"{e.get('agent')} DROPPED: document invalid after retries"
    if t == "self_role":
        return f"{e.get('agent')} takes self_role ({e.get('kind')}) — outputs {e.get('outputs')} — condition: {e.get('condition') or 'none'}"
    if t == "self_role_start":
        return f"{e.get('agent')} self_role work begins"
    if t == "defer":
        return f"{e.get('agent')} DEFERS until {e.get('wake_condition')}"
    if t == "trigger_add":
        return f"circuit += rule [{e.get('id')}] : when {e.get('condition')} wake {e.get('agent')}"
    if t == "trigger_fire":
        return f"rule [{e.get('id')}] FIRED → {e.get('agent')} enqueued"
    if t == "write":
        return f"{e.get('author')} wrote {e.get('path')} ({e.get('chars'):,} chars)"
    if t == "cross_branch_read":
        return f"{e.get('agent')} read {e.get('path')} (cross-branch)"
    if t == "conflict":
        return f"CONFLICT: {e.get('author')} attempted {e.get('path')}"
    if t == "schema_mismatch":
        return f"{e.get('agent')} worker did not return declared path {e.get('declared')} (fallback written)"
    if t == "worker_invalid":
        return "worker output unparseable after retries (empty outputs used)"
    if t == "planner_call":
        return f"planner call #{e.get('n')} — context {e.get('context_chars'):,} chars — churn {e.get('churn')} — {e.get('remaining')} tasks remain"
    if t == "state_truncation":
        return f"planner state TRUNCATED: {e.get('dropped_entries')} oldest entries dropped"
    if t == "stall":
        return f"STALL: no runnable task among {e.get('remaining')}"
    if t == "rail_hit":
        return f"RAIL HIT: {e.get('rail')}"
    if t in ("agent_start", "enqueue"):
        a = e.get("agent")
        return f"{t}: {a['task_id'] if isinstance(a, dict) else a}"
    return json.dumps({k: v for k, v in e.items() if k != "ts"}, ensure_ascii=False)[:300]


def build_data(run_dir: Path) -> dict:
    raw_events = []
    trace = run_dir / "trace.jsonl"
    if trace.exists():
        raw_events = [json.loads(l) for l in trace.read_text(encoding="utf-8").splitlines()]
    t0 = raw_events[0]["ts"] if raw_events else 0

    entries, triggers = [], []
    if (run_dir / "state.sqlite").exists():
        db = sqlite3.connect(run_dir / "state.sqlite")
        entries = [
            {"path": k, "value": v, "author": a, "chars": len(str(v))}
            for k, v, a in db.execute("SELECT namespace_key, value, author FROM entries ORDER BY created_at")
        ]
        triggers = [
            {"id": i, "condition": c, "agent": json.loads(s).get("task_id", "?"), "fired": bool(f), "added_at": None, "fired_at": None}
            for i, c, s, f in db.execute("SELECT id, condition, agent_spec, fired FROM triggers")
        ]
    elif (run_dir / "entries.json").exists():
        raw = json.loads((run_dir / "entries.json").read_text(encoding="utf-8"))
        entries = [{"path": k, "value": v, "author": "", "chars": len(str(v))} for k, v in raw.items()]

    metrics = {}
    if (run_dir / "metrics.json").exists():
        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))

    trig_by_id = {t["id"]: t for t in triggers}
    nodes: dict[str, dict] = {}

    def node(tid: str, at: int) -> dict:
        return nodes.setdefault(tid, {"id": tid, "task": "", "capsule": "", "condition": None,
                                      "outputs": [], "self_role": None, "born": at})

    edges: list[dict] = []
    events: list[dict] = []
    for i, e in enumerate(raw_events):
        t = e.get("event")
        ev = {"i": i, "t": round(e.get("ts", 0) - t0, 1), "y": t, "x": summarize_event(e)}
        if t in ("enqueue", "agent_start"):
            a = e.get("agent")
            tid = a["task_id"] if isinstance(a, dict) else str(a)
            ev["a"] = tid
            if t == "agent_start" and isinstance(a, dict):
                ev["doc"] = {"task": a.get("task"), "capsule": a.get("capsule"), "condition": a.get("condition"),
                             "expected_outputs": a.get("expected_outputs"), "worker_only": a.get("worker_only", False)}
            if isinstance(a, dict) and tid == "root":
                node("root", i)["task"] = a.get("task", "")
        elif t == "spawn":
            c = e["child"]
            n = node(c["task_id"], i)
            n.update(task=c.get("task", ""), capsule=c.get("capsule", ""), condition=c.get("condition"),
                     outputs=[o.get("path") for o in c.get("expected_outputs", [])])
            node(e["parent"], i)
            ev.update(a=c["task_id"], parent=e["parent"], g=bool(c.get("condition")))
            edges.append({"from": e["parent"], "to": c["task_id"], "kind": "spawn", "label": "", "at": i})
            for ref in condition_refs(c.get("condition") or ""):
                edges.append({"from": ns_owner(ref), "to": c["task_id"], "kind": "waits", "label": ref, "at": i})
        elif t == "self_role":
            n = node(e["agent"], i)
            n["self_role"] = {"kind": e.get("kind"), "outputs": e.get("outputs"), "condition": e.get("condition")}
            ev.update(a=e["agent"], g=bool(e.get("condition")))
            for ref in condition_refs(e.get("condition") or ""):
                edges.append({"from": ns_owner(ref), "to": e["agent"], "kind": "waits", "label": ref, "at": i})
        elif t == "self_role_start":
            ev["a"] = e.get("agent")
        elif t == "defer":
            ev["a"] = e.get("agent")
            for ref in condition_refs(e.get("wake_condition") or ""):
                edges.append({"from": ns_owner(ref), "to": e["agent"], "kind": "wake", "label": ref, "at": i})
        elif t == "trigger_add":
            ev.update(a=e.get("agent"), r=e.get("id"))
            if e.get("id") in trig_by_id and trig_by_id[e["id"]]["added_at"] is None:
                trig_by_id[e["id"]]["added_at"] = i
        elif t == "trigger_fire":
            ev.update(a=e.get("agent"), r=e.get("id"))
            if e.get("id") in trig_by_id:
                trig_by_id[e["id"]]["fired_at"] = i
        elif t == "write":
            ev.update(a=e.get("author"), p=e.get("path"))
        elif t in ("route", "route_repair", "route_invalid", "cross_branch_read", "schema_mismatch", "route_context"):
            ev["a"] = e.get("agent")
            if t == "route":
                ev["act"] = e.get("action", {}).get("action")
                ev["doc"] = e.get("action")
            elif t == "route_repair":
                ev["doc"] = {"notes": e.get("notes")}
        events.append(ev)

    planner_calls = [
        {"n": e.get("n"), "chars": e.get("context_chars"), "churn": e.get("churn"), "remaining": e.get("remaining")}
        for e in raw_events if e.get("event") == "planner_call"
    ]
    return {
        "run": run_dir.name, "metrics": metrics, "nodes": list(nodes.values()), "edges": edges,
        "triggers": triggers, "events": events, "entries": entries, "planner_calls": planner_calls,
        "dead_rules": sum(1 for t in triggers if not t["fired"]),
    }


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title><style>
:root{--page:#0d0d0d;--card:#1a1a19;--card2:#232322;--ink:#fff;--ink2:#c3c2b7;--mut:#898781;--grid:#2c2c2a;--base:#383835;--ring:rgba(255,255,255,.1);
--e-spawn:#3987e5;--e-waits:#199e70;--e-wake:#9085e9;--s-active:#3987e5;--s-done:#0ca30c;--s-sleep:#fab219;--s-dead:#d03b3b}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--page);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:14px 22px 6px;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}header h1{font-size:17px;margin:0}
.chip{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;border:1px solid var(--ring);color:var(--ink2)}
.chip.ok{color:var(--s-done);border-color:var(--s-done)}.chip.bad{color:var(--s-dead);border-color:var(--s-dead)}
#controls{position:sticky;top:0;z-index:20;background:var(--page);border-bottom:1px solid var(--grid);padding:10px 22px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
#controls button,#controls select{background:var(--card2);color:var(--ink);border:1px solid var(--ring);border-radius:7px;padding:5px 12px;font-size:13px;cursor:pointer}
#controls button:hover{border-color:var(--e-spawn)}#scrub{flex:1;min-width:220px;accent-color:var(--e-spawn)}
#eclock{font-variant-numeric:tabular-nums;color:var(--mut);font-size:12px;min-width:130px}
#evcard{width:100%;background:var(--card);border:1px solid var(--grid);border-left:4px solid var(--e-spawn);border-radius:8px;padding:7px 12px;font-size:13px;color:var(--ink2)}
#evcard b{color:var(--ink)}
section{margin:16px 22px;background:var(--card);border:1px solid var(--grid);border-radius:10px;padding:16px}
h2{font-size:13px;margin:0 0 12px;color:var(--ink2);text-transform:uppercase;letter-spacing:.07em}h2 small{color:var(--mut);text-transform:none;letter-spacing:0;font-weight:400}
table{border-collapse:collapse;width:100%;font-size:13px}th{text-align:left;color:var(--mut);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--base)}
td{padding:5px 10px;border-bottom:1px solid var(--grid);vertical-align:top}tbody tr:hover td{background:var(--card2)}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:12px}
#graphwrap{display:flex;gap:16px}#gsvg{overflow:auto;flex:1;border:1px solid var(--grid);border-radius:8px;background:var(--page)}
#detail{width:340px;flex-shrink:0;font-size:13px;color:var(--ink2)}#detail b{color:var(--ink)}#detail .empty{color:var(--mut)}
.node rect{fill:var(--card2);stroke:var(--base);stroke-width:1.3;cursor:pointer}
.node.ghost{opacity:.13}.node.sel rect{stroke:#fff;stroke-width:2.6}
.node.st-active rect{stroke:var(--s-active);stroke-width:2.4}.node.st-done rect{stroke:var(--s-done);stroke-width:2}
.node.st-sleeping rect{stroke:var(--s-sleep);stroke-width:2.2;stroke-dasharray:6 3}.node.st-waiting rect{stroke:var(--mut);stroke-dasharray:4 4}
.node.st-starved rect,.node.st-dropped rect{stroke:var(--s-dead);stroke-width:2.4}
.node text{fill:var(--ink);font-size:12px;pointer-events:none}.node text.sub{fill:var(--mut);font-size:10px}
.edge{fill:none;stroke-width:2;opacity:.8}.edge.spawn{stroke:var(--e-spawn)}.edge.waits{stroke:var(--e-waits);stroke-dasharray:6 4}
.edge.wake{stroke:var(--e-wake);stroke-dasharray:2 4}.edge.hl{opacity:1;stroke-width:3.4}.edge.fade{opacity:.1}.edge.ghost{display:none}
.legend{font-size:12px;color:var(--mut);margin-top:10px;display:flex;flex-wrap:wrap;gap:16px}
.sw{display:inline-block;width:22px;height:0;border-top:3px solid;vertical-align:middle;margin-right:5px}
.dot{display:inline-block;width:10px;height:10px;border-radius:3px;vertical-align:middle;margin-right:5px}
#lanes{overflow-x:auto;border:1px solid var(--grid);border-radius:8px;background:var(--page)}
.lanelabel{cursor:pointer}.lanelabel:hover{fill:var(--ink)}
#ttip{position:fixed;display:none;background:var(--card2);border:1px solid var(--ring);border-radius:7px;padding:6px 10px;font-size:12px;color:var(--ink2);pointer-events:none;z-index:50;max-width:380px}
#ttip b{color:var(--ink)}
tr.cur td{background:#22303e!important;border-left:3px solid var(--e-spawn)}tr.future{opacity:.35}
tr.r-armed td:last-child{color:var(--s-sleep)}tr.r-fired td:last-child{color:var(--s-done)}tr.r-dead td:last-child{color:var(--s-dead);font-weight:700}tr.r-pending{opacity:.35}
input[type=search]{background:var(--page);border:1px solid var(--base);color:var(--ink);border-radius:7px;padding:6px 10px;width:260px;margin-bottom:10px}
.filters{margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px}
.filters label{border:1px solid var(--base);border-radius:12px;padding:2px 10px;font-size:12px;color:var(--mut);cursor:pointer;user-select:none}
.filters label.on{color:var(--ink);border-color:var(--e-spawn);background:#1c2a3a}
details{border:1px solid var(--grid);border-radius:8px;margin:6px 0;padding:6px 12px}summary{cursor:pointer}
details.new{border-color:var(--s-done)}details pre{white-space:pre-wrap;color:var(--ink2);font-size:12px;max-height:420px;overflow:auto}
#evdetail{font-size:13px;color:var(--ink2)}#evdetail h4{margin:2px 0 8px;color:var(--ink);font-size:13px}
#evdetail pre{white-space:pre-wrap;background:var(--page);border:1px solid var(--grid);border-radius:8px;padding:10px;max-height:360px;overflow:auto;font-size:12px}
#evdetail .k{color:var(--mut)}#evdetail table td:first-child{color:var(--mut);width:150px}
.reason{border-left:3px solid var(--e-spawn);background:var(--page);padding:7px 12px;border-radius:6px;margin:8px 0;color:var(--ink)}
.bar{fill:var(--e-spawn)}.bar:hover{fill:var(--s-sleep)}.axis{fill:var(--mut);font-size:11px}
td .tdot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;vertical-align:baseline}
</style></head><body>
<header><h1 id="ttl"></h1><span id="chips"></span></header>
<div id="controls">
 <button id="play">&#9654; play</button><button id="stepb">&#8592;</button><button id="stepf">&#8594;</button>
 <select id="speed"><option value="400">slow</option><option value="150" selected>normal</option><option value="60">fast</option></select>
 <input type="range" id="scrub" min="0" value="0"><span id="eclock"></span>
 <div id="evcard"><b>event 0</b> — drag the slider, press play, or use &larr;/&rarr; keys (space = play/pause)</div>
</div>
<section id="inspector"><h2>Event inspector <small>— the payload at the cursor: what the agent received / generated</small></h2><div id="evdetail"></div></section>
<section id="graph"><h2>Agent circuit <small>— live at cursor; click a node</small></h2>
<div id="graphwrap"><div id="gsvg"></div><div id="detail"><div class="empty">Click a node (or a swimlane label) to inspect its contract, state, and writes.</div></div></div>
<div class="legend">
<span><span class="sw" style="border-color:var(--e-spawn)"></span>spawn</span>
<span><span class="sw" style="border-color:var(--e-waits);border-top-style:dashed"></span>waits-on</span>
<span><span class="sw" style="border-color:var(--e-wake);border-top-style:dotted"></span>defer-wake</span>
<span style="border-left:1px solid var(--base);padding-left:16px"><span class="dot" style="background:var(--s-active)"></span>active</span>
<span><span class="dot" style="border:2px dashed var(--mut)"></span>waiting (gated)</span>
<span><span class="dot" style="background:var(--s-sleep)"></span>sleeping (deferred)</span>
<span><span class="dot" style="background:var(--s-done)"></span>done</span>
<span><span class="dot" style="background:var(--s-dead)"></span>starved / dropped</span></div></section>
<section id="tl"><h2>Swimlanes <small>— one lane per agent over the event axis; ticks are writes; the line is the cursor</small></h2>
<div id="lanes"></div><div id="spark"></div></section>
<section id="pchart" style="display:none"><h2>Planner context per call <small>— hover bars</small></h2><div id="pbars"></div></section>
<section id="circuit"><h2>Circuit — rule table C <small>— click a row to jump to its moment</small></h2><div id="ctable"></div></section>
<section id="traj"><h2>Trajectory <small>— click a row to seek the replay</small></h2>
<input type="search" id="tsearch" placeholder="search events…"><div class="filters" id="tfilters"></div><div id="ttable" style="max-height:480px;overflow:auto"></div></section>
<section id="mem"><h2>Global memory D <small id="memcount"></small></h2><input type="search" id="msearch" placeholder="filter paths…"><div id="mlist"></div></section>
<div id="ttip"></div>
<script>const DATA = __DATA__;
const $=q=>document.querySelector(q), esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const EV=DATA.events, N=Math.max(EV.length,1), LAST=N-1;
document.title=DATA.run; $("#ttl").textContent="Run: "+DATA.run;
const m=DATA.metrics||{}, chips=[];
if("converged" in m) chips.push(`<span class="chip ${m.converged?"ok":"bad"}">${m.converged?"converged":"NOT converged"}</span>`);
for(const k of ["llm_calls","max_depth","agent_count","defer_count","planner_calls","termination"]) if(m[k]!==undefined) chips.push(`<span class="chip">${k}: ${esc(m[k])}</span>`);
if(DATA.dead_rules) chips.push(`<span class="chip bad">dead rules: ${DATA.dead_rules}</span>`);
$("#chips").innerHTML=chips.join(" ");
// ---------- replay engine ----------
const nodes=DATA.nodes, byId={}; nodes.forEach(n=>byId[n.id]=n);
function replay(upto){ // state after events[0..upto]
  const st={}, mem=[], writes={}; let actor=null;
  const S=(id,v)=>{if(byId[id])st[id]=v};
  const finishActor=()=>{if(actor&&st[actor]==="active")S(actor,"done");};
  for(let i=0;i<=upto&&i<N;i++){const e=EV[i];
    switch(e.y){
      case "spawn": S(e.a, e.g?"waiting":"queued"); break;
      case "enqueue": if(e.a==="root"&&st.root===undefined)S("root","queued"); break;
      case "agent_start": finishActor(); actor=e.a; S(e.a,"active"); break;
      case "self_role_start": finishActor(); actor=e.a; S(e.a,"active"); break;
      case "self_role": S(e.a, e.g?"waiting":"queued"); break;
      case "defer": S(e.a,"sleeping"); actor=null; break;
      case "trigger_fire": if(st[e.a]==="sleeping"||st[e.a]==="waiting")S(e.a,"queued"); break;
      case "route_invalid": S(e.a,"dropped"); actor=null; break;
      case "write": mem.push(e.p); (writes[e.a]??=[]).push(e.p); if(e.a&&st[e.a]!=="active")S(e.a,"active"); break;
    }}
  if(upto>=LAST){finishActor(); for(const id in st) if(st[id]==="sleeping"||st[id]==="waiting"||st[id]==="queued") st[id]="starved";}
  return {st,mem,writes};
}
const FINAL=replay(LAST);
// swimlane segments: replay once recording transitions
const segs={}, laneOrder=[];
{const st={}; let actor=null; const open={}; // id -> {state, from}
 const trans=(id,v,i)=>{if(!byId[id])return; if(!(id in st)){laneOrder.push(id);} if(st[id]===v)return;
   if(open[id])(segs[id]??=[]).push({s:open[id].state,a:open[id].from,b:i});
   open[id]={state:v,from:i}; st[id]=v;};
 const fin=(i)=>{if(actor&&st[actor]==="active")trans(actor,"done",i);};
 EV.forEach((e,i)=>{switch(e.y){
   case "spawn": trans(e.a, e.g?"waiting":"queued", i); break;
   case "enqueue": if(e.a==="root"&&st.root===undefined)trans("root","queued",i); break;
   case "agent_start": case "self_role_start": fin(i); actor=e.a; trans(e.a,"active",i); break;
   case "self_role": trans(e.a, e.g?"waiting":"queued", i); break;
   case "defer": trans(e.a,"sleeping",i); actor=null; break;
   case "trigger_fire": if(st[e.a]==="sleeping"||st[e.a]==="waiting")trans(e.a,"queued",i); break;
   case "route_invalid": trans(e.a,"dropped",i); actor=null; break;
   case "write": if(e.a&&st[e.a]!=="active")trans(e.a,"active",i); break;}});
 fin(LAST); for(const id in open){let s=open[id].state; if(["sleeping","waiting","queued"].includes(s)&&FINAL.st[id]==="starved")s="starved";
   (segs[id]??=[]).push({s,a:open[id].from,b:LAST});}}
// ---------- graph ----------
const depth=id=>id==="root"?0:id.split(".").length-1;
const cols={}; [...nodes].sort((a,b)=>a.id.localeCompare(b.id)).forEach(n=>{(cols[depth(n.id)]??=[]).push(n);});
const CW=215,RH=66,GW=Math.max(...Object.keys(cols).map(Number),0)*CW+240,GH=Math.max(...Object.values(cols).map(c=>c.length),1)*RH+40;
nodes.forEach(n=>{const d=depth(n.id),i=cols[d].indexOf(n); n.x=30+d*CW; n.y=24+i*RH;});
const gEdges=DATA.edges.filter(e=>byId[e.from]&&byId[e.to]);
let svg=`<svg width="${GW}" height="${GH}" xmlns="http://www.w3.org/2000/svg">`;
svg+=`<defs>${["spawn","waits","wake"].map(k=>`<marker id="m-${k}" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="${{spawn:"#3987e5",waits:"#199e70",wake:"#9085e9"}[k]}"/></marker>`).join("")}</defs>`;
gEdges.forEach((e,i)=>{const a=byId[e.from],b=byId[e.to],x1=a.x+152,y1=a.y+22,x2=b.x,y2=b.y+22,mx=(x1+x2)/2;
svg+=`<path id="e${i}" class="edge ${e.kind}" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}" marker-end="url(#m-${e.kind})"><title>${esc(e.kind)} ${esc(e.label)} (e${e.at})</title></path>`;});
nodes.forEach(n=>{svg+=`<g class="node" data-id="${esc(n.id)}" transform="translate(${n.x},${n.y})"><rect width="152" height="44" rx="7"/><text x="10" y="18">${esc(n.id)}</text><text x="10" y="34" class="sub" data-sub="${esc(n.id)}">${esc(n.task.slice(0,22))}</text></g>`;});
svg+="</svg>"; $("#gsvg").innerHTML=svg;
if(!nodes.length){$("#graph").style.display="none";$("#tl").style.display="none";}
let SEL=null;
function detail(id){const n=byId[id]; if(!n)return; SEL=id;
 const cur=replay(CUR), state=cur.st[id]??"(not yet spawned)", w=cur.writes[id]??[];
 const rel=DATA.edges.filter(e=>e.from===id||e.to===id);
 $("#detail").innerHTML=`<h3 style="margin:0 0 8px;color:var(--ink)">${esc(id)} <span class="chip">${esc(state)}</span></h3>
 <p><b>task</b> ${esc(n.task)||"—"}</p><p><b>capsule</b> ${esc(n.capsule)||"—"}</p>
 <p><b>start condition</b> <span class="mono">${esc(n.condition??"none (immediate)")}</span></p>
 <p><b>assigned outputs</b> <span class="mono">${n.outputs.map(esc).join("<br>")||"—"}</span></p>
 ${n.self_role?`<p><b>self_role</b> (${esc(n.self_role.kind)}) → <span class="mono">${(n.self_role.outputs||[]).map(esc).join(", ")}</span><br><span class="mono" style="color:var(--mut)">when ${esc(n.self_role.condition??"immediately")}</span></p>`:""}
 <p><b>writes so far</b> <span class="mono">${w.map(esc).join("<br>")||"nothing yet"}</span></p>
 <p><b>edges</b><br>${rel.map(e=>`<span class="mono" style="color:var(--mut)">${esc(e.from)} →(${e.kind})→ ${esc(e.to)} ${esc(e.label)}</span>`).join("<br>")||"—"}</p>`;
 paintGraph();}
document.querySelectorAll(".node").forEach(g=>g.addEventListener("click",()=>detail(g.dataset.id)));
// ---------- swimlanes ----------
const LH=24,LPAD=170,XW=Math.max(1250,N*8),LSVGH=laneOrder.length*LH+34;
const SC={active:"#3987e5",done:"#0ca30c",sleeping:"#fab219",waiting:"none",queued:"#52514e",starved:"#d03b3b",dropped:"#d03b3b"};
const x=i=>LPAD+(i/Math.max(LAST,1))*(XW-LPAD-20);
let lsvg=`<svg id="lanesvg" width="${XW}" height="${LSVGH}" xmlns="http://www.w3.org/2000/svg">`;
laneOrder.forEach((id,r)=>{const y=8+r*LH;
 lsvg+=`<text class="axis lanelabel" data-id="${esc(id)}" x="8" y="${y+11}">${esc(id)}</text>`;
 (segs[id]||[]).forEach(s=>{const w=Math.max(x(s.b)-x(s.a),2), fill=SC[s.s]||"#52514e";
  lsvg+=`<rect data-tip="<b>${esc(id)}</b> ${s.s} — e${s.a}→e${s.b} (t+${EV[s.a].t}s→t+${EV[s.b].t}s)" x="${x(s.a)}" y="${y}" width="${w}" height="13" rx="3" fill="${fill==="none"?"transparent":fill}" ${s.s==="waiting"?`stroke="#898781" stroke-dasharray="4 3"`:s.s==="sleeping"?`stroke="#c98500"`:""} ${fill!=="none"?"":""}/>`;
  if(s.s==="starved") lsvg+=`<text x="${x(s.b)-10}" y="${y+11}" fill="#d03b3b" font-size="11">&#10007;</text>`;});
});
EV.forEach(e=>{if(e.y==="write"&&e.a){const r=laneOrder.indexOf(e.a); if(r>=0) lsvg+=`<circle data-tip="<b>${esc(e.a)}</b> wrote <b>${esc(e.p)}</b> at e${e.i}" cx="${x(e.i)}" cy="${8+r*LH+6.5}" r="3.2" fill="#fff" stroke="#0ca30c" stroke-width="1.5"/>`;}});
lsvg+=`<line id="cursor1" y1="0" y2="${LSVGH}" stroke="#fff" stroke-width="1.4" opacity=".85"/>`;
lsvg+=`</svg>`; $("#lanes").innerHTML=lsvg;
document.querySelectorAll(".lanelabel").forEach(t=>t.addEventListener("click",()=>detail(t.dataset.id)));
// memory sparkline (cumulative writes) on same axis
{let c=0; const pts=EV.map((e,i)=>{if(e.y==="write")c++; return [x(i),c];}); const mx=Math.max(c,1), SH=64;
 const line=pts.map(p=>`${p[0]},${54-(p[1]/mx)*40}`).join(" ");
 $("#spark").innerHTML=`<svg id="sparksvg" width="${XW}" height="${SH}"><text class="axis" x="8" y="30">memory entries →</text><text class="axis" x="${LPAD}" y="12">${mx} total</text><polyline points="${line}" fill="none" stroke="#3987e5" stroke-width="2"/><line id="cursor2" y1="0" y2="${SH}" stroke="#fff" stroke-width="1.4" opacity=".85"/></svg>`;}
// ---------- planner chart ----------
if(DATA.planner_calls.length){$("#pchart").style.display="";const pc=DATA.planner_calls,mx=Math.max(...pc.map(p=>p.chars));
$("#pbars").innerHTML=`<svg width="${pc.length*34+80}" height="180">${pc.map((p,i)=>{const h=Math.round(p.chars/mx*130);
return `<rect class="bar" data-tip="call ${p.n}: <b>${p.chars.toLocaleString()}</b> chars — churn +${p.churn.added}/−${p.churn.removed}/~${p.churn.modified} — ${p.remaining} tasks left" x="${56+i*34}" y="${150-h}" width="24" height="${h}" rx="3"/><text class="axis" x="${58+i*34}" y="166">${p.n}</text>`;}).join("")}
<text class="axis" x="2" y="16">${mx.toLocaleString()} max</text></svg>`;}
// ---------- circuit table ----------
function circuitHTML(cur){if(!DATA.triggers.length)return `<p style="color:var(--mut)">No trigger table — this system has no circuit (central scheduler).</p>`;
 return `<table><tr><th>rule id</th><th>condition &phi;</th><th>wakes &sigma;</th><th>added</th><th>state at cursor</th></tr>`+DATA.triggers.map(t=>{
  const added=t.added_at!==null&&t.added_at<=cur, fired=t.fired_at!==null&&t.fired_at<=cur;
  let cls="r-pending",lab="not yet authored";
  if(fired){cls="r-fired";lab=`FIRED @e${t.fired_at}`;}
  else if(added&&cur>=LAST&&!t.fired){cls="r-dead";lab="DEAD — never became true";}
  else if(added){cls="r-armed";lab="armed, waiting";}
  return `<tr class="${cls}" data-seek="${t.fired_at??t.added_at??0}" style="cursor:pointer"><td class="mono">${esc(t.id)}</td><td class="mono">${esc(t.condition)}</td><td>${esc(t.agent)}</td><td class="mono">${t.added_at!==null?"e"+t.added_at:"—"}</td><td>${lab}</td></tr>`;}).join("")+`</table>`;}
// ---------- trajectory ----------
const TDOT={write:"#0ca30c",defer:"#fab219",trigger_fire:"#9085e9",trigger_add:"#9085e9",spawn:"#3987e5",self_role:"#3987e5",self_role_start:"#3987e5",conflict:"#d03b3b",rail_hit:"#d03b3b",route_invalid:"#d03b3b",stall:"#d03b3b",schema_mismatch:"#d03b3b",worker_invalid:"#d03b3b"};
const types=[...new Set(EV.map(e=>e.y))], on=new Set(types);
$("#tfilters").innerHTML=types.map(t=>`<label class="on" data-t="${esc(t)}">${esc(t)}</label>`).join("");
function drawT(){const q=$("#tsearch").value.toLowerCase();
 $("#ttable").innerHTML=`<table><tr><th>#</th><th>t+s</th><th>event</th><th>what happened</th></tr>`+EV.filter(e=>on.has(e.y)&&(!q||e.x.toLowerCase().includes(q))).map(e=>
  `<tr id="ev${e.i}" class="${e.i===CUR?"cur":e.i>CUR?"future":""}" data-seek="${e.i}" style="cursor:pointer"><td class="mono">${e.i}</td><td class="mono">${e.t}</td><td class="mono"><span class="tdot" style="background:${TDOT[e.y]||"#898781"}"></span>${esc(e.y)}</td><td>${esc(e.x)}</td></tr>`).join("")+`</table>`;}
document.querySelectorAll("#tfilters label").forEach(l=>l.addEventListener("click",()=>{const t=l.dataset.t; on.has(t)?on.delete(t):on.add(t); l.classList.toggle("on"); drawT();}));
$("#tsearch").addEventListener("input",drawT);
// ---------- memory ----------
const entryByPath={}; DATA.entries.forEach(e=>entryByPath[e.path]=e);
function drawM(cur){const q=$("#msearch").value.toLowerCase(); const seen=replay(cur).mem;
 const uniq=[...new Set(seen)]; $("#memcount").textContent=`— ${uniq.length}/${DATA.entries.length} entries at cursor`;
 const lastPath=seen[seen.length-1];
 $("#mlist").innerHTML=uniq.filter(p=>!q||p.toLowerCase().includes(q)).map(p=>{const e=entryByPath[p]||{value:"",chars:0,author:""};
  return `<details class="${p===lastPath?"new":""}"><summary><b class="mono">${esc(p)}</b> <span style="color:var(--mut)">— ${e.chars.toLocaleString()} chars${e.author?" by "+esc(e.author):""}</span></summary><pre>${esc(e.value)}</pre></details>`;}).join("")||`<p style="color:var(--mut)">nothing written yet</p>`;}
$("#msearch").addEventListener("input",()=>drawM(CUR));
// ---------- event inspector ----------
function refs(c){return [...String(c||"").matchAll(/done\("([^"]+)"\)/g)].map(m=>m[1]);}
function capPaths(s){return [...String(s||"").matchAll(/root(?:\.\d+)*\/[a-z][a-z0-9_]*/g)].map(m=>m[0]);}
function visibleAt(id,i,cond,capsule){const parts=id.split("."),pre=[];
 for(let k=1;k<=parts.length;k++)pre.push(parts.slice(0,k).join(".")+"/");
 const named=new Set([...refs(cond),...capPaths(capsule)]);
 const seen=new Set();
 for(const e of EV){if(e.i>=i)break; if(e.y==="write"&&(pre.some(p=>String(e.p).startsWith(p))||named.has(e.p)))seen.add(e.p);}
 return [...seen];}
function kv(rows){return `<table>${rows.map(([k,v])=>`<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join("")}</table>`;}
function inspect(){const e=EV[CUR]||{}; let h="";
 if((e.y==="agent_start"||e.y==="self_role_start")&&byId[e.a]){const n=byId[e.a];
  const isSR=e.y==="self_role_start", d=e.doc||{}, cond=isSR?(n.self_role?.condition):(d.condition??n.condition), caps=d.capsule??n.capsule;
  h+=`<h4>INPUT — what ${esc(e.a)} receives ${isSR?"(self_role continuation, straight to worker)":"(routing turn)"}</h4>`;
  h+=kv([["task",esc(isSR?"(its own self_role job — outputs below)":(d.task??n.task))||"—"],
         ["capsule",esc(caps)||"—"],
         ["start condition",`<span class="mono">${esc(cond??"none (immediate)")}</span>`],
         ["must produce",`<span class="mono">${((isSR?n.self_role?.outputs:d.expected_outputs?.map(o=>o.path??o))||n.outputs||[]).map(p=>esc(typeof p==="object"?p.path:p)).join("<br>")||"—"}</span>`]]);
  const vis=visibleAt(e.a,e.i,cond,caps);
  h+=`<h4 style="margin-top:12px">visible memory at this instant <span class="k">(reconstructed from the visibility rule: ancestors + condition refs + capsule paths)</span></h4>`;
  h+=vis.length?vis.map(p=>{const en=entryByPath[p]||{chars:0};return `<div class="mono">${esc(p)} <span class="k">— ${en.chars.toLocaleString()} chars</span></div>`;}).join(""):`<span class="k">(empty — this agent starts blind)</span>`;}
 else if(e.y==="route"&&e.doc){
  h+=`<h4>OUTPUT — action document generated by ${esc(e.a)}: <b>${esc(e.doc.action)}</b></h4>`;
  if(e.doc.reasoning)h+=`<div class="reason">"${esc(e.doc.reasoning)}"</div>`;
  const rest={...e.doc}; delete rest.reasoning; delete rest.task_id;
  h+=`<pre>${esc(JSON.stringify(rest,null,2))}</pre>`;}
 else if(e.y==="write"&&entryByPath[e.p]){const en=entryByPath[e.p];
  h+=`<h4>OUTPUT — artifact written by ${esc(e.a)} at <span class="mono">${esc(e.p)}</span> (${en.chars.toLocaleString()} chars)</h4><pre>${esc(en.value)}</pre>`;}
 else if(e.y==="route_repair"&&e.doc){
  h+=`<h4>VALIDATOR — rejected ${esc(e.a)}'s document (repair attempt follows)</h4><pre>${esc((e.doc.notes||[]).join("\n"))}</pre>`;}
 else if(e.y==="self_role"&&byId[e.a]?.self_role){const sr=byId[e.a].self_role;
  h+=`<h4>${esc(e.a)} registers its self_role (${esc(sr.kind)})</h4>`+kv([["will produce",`<span class="mono">${(sr.outputs||[]).map(esc).join("<br>")}</span>`],["gated on",`<span class="mono">${esc(sr.condition??"nothing — starts immediately")}</span>`]]);}
 else h=`<span class="k">no payload on <b>${esc(e.y)}</b> — agent_start / self_role_start carry the input side; route / write / route_repair carry the output side. Step with ←/→.</span>`;
 $("#evdetail").innerHTML=h;}
// ---------- paint at cursor ----------
let CUR=LAST;
function paintGraph(){const cur=replay(CUR);
 document.querySelectorAll(".node").forEach(g=>{const id=g.dataset.id, s=cur.st[id];
  g.setAttribute("class",`node ${s?("st-"+s):"ghost"} ${SEL===id?"sel":""}`);
  const sub=g.querySelector("[data-sub]"), n=byId[id], w=(cur.writes[id]||[]).length;
  sub.textContent = s==="starved"?"STARVED":s==="dropped"?"DROPPED":w?`wrote ${w} ${w>1?"entries":"entry"}`:(s||"").padEnd(0)||n.task.slice(0,22);});
 gEdges.forEach((e,i)=>{const p=document.getElementById("e"+i);
  p.classList.toggle("ghost",e.at>CUR);
  const rel=SEL&&(e.from===SEL||e.to===SEL);
  p.classList.toggle("hl",!!rel); p.classList.toggle("fade",SEL&&!rel);});}
function paint(){
 $("#scrub").value=CUR; const e=EV[CUR]||{t:0,y:"—",x:"empty trace"};
 $("#eclock").textContent=`event ${CUR}/${LAST} · t+${e.t}s`;
 $("#evcard").innerHTML=`<b>e${CUR} · ${esc(e.y)}</b> — ${esc(e.x)}`;
 $("#evcard").style.borderLeftColor=TDOT[e.y]||"#3987e5";
 paintGraph(); if(SEL)detail(SEL); inspect();
 const cx=x(CUR); $("#cursor1")?.setAttribute("x1",cx); $("#cursor1")?.setAttribute("x2",cx);
 $("#cursor2")?.setAttribute("x1",cx); $("#cursor2")?.setAttribute("x2",cx);
 $("#ctable").innerHTML=circuitHTML(CUR);
 document.querySelectorAll("#ctable tr[data-seek]").forEach(r=>r.addEventListener("click",()=>seek(+r.dataset.seek)));
 drawT(); const row=document.getElementById("ev"+CUR); if(row&&playing)row.scrollIntoView({block:"center"});
 document.querySelectorAll("#ttable tr[data-seek]").forEach(r=>r.addEventListener("click",()=>seek(+r.dataset.seek)));
 drawM(CUR);}
function seek(i){CUR=Math.max(0,Math.min(LAST,i)); paint();}
$("#scrub").max=LAST; $("#scrub").addEventListener("input",()=>seek(+$("#scrub").value));
$("#stepb").addEventListener("click",()=>seek(CUR-1)); $("#stepf").addEventListener("click",()=>seek(CUR+1));
let playing=null;
function toggle(){if(playing){clearInterval(playing);playing=null;$("#play").innerHTML="&#9654; play";}
 else{if(CUR>=LAST)CUR=-1;$("#play").innerHTML="&#10074;&#10074; pause";playing=setInterval(()=>{if(CUR>=LAST)return toggle();seek(CUR+1);},+$("#speed").value);}}
$("#play").addEventListener("click",toggle);
$("#speed").addEventListener("change",()=>{if(playing){clearInterval(playing);playing=setInterval(()=>{if(CUR>=LAST)return toggle();seek(CUR+1);},+$("#speed").value);}});
document.addEventListener("keydown",e=>{if(e.target.tagName==="INPUT"&&e.target.type==="search")return;
 if(e.key==="ArrowLeft"){seek(CUR-1);e.preventDefault();} if(e.key==="ArrowRight"){seek(CUR+1);e.preventDefault();}
 if(e.key===" "){toggle();e.preventDefault();}});
// shared tooltip
const tip=$("#ttip");
document.addEventListener("mousemove",e=>{const t=e.target.closest("[data-tip]");
 if(t){tip.style.display="block";tip.innerHTML=t.dataset.tip;tip.style.left=Math.min(e.clientX+14,window.innerWidth-400)+"px";tip.style.top=(e.clientY+14)+"px";}
 else tip.style.display="none";});
if(location.hash.match(/^#e\d+$/)) CUR=Math.min(LAST,+location.hash.slice(2));
paint();
</script></body></html>"""


def main() -> int:
    run_dir = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else run_dir / "view.html"
    data = build_data(run_dir)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(PAGE.replace("__TITLE__", data["run"]).replace("__DATA__", payload), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
