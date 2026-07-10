"""Interactive single-file run visualizer.

    python3 -m src.visualize <run_dir> [out.html]

Emits <run_dir>/view.html: a self-contained page (inline CSS/JS, no
network) with an interactive agent-circuit graph (click nodes for
details; spawn vs waits-on edges; dead triggers highlighted), the
verbatim trigger table C, a filterable trajectory, and searchable
global memory D. Works on RATD runs (state.sqlite + trace.jsonl) and
tree/planner baseline runs (entries.json / plan.json + trace.jsonl);
planner runs get a context-growth chart instead of a circuit.
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
    events = []
    trace = run_dir / "trace.jsonl"
    if trace.exists():
        events = [json.loads(l) for l in trace.read_text(encoding="utf-8").splitlines()]
    t0 = events[0]["ts"] if events else 0

    entries, triggers = [], []
    if (run_dir / "state.sqlite").exists():
        db = sqlite3.connect(run_dir / "state.sqlite")
        entries = [
            {"path": k, "value": v, "author": a, "chars": len(str(v))}
            for k, v, a in db.execute("SELECT namespace_key, value, author FROM entries ORDER BY created_at")
        ]
        triggers = [
            {"id": i, "condition": c, "agent": json.loads(s).get("task_id", "?"), "fired": bool(f)}
            for i, c, s, f in db.execute("SELECT id, condition, agent_spec, fired FROM triggers")
        ]
    elif (run_dir / "entries.json").exists():
        raw = json.loads((run_dir / "entries.json").read_text(encoding="utf-8"))
        entries = [{"path": k, "value": v, "author": "", "chars": len(str(v))} for k, v in raw.items()]

    metrics = {}
    if (run_dir / "metrics.json").exists():
        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))

    nodes: dict[str, dict] = {}

    def node(tid: str) -> dict:
        return nodes.setdefault(tid, {"id": tid, "task": "", "capsule": "", "condition": None,
                                      "outputs": [], "badges": [], "writes": [], "self_role": None})

    edges: list[dict] = []
    for e in events:
        t = e.get("event")
        if t in ("enqueue", "agent_start") and isinstance(e.get("agent"), dict) and e["agent"].get("task_id") == "root":
            n = node("root")
            n["task"] = e["agent"].get("task", "")
        elif t == "spawn":
            c = e["child"]
            n = node(c["task_id"])
            n.update(task=c.get("task", ""), capsule=c.get("capsule", ""), condition=c.get("condition"),
                     outputs=[o.get("path") for o in c.get("expected_outputs", [])])
            node(e["parent"])
            edges.append({"from": e["parent"], "to": c["task_id"], "kind": "spawn", "label": ""})
            for ref in condition_refs(c.get("condition") or ""):
                edges.append({"from": ns_owner(ref), "to": c["task_id"], "kind": "waits", "label": ref})
        elif t == "self_role":
            n = node(e["agent"])
            n["self_role"] = {"kind": e.get("kind"), "outputs": e.get("outputs"), "condition": e.get("condition")}
            if "self_role" not in n["badges"]:
                n["badges"].append("self_role")
            for ref in condition_refs(e.get("condition") or ""):
                edges.append({"from": ns_owner(ref), "to": e["agent"], "kind": "waits", "label": ref})
        elif t == "defer":
            n = node(e["agent"])
            n["badges"].append("DEFER")
            for ref in condition_refs(e.get("wake_condition") or ""):
                edges.append({"from": ns_owner(ref), "to": e["agent"], "kind": "wake", "label": ref})
        elif t == "route_invalid":
            node(e["agent"])["badges"].append("DROPPED")
        elif t == "write":
            if e.get("author") in nodes:
                nodes[e["author"]]["writes"].append(e.get("path"))

    plan_path = run_dir / "plan.json"
    if not nodes and plan_path.exists():
        for tsk in json.loads(plan_path.read_text(encoding="utf-8")):
            n = node(tsk["id"])
            n.update(task=tsk.get("goal", ""), condition=tsk.get("condition"),
                     outputs=[o.get("path") for o in tsk.get("outputs", [])])
            parent = ".".join(tsk["id"].split(".")[:-1]) or "root"
            node(parent)
            edges.append({"from": parent, "to": tsk["id"], "kind": "spawn", "label": ""})
            for ref in condition_refs(tsk.get("condition") or ""):
                edges.append({"from": ns_owner(ref), "to": tsk["id"], "kind": "waits", "label": ref})

    dead = {tr["id"] for tr in triggers if not tr["fired"]}
    for tr in triggers:
        if not tr["fired"] and tr["agent"] in nodes:
            nodes[tr["agent"]]["badges"].append("STARVED" if ":defer" in tr["id"] else "NEVER-FIRED")

    planner_calls = [
        {"n": e.get("n"), "chars": e.get("context_chars"), "churn": e.get("churn"), "remaining": e.get("remaining")}
        for e in events if e.get("event") == "planner_call"
    ]
    ev_rows = [{"t": round(e.get("ts", 0) - t0, 1), "type": e.get("event"), "text": summarize_event(e)} for e in events]
    return {
        "run": run_dir.name, "metrics": metrics, "nodes": list(nodes.values()), "edges": edges,
        "triggers": triggers, "events": ev_rows, "entries": entries, "planner_calls": planner_calls,
        "dead_rules": len(dead),
    }


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title><style>
:root{--bg:#0f1420;--card:#171e2e;--line:#2a3550;--fg:#dce4f2;--dim:#8a97b0;--acc:#5aa2ff;--ok:#3fbf7f;--bad:#ff5f6b;--warn:#ffb454;--spawn:#5aa2ff;--waits:#ffb454;--wake:#c792ea}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{position:sticky;top:0;z-index:9;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 20px;display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
header h1{font-size:16px;margin:0}header nav a{color:var(--acc);text-decoration:none;margin-right:12px;font-size:13px}
.chip{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;border:1px solid var(--line);color:var(--dim)}
.chip.ok{color:var(--ok);border-color:var(--ok)}.chip.bad{color:var(--bad);border-color:var(--bad)}
section{margin:18px 20px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
h2{font-size:14px;margin:0 0 12px;color:var(--acc);text-transform:uppercase;letter-spacing:.06em}
table{border-collapse:collapse;width:100%;font-size:13px}th{text-align:left;color:var(--dim);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--line)}
td{padding:5px 10px;border-bottom:1px solid #1e273c;vertical-align:top}tr:hover td{background:#1b2438}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:12px}
#graphwrap{display:flex;gap:16px}#gsvg{overflow:auto;flex:1;border:1px solid var(--line);border-radius:8px;background:#0c111c}
#detail{width:340px;flex-shrink:0;font-size:13px}#detail .empty{color:var(--dim)}
.node rect{fill:#1d2740;stroke:var(--line);stroke-width:1.2;rx:7;cursor:pointer}
.node.sel rect{stroke:var(--acc);stroke-width:2.5}.node.wrote rect{stroke:var(--ok)}
.node.dead rect{stroke:var(--bad);stroke-width:2}.node text{fill:var(--fg);font-size:12px;pointer-events:none}
.node text.sub{fill:var(--dim);font-size:10px}
.edge{fill:none;stroke-width:1.6;opacity:.75}.edge.spawn{stroke:var(--spawn)}.edge.waits{stroke:var(--waits);stroke-dasharray:5 4}
.edge.wake{stroke:var(--wake);stroke-dasharray:2 4;stroke-width:2}.edge.hl{opacity:1;stroke-width:3}
.edge.fade{opacity:.12}.legend{font-size:12px;color:var(--dim);margin-top:8px}
.legend span{margin-right:16px}.sw{display:inline-block;width:22px;height:0;border-top:3px solid;vertical-align:middle;margin-right:5px}
.badge{display:inline-block;font-size:10px;padding:1px 7px;border-radius:9px;margin-left:6px;background:#26314d;color:var(--warn)}
.badge.b-DROPPED,.badge.b-STARVED,.badge.b-NEVER-FIRED{background:#3a1b22;color:var(--bad)}
tr.dead td{background:#2b161c}tr.fired td:last-child{color:var(--ok)}tr.dead td:last-child{color:var(--bad);font-weight:700}
input[type=search]{background:#0c111c;border:1px solid var(--line);color:var(--fg);border-radius:6px;padding:6px 10px;width:260px;margin-bottom:10px}
.filters{margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px}
.filters label{border:1px solid var(--line);border-radius:12px;padding:2px 10px;font-size:12px;color:var(--dim);cursor:pointer;user-select:none}
.filters label.on{color:var(--fg);border-color:var(--acc);background:#1c2a45}
details{border:1px solid var(--line);border-radius:8px;margin:6px 0;padding:6px 12px}summary{cursor:pointer;color:var(--fg)}
details pre{white-space:pre-wrap;color:var(--dim);font-size:12px;max-height:420px;overflow:auto}
.bar{fill:var(--acc)}.bar:hover{fill:var(--warn)}.axis{fill:var(--dim);font-size:11px}
td.et-defer,td.et-trigger_fire{color:var(--warn)}td.et-conflict,td.et-rail_hit,td.et-route_invalid,td.et-stall{color:var(--bad)}
td.et-write{color:var(--ok)}td.et-trigger_add{color:var(--wake)}
</style></head><body>
<header><h1 id="ttl"></h1><span id="chips"></span>
<nav><a href="#graph">graph</a><a href="#circuit">circuit</a><a href="#traj">trajectory</a><a href="#mem">memory</a></nav></header>
<section id="graph"><h2>Agent circuit graph <span style="color:var(--dim);text-transform:none;letter-spacing:0">— click a node</span></h2>
<div id="graphwrap"><div id="gsvg"></div><div id="detail"><div class="empty">Click a node to inspect its capsule, contract, and writes. Edges to/from it light up.</div></div></div>
<div class="legend"><span><span class="sw" style="border-color:var(--spawn)"></span>spawn</span>
<span><span class="sw" style="border-color:var(--waits);border-top-style:dashed"></span>waits-on (trigger dependency)</span>
<span><span class="sw" style="border-color:var(--wake);border-top-style:dotted"></span>defer-wake</span>
<span style="color:var(--ok)">green border = wrote data</span> <span style="color:var(--bad)">red = dead trigger / dropped</span></div></section>
<section id="pchart" style="display:none"><h2>Planner context per call</h2><div id="pbars"></div></section>
<section id="circuit"><h2>Circuit — trigger table C (verbatim)</h2><div id="ctable"></div></section>
<section id="traj"><h2>Trajectory</h2><input type="search" id="tsearch" placeholder="search events…"><div class="filters" id="tfilters"></div><div id="ttable"></div></section>
<section id="mem"><h2>Global memory D (accumulation order)</h2><input type="search" id="msearch" placeholder="filter paths…"><div id="mlist"></div></section>
<script>const DATA = __DATA__;
const $=q=>document.querySelector(q), esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
document.title=DATA.run; $("#ttl").textContent="Run: "+DATA.run;
const m=DATA.metrics||{}, chips=[];
if("converged" in m) chips.push(`<span class="chip ${m.converged?"ok":"bad"}">${m.converged?"converged":"NOT converged"}</span>`);
for(const k of ["llm_calls","max_depth","agent_count","defer_count","planner_calls","termination"]) if(m[k]!==undefined) chips.push(`<span class="chip">${k}: ${esc(m[k])}</span>`);
if(DATA.dead_rules) chips.push(`<span class="chip bad">dead rules: ${DATA.dead_rules}</span>`);
$("#chips").innerHTML=chips.join(" ");
// ---- graph ----
const nodes=DATA.nodes, byId={}; nodes.forEach(n=>byId[n.id]=n);
const depth=id=>id==="root"?0:id.split(".").length-1;
const cols={}; nodes.sort((a,b)=>a.id.localeCompare(b.id)).forEach(n=>{(cols[depth(n.id)]??=[]).push(n);});
const CW=210,RH=64,W=Math.max(...Object.keys(cols).map(Number),0)*CW+230,H=Math.max(...Object.values(cols).map(c=>c.length),1)*RH+40;
nodes.forEach(n=>{const d=depth(n.id),i=cols[d].indexOf(n); n.x=30+d*CW; n.y=24+i*RH;});
const edges=DATA.edges.filter(e=>byId[e.from]&&byId[e.to]);
let svg=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">`;
svg+=`<defs>${["spawn","waits","wake"].map(k=>`<marker id="m-${k}" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="${{spawn:"#5aa2ff",waits:"#ffb454",wake:"#c792ea"}[k]}"/></marker>`).join("")}</defs>`;
edges.forEach((e,i)=>{const a=byId[e.from],b=byId[e.to],x1=a.x+150,y1=a.y+21,x2=b.x,y2=b.y+21,mx=(x1+x2)/2;
svg+=`<path id="e${i}" class="edge ${e.kind}" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}" marker-end="url(#m-${e.kind})"><title>${esc(e.kind)} ${esc(e.label)}</title></path>`;});
nodes.forEach(n=>{const cls=["node"]; if(n.writes.length)cls.push("wrote"); if(n.badges.some(b=>["DROPPED","STARVED","NEVER-FIRED"].includes(b)))cls.push("dead");
svg+=`<g class="${cls.join(" ")}" data-id="${esc(n.id)}" transform="translate(${n.x},${n.y})"><rect width="150" height="42" rx="7"/><text x="10" y="17">${esc(n.id)}</text><text x="10" y="33" class="sub">${esc((n.badges.join(" · ")||n.task).slice(0,22))}</text></g>`;});
svg+="</svg>"; $("#gsvg").innerHTML=svg;
function pick(id){document.querySelectorAll(".node").forEach(g=>g.classList.toggle("sel",g.dataset.id===id));
edges.forEach((e,i)=>{const p=document.getElementById("e"+i); p.classList.toggle("hl",e.from===id||e.to===id); p.classList.toggle("fade",!(e.from===id||e.to===id));});
const n=byId[id], rel=DATA.edges.filter(e=>e.from===id||e.to===id);
$("#detail").innerHTML=`<h3 style="margin:0 0 8px">${esc(id)} ${n.badges.map(b=>`<span class="badge b-${esc(b)}">${esc(b)}</span>`).join("")}</h3>
<p><b>task</b> ${esc(n.task)||"—"}</p><p><b>capsule</b> <span style="color:var(--dim)">${esc(n.capsule)||"—"}</span></p>
<p><b>start condition</b> <span class="mono">${esc(n.condition??"none (immediate)")}</span></p>
<p><b>assigned outputs</b> <span class="mono">${n.outputs.map(esc).join("<br>")||"—"}</span></p>
${n.self_role?`<p><b>self_role</b> (${esc(n.self_role.kind)}) → <span class="mono">${(n.self_role.outputs||[]).map(esc).join(", ")}</span><br><span class="mono" style="color:var(--dim)">when ${esc(n.self_role.condition??"immediately")}</span></p>`:""}
<p><b>wrote</b> <span class="mono">${n.writes.map(esc).join("<br>")||"nothing"}</span></p>
<p><b>edges</b><br>${rel.map(e=>`<span class="mono" style="color:var(--dim)">${esc(e.from)} →(${e.kind})→ ${esc(e.to)} ${esc(e.label)}</span>`).join("<br>")||"—"}</p>`;}
document.querySelectorAll(".node").forEach(g=>g.addEventListener("click",()=>pick(g.dataset.id)));
// ---- planner chart ----
if(DATA.planner_calls.length){$("#pchart").style.display="";const pc=DATA.planner_calls,mx=Math.max(...pc.map(p=>p.chars));
$("#pbars").innerHTML=`<svg width="${pc.length*34+70}" height="180">${pc.map((p,i)=>{const h=Math.round(p.chars/mx*130);
return `<rect class="bar" x="${50+i*34}" y="${150-h}" width="24" height="${h}"><title>call ${p.n}: ${p.chars.toLocaleString()} chars, churn +${p.churn.added}/-${p.churn.removed}/~${p.churn.modified}</title></rect><text class="axis" x="${50+i*34}" y="165">${p.n}</text>`;}).join("")}
<text class="axis" x="0" y="20">${mx.toLocaleString()} chars max</text></svg><p style="color:var(--dim);font-size:12px">hover bars: context chars + plan churn per call</p>`;}
// ---- circuit ----
$("#ctable").innerHTML=DATA.triggers.length?`<table><tr><th>rule id</th><th>condition φ</th><th>wakes σ</th><th>fired</th></tr>${DATA.triggers.map(t=>`<tr class="${t.fired?"fired":"dead"}"><td class="mono">${esc(t.id)}</td><td class="mono">${esc(t.condition)}</td><td>${esc(t.agent)}</td><td>${t.fired?"YES":"NO — never became true"}</td></tr>`).join("")}</table>`
:`<p style="color:var(--dim)">No trigger table — this system has no circuit (central scheduler).</p>`;
// ---- trajectory ----
const types=[...new Set(DATA.events.map(e=>e.type))], on=new Set(types);
$("#tfilters").innerHTML=types.map(t=>`<label class="on" data-t="${esc(t)}">${esc(t)}</label>`).join("");
function drawT(){const q=$("#tsearch").value.toLowerCase();
$("#ttable").innerHTML=`<table><tr><th>t+s</th><th>event</th><th>what happened</th></tr>${DATA.events.filter(e=>on.has(e.type)&&(!q||e.text.toLowerCase().includes(q))).map(e=>`<tr><td class="mono">${e.t}</td><td class="mono et-${esc(e.type)}">${esc(e.type)}</td><td>${esc(e.text)}</td></tr>`).join("")}</table>`;}
document.querySelectorAll("#tfilters label").forEach(l=>l.addEventListener("click",()=>{const t=l.dataset.t; on.has(t)?on.delete(t):on.add(t); l.classList.toggle("on"); drawT();}));
$("#tsearch").addEventListener("input",drawT); drawT();
// ---- memory ----
function drawM(){const q=$("#msearch").value.toLowerCase();
$("#mlist").innerHTML=DATA.entries.filter(e=>!q||e.path.toLowerCase().includes(q)).map(e=>`<details><summary><b class="mono">${esc(e.path)}</b> <span style="color:var(--dim)">— ${e.chars.toLocaleString()} chars${e.author?" by "+esc(e.author):""}</span></summary><pre>${esc(e.value)}</pre></details>`).join("")||`<p style="color:var(--dim)">no entries</p>`;}
$("#msearch").addEventListener("input",drawM); drawM();
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
