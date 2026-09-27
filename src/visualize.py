"""Interactive run-replay visualizer (v2 / ET series; also handles legacy v3-style traces).

    python3 -m src.visualize <run_dir> [out.html]

One self-contained dark HTML page per run (inline CSS/JS, no network) that
replays a RATD run event by event. Rebuilt for the v2 substrate: multi-round
ReAct agents, the K/W/G memory planes, the expression-condition circuit, and the
ET measurements around prompt size and handoff costs. The page includes a time
scrubber, live circuit graph, per-agent swimlanes, rule table, searchable
trajectory, and global memory view. It reads v2 run directories (trace.jsonl +
state.json + metrics.json + run_meta.json) and is tolerant of legacy sqlite/
entries-style runs used by earlier phases.

The circuit is foregrounded: rules are (φ, σ, provenance), and the graph shows
artifact-author -> woken-agent wiring as stigmergic coordination. The memory
depiction shows where artifacts live across K (catalog index), W (per-agent
workspaces), and G (linear-versioned global). Plus the central ET measurement:
per-round prompt size per agent, which captures the planner-vs-RATD cost
signature.
"""
"""
from __future__ import annotations

import json
import json
import re
import sqlite3
import sys
from pathlib import Path

from .phase1 import condition_refs

# --- v2 condition parsing: pull the state sources a rule's expression touches.
# The namespace is fixed (Playground Spec v2 §3): only these read-only accessors
# are referenceable, so a regex over the frozen accessor set is exact enough to
# recover a rule's wiring for display.
RE_AGENT = re.compile(r"(?:state|children)\(\s*[\"']([^\"']+)[\"']")
RE_FIRED = re.compile(r"fired\(\s*[\"']([^\"']+)[\"']")
RE_PATH = re.compile(r"(?:exists|head|field|history|matching|count)\(\s*[\"']([^\"']+)[\"']")

ARM_LABEL = {"r": "RATD · multi-round", "p": "Planner · centralized",
             "s": "Stigmergic · single-shot"}

    }


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title><style>
:root{--page:#0d0d0d;--card:#1a1a19;--card2:#232322;--ink:#fff;--ink2:#c3c2b7;--mut:#898781;--grid:#2c2c2a;--base:#383835;--ring:rgba(255,255,255,.1);
--e-spawn:#3987e5;--e-waits:#199e70;--e-wake:#9085e9;--e-stig:#e0952b;--s-run:#3987e5;--s-done:#0ca30c;--s-wait:#fab219;--s-fail:#d03b3b;--s-spawned:#6f6d67;--s-active:#3987e5;--s-sleep:#fab219;--s-dead:#d03b3b;--plane-k:#5aa9c9;--plane-w:#c99be0;--plane-g:#5fbf8f}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--page);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:14px 22px 6px;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}header h1{font-size:17px;margin:0}
.chip{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;border:1px solid var(--ring);color:var(--ink2)}
.chip.ok{color:var(--s-done);border-color:var(--s-done)}.chip.bad{color:var(--s-fail);border-color:var(--s-fail)}
.chip.arm{color:var(--e-wake);border-color:var(--e-wake);font-weight:600}
#tasktext{margin:2px 22px 0;color:var(--mut);font-size:12.5px;max-width:1100px}
#controls{position:sticky;top:0;z-index:20;background:var(--page);border-bottom:1px solid var(--grid);padding:10px 22px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
#controls button,#controls select{background:var(--card2);color:var(--ink);border:1px solid var(--ring);border-radius:7px;padding:5px 12px;font-size:13px;cursor:pointer}
#controls button:hover{border-color:var(--e-spawn)}#scrub{flex:1;min-width:220px;accent-color:var(--e-spawn)}
#eclock{font-variant-numeric:tabular-nums;color:var(--mut);font-size:12px;min-width:150px}

#evcard{width:100%;background:var(--card);border:1px solid var(--grid);border-left:4px solid var(--e-spawn);border-radius:8px;padding:7px 12px;font-size:13px;color:var(--ink2)}
#evcard b{color:var(--ink)}
section{margin:16px 22px;background:var(--card);border:1px solid var(--grid);border-radius:10px;padding:16px}
h2{font-size:13px;margin:0 0 12px;color:var(--ink2);text-transform:uppercase;letter-spacing:.07em}h2 small{color:var(--mut);text-transform:none;letter-spacing:0;font-weight:400}
table{border-collapse:collapse;width:100%;font-size:13px}th{text-align:left;color:var(--mut);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--base)}
td{padding:5px 10px;border-bottom:1px solid var(--grid);vertical-align:top}tbody tr:hover td{background:var(--card2)}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:12px}
#graphwrap{display:flex;gap:16px}#gsvg{overflow:auto;flex:1;border:1px solid var(--grid);border-radius:8px;background:var(--page);max-height:760px;resize:vertical}
#detail{width:360px;flex-shrink:0;font-size:13px;color:var(--ink2)}#detail b{color:var(--ink)}#detail .empty{color:var(--mut)}
.node rect{fill:var(--card2);stroke:var(--base);stroke-width:1.3;cursor:pointer}
.node.ghost{opacity:.13}.node.sel rect{stroke:#fff;stroke-width:2.8}
.node.dim{opacity:.16}
.node.st-running rect{stroke:var(--s-run);stroke-width:2.4}.node.st-done rect{stroke:var(--s-done);stroke-width:2}
.node.st-waiting rect{stroke:var(--s-wait);stroke-width:2.2;stroke-dasharray:6 3}.node.st-spawned rect{stroke:var(--mut);stroke-dasharray:4 4}
.node.st-failed rect,.node.st-terminated rect{stroke:var(--s-fail);stroke-width:2.4}
.node.starved rect{stroke:var(--s-fail);stroke-width:2.4;stroke-dasharray:6 3}
.node text{fill:var(--ink);font-size:13px;pointer-events:none}.node text.sub{fill:var(--mut);font-size:11px}.node text.role{fill:var(--mut);font-size:10px}
/* three node kinds */
.gn-rule rect{fill:#1b192a;stroke:#4a4668;stroke-width:1.3;cursor:pointer}
.gn-rule.rs-armed rect{stroke:var(--s-wait);stroke-width:2}.gn-rule.rs-fired rect{stroke:var(--s-done);stroke-width:2}
.gn-rule.rs-disabled rect{stroke:var(--mut);stroke-dasharray:3 3}.gn-rule.rs-pending{opacity:.32}
.gn-rule text{fill:#d3cdf0}.gn-rule text.sub{fill:#8b84b3}
.gn-art rect{fill:#141613;stroke:var(--base);stroke-width:1.3;cursor:pointer}
.gn-art.plane-G rect{stroke:var(--plane-g)}.gn-art.plane-W rect{stroke:var(--plane-w)}
.gn-art.ghost{opacity:.22}.gn-art.phantom rect{fill:none;stroke-dasharray:3 3;opacity:.55}
.gn-art.divg rect{stroke:var(--e-stig);stroke-width:2.4}
.gn-art text{fill:var(--ink2);font-size:11px;pointer-events:none}
.edge{fill:none;stroke-width:1.7;opacity:.42}
.edge.ek-spawn{stroke:var(--e-spawn);opacity:.7}
.edge.ek-write{stroke:var(--plane-w)}
.edge.ek-read{stroke:var(--plane-g);stroke-dasharray:5 3}
.edge.ek-gate{stroke:var(--e-stig);stroke-dasharray:2 3;opacity:.6}
.edge.ek-state{stroke:var(--e-wake);stroke-dasharray:6 4}
.edge.ek-fire{stroke:var(--e-wake);stroke-width:2.2;opacity:.62}
.edge.hl{opacity:1!important;stroke-width:3.4}.edge.fade{opacity:.05}.edge.ghost{display:none}
.legend{font-size:12px;color:var(--mut);margin-top:10px;display:flex;flex-wrap:wrap;gap:16px;align-items:center}
.sw{display:inline-block;width:22px;height:0;border-top:3px solid;vertical-align:middle;margin-right:5px}
.dot{display:inline-block;width:10px;height:10px;border-radius:3px;vertical-align:middle;margin-right:5px}
#lanes,#ctxwrap{overflow-x:auto;border:1px solid var(--grid);border-radius:8px;background:var(--page)}
.lanelabel{cursor:pointer}.lanelabel:hover{fill:var(--ink)}
#ttip{position:fixed;display:none;background:var(--card2);border:1px solid var(--ring);border-radius:7px;padding:6px 10px;font-size:12px;color:var(--ink2);pointer-events:none;z-index:50;max-width:420px}
#ttip b{color:var(--ink)}
tr.cur td{background:#22303e!important;border-left:3px solid var(--e-spawn)}tr.future{opacity:.35}
tr.r-armed td:last-child{color:var(--s-wait)}tr.r-fired td:last-child{color:var(--s-done)}tr.r-disabled td:last-child{color:var(--mut)}tr.r-pending{opacity:.4}tr.r-dead td:last-child{color:var(--s-fail);font-weight:700}
tr.r-nonauthor td{box-shadow:inset 3px 0 0 var(--e-stig)}

input[type=search]{background:var(--page);border:1px solid var(--base);color:var(--ink);border-radius:7px;padding:6px 10px;width:260px;margin-bottom:10px}
.filters{margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px}
.filters label{border:1px solid var(--base);border-radius:12px;padding:2px 10px;font-size:12px;color:var(--mut);cursor:pointer;user-select:none}
.filters label.on{color:var(--ink);border-color:var(--e-spawn);background:#1c2a3a}
details{border:1px solid var(--grid);border-radius:8px;margin:6px 0;padding:6px 12px}summary{cursor:pointer}
details.new{border-color:var(--s-done)}details pre{white-space:pre-wrap;color:var(--ink2);font-size:12px;max-height:420px;overflow:auto}
#evdetail{font-size:13px;color:var(--ink2)}#evdetail h4{margin:2px 0 8px;color:var(--ink);font-size:13px}
#evdetail pre{white-space:pre-wrap;background:var(--page);border:1px solid var(--grid);border-radius:8px;padding:10px;max-height:420px;overflow:auto;font-size:12px}
#evdetail .k{color:var(--mut)}#evdetail table td:first-child{color:var(--mut);width:160px}
.reason{border-left:3px solid var(--e-spawn);background:var(--page);padding:7px 12px;border-radius:6px;margin:8px 0;color:var(--ink)}
.tag{display:inline-block;font-size:10px;padding:1px 6px;border-radius:5px;border:1px solid var(--base);color:var(--mut);margin-right:4px}
.tag.err{color:var(--s-fail);border-color:var(--s-fail)}.tag.cut{color:var(--e-stig);border-color:var(--e-stig)}
.planes{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.plane{background:var(--page);border:1px solid var(--grid);border-radius:8px;padding:10px}
.plane h3{margin:0 0 8px;font-size:12px;letter-spacing:.05em}
.plane.k h3{color:var(--plane-k)}.plane.w h3{color:var(--plane-w)}.plane.g h3{color:var(--plane-g)}
.art{border:1px solid var(--grid);border-radius:6px;padding:5px 8px;margin:5px 0;font-size:12px;background:var(--card2)}
.art.ghost{opacity:.3}.art .p{color:var(--ink);word-break:break-all}.art .meta{color:var(--mut);font-size:11px}
.art.div{border-color:var(--e-stig)}
.grp{color:var(--mut);font-size:11px;margin:8px 0 2px;text-transform:uppercase;letter-spacing:.05em}
.bar{fill:var(--e-spawn)}.bar:hover{fill:var(--s-wait)}.axis{fill:var(--mut);font-size:11px}
td .tdot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;vertical-align:baseline}
.tog{display:inline-flex;gap:5px;align-items:center;font-size:12px;color:var(--mut);cursor:pointer}
.hint{color:var(--mut);font-size:11.5px;margin:0 0 10px}
</style></head><body>
<header><h1 id="ttl"></h1><span id="chips"></span></header>
<div id="tasktext"></div>

<div id="controls">
 <button id="play">&#9654; play</button><button id="stepb">&#8592;</button><button id="stepf">&#8594;</button>
 <select id="speed"><option value="400">slow</option><option value="150" selected>normal</option><option value="60">fast</option></select>
 <input type="range" id="scrub" min="0" value="0"><span id="eclock"></span>
 <div id="evcard"><b>event 0</b> — drag the slider, press play, or use &larr;/&rarr; keys (space = play/pause)</div>
</div>
<section id="inspector"><h2>Event inspector <small>— the payload at the cursor: prompt in / reply out / tool result / artifact body / rule wiring</small></h2><div id="evdetail"></div></section>
<section id="graph"><h2>The circuit <small>— agents · rules · artifacts, laid out left→right by causal depth (root → workers → artifacts → rules); back-curving edges are the feedback that closes the loop</small></h2>
<p class="hint">The whole coordination loop, made of three node kinds. An agent <b>writes</b> an artifact into shared memory; a rule <b>gates</b> on that artifact (<span class="mono">exists("global/x.md")</span>) or on agent state (<span class="mono">state("a1")</span>); when true it <b>fires</b> to resume/spawn a target agent — <b>stigmergy</b>: coordination through the environment, not messages. A dashed <span style="color:var(--plane-g)">read</span> is the other half — an agent consuming an artifact directly (a handoff). Hollow dashed artifacts were <b>awaited but never written</b> (they explain dead rules). <b>Click a node</b> to isolate its neighbourhood; click empty space to reset.</p>
<div style="margin-bottom:10px;display:flex;gap:18px;flex-wrap:wrap;align-items:center"><label class="tog"><input type="checkbox" id="togR" checked> rules &amp; wiring</label><label class="tog"><input type="checkbox" id="togV"> &#8635; revive rules <span id="vcount" style="color:var(--mut)"></span></label><label class="tog"><input type="checkbox" id="togA" checked> artifacts &amp; memory flow</label><span class="hint" style="margin:0">scroll to pan · drag bottom edge to resize · click a node to focus it</span></div>
<div id="graphwrap"><div id="gsvg"></div><div id="detail"><div class="empty">Click any node — agent, rule, or artifact — to inspect it and highlight its wiring. Rule/artifact clicks also seek the replay to when it appeared.</div></div></div>
<div class="legend">
<span style="color:var(--ink2)">nodes:</span>
<span><span class="dot" style="background:var(--card2);border:1px solid var(--base)"></span>agent</span>
<span><span class="dot" style="background:#1b192a;border:1px solid #4a4668;border-radius:6px"></span>rule ◆</span>
<span><span class="dot" style="background:#141613;border:1px solid var(--plane-g);border-radius:6px"></span>G artifact ▤</span>
<span><span class="dot" style="background:#141613;border:1px solid var(--plane-w);border-radius:6px"></span>W artifact ▢</span>
<span style="border-left:1px solid var(--base);padding-left:16px;color:var(--ink2)">edges:</span>
<span><span class="sw" style="border-color:var(--e-spawn)"></span>spawn</span>
<span><span class="sw" style="border-color:var(--plane-w)"></span>write</span>
<span><span class="sw" style="border-color:var(--plane-g);border-top-style:dashed"></span>read (handoff)</span>
<span><span class="sw" style="border-color:var(--e-stig);border-top-style:dashed"></span>gate</span>
<span><span class="sw" style="border-color:var(--e-wake);border-top-style:dashed"></span>state</span>
<span><span class="sw" style="border-color:var(--e-wake)"></span>fire</span>
</div>
<div class="legend"><span style="color:var(--ink2)">agent state @cursor:</span>
<span><span class="dot" style="background:var(--s-run)"></span>running</span>
<span><span class="dot" style="border:2px dashed var(--mut)"></span>spawned</span>
<span><span class="dot" style="background:var(--s-wait)"></span>waiting</span>
<span><span class="dot" style="background:var(--s-done)"></span>done</span>
<span><span class="dot" style="background:var(--s-fail)"></span>failed</span>
<span style="border-left:1px solid var(--base);padding-left:16px">rule:</span>
<span><span class="dot" style="background:var(--s-wait)"></span>armed</span>
<span><span class="dot" style="background:var(--s-done)"></span>fired</span></div></section>
<section id="ctxsec"><h2>Per-round context (ET §6) <small>— prompt size per agent per round; the crossover signature: planner grows with global state, RATD/stig stay local</small></h2>
<div id="ctxwrap"></div><div class="legend" id="ctxleg"></div></section>
<section id="geo"><h2>Data geography — memory planes K · W · G <small>— where every artifact lives at the cursor; K catalog index, W per-agent workspaces (open read), G linear-versioned global</small></h2>
<div class="planes"><div class="plane k" id="planeK"></div><div class="plane w" id="planeW"></div><div class="plane g" id="planeG"></div></div></section>
<section id="tl"><h2>Swimlanes <small>— one lane per agent over the event axis; ticks are writes (W○ / G●); the line is the cursor; handoffs are dashed arcs</small></h2>
<div id="lanes"></div></section>
<section id="circuit"><h2>Circuit — rule table <small>— condition &phi; → target &sigma;; click a row to jump &amp; highlight its wiring; gold bar = edited by a non-author</small></h2><div id="ctable"></div></section>
<section id="handoff"><h2>Handoffs <small>— cross-agent reads: the reads-are-grants delivery channels (writer &rarr; reader via a memory path)</small></h2><div id="htable"></div></section>
<section id="traj"><h2>Trajectory <small>— click a row to seek the replay</small></h2>
<input type="search" id="tsearch" placeholder="search events…"><div class="filters" id="tfilters"></div><div id="ttable" style="max-height:480px;overflow:auto"></div></section>
<section id="mem"><h2>Global memory D <small id="memcount"></small></h2><input type="search" id="msearch" placeholder="filter paths…"><div id="mlist"></div></section>

<div id="ttip"></div>
<script>const DATA = __DATA__;
const $=q=>document.querySelector(q), esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const EV=DATA.events, N=Math.max(EV.length,1), LAST=N-1;
document.title=DATA.run; $("#ttl").textContent="Run: "+DATA.run;
const AG=DATA.agents || [], byId={}; AG.forEach(a=>byId[a.id]=a);
const RULES=DATA.rules || []; const ruleById={}; RULES.forEach(r=>ruleById[r.id]=r);
const h=DATA.health||{}, m=DATA.metrics||{}, chips=[];
if(DATA.arm_label) chips.push(`<span class="chip arm">${esc(DATA.arm_label)}</span>`);
if(DATA.task_id) chips.push(`<span class="chip">task ${esc(DATA.task_id)}</span>`);
if("converged" in m) chips.push(`<span class="chip ${m.converged?"ok":"bad"}">${m.converged?"converged":"NOT converged"}</span>`);
if(h.systemic_failure!==undefined) chips.push(`<span class="chip ${h.systemic_failure?"bad":"ok"}">${h.systemic_failure?"SYSTEMIC FAILURE":"healthy"}</span>`);
if(h.quiescent!==undefined) chips.push(`<span class="chip ${h.quiescent?"ok":"bad"}">${h.quiescent?"quiescent":"not quiescent"}</span>`);
if(h.rail_hit) chips.push(`<span class="chip bad">rail: ${esc(h.rail_hit)}</span>`);
for(const [k,lab] of [["n_agents","agents"],["llm_calls","LLM calls"],["total_tokens","tokens"],["n_rules","rules"],["rules_fired","fired"],["global_artifacts","G artifacts"]]) if(m[k]!==undefined) chips.push(`<span class="chip">${lab}: ${(m[k]||0).toLocaleString()}</span>`);
if(m.divergent_artifacts) chips.push(`<span class="chip bad">divergent: ${m.divergent_artifacts}</span>`);
if(m.rule_edits_by_nonauthor) chips.push(`<span class="chip bad">non-author edits: ${m.rule_edits_by_nonauthor}</span>`);
if(m.wall_clock_s!==undefined) chips.push(`<span class="chip">${m.wall_clock_s}s</span>`);
if(DATA.dead_rules) chips.push(`<span class="chip bad">dead rules: ${DATA.dead_rules}</span>`);
for(const k of ["llm_calls","max_depth","agent_count","defer_count","planner_calls","termination"]) if(m[k]!==undefined) chips.push(`<span class="chip">${k}: ${esc(m[k])}</span>`);
$("#chips").innerHTML=chips.join(" ");
$("#tasktext").innerHTML=`<b class="mono" style="color:var(--ink2)">${esc(DATA.model||"")}</b> — ${esc(DATA.task_text||"")}`;
const STARVED=new Set(h.waiting_at_end||[]);
// ---------- replay engine ----------
function replay(upto){
  const st={}, round={}, writes={}, mem=new Set(), rs={};
  RULES.forEach(r=>rs[r.id]="pending");
  for(let i=0;i<=upto&&i<N;i++){const e=EV[i];
    switch(e.y){
      case "spawn": st[e.a]="spawned"; break;
      case "lifecycle": if(e.a in st||true) st[e.a]=e.to; break;
      case "llm_call": case "tool_call": if(e.a&&(e.r||0)>(round[e.a]||0))round[e.a]=e.r; break;
      case "write": case "ws_write": case "g_commit": if(e.p){mem.add(e.p);(writes[e.a]??=[]).push(e.p);} break;
      case "rule_add": if(e.rid)rs[e.rid]="armed"; break;
      case "rule_fired": if(e.rid)rs[e.rid]="fired"; break;
      case "rule_disable": if(e.rid)rs[e.rid]="disabled"; break;
    }
  }
  if(upto>=LAST){for(const id of STARVED) if(st[id]==="waiting")st[id]="starved";}
  return {st,round,writes,mem,rs};
}

const x=i=>LPAD+(i/Math.max(LAST,1))*(XW-LPAD-20);
let lsvg=`<svg id="lanesvg" width="${XW}" height="${LSVGH}" xmlns="http://www.w3.org/2000/svg">`;
laneOrder.forEach((id,r)=>{const y=8+r*LH;
 lsvg+=`<text class="axis lanelabel" data-id="${esc(id)}" x="8" y="${y+11}">${esc(id)}</text>`;
 (segs[id]||[]).forEach(s=>{const w=Math.max(x(s.b)-x(s.a),2), fill=SC[s.s]||"#52514e";
const laneOrder=AG.map(a=>a.id);
const segsFor=()=>{ // recompute lifecycle segments across events
 const segs={}, open={}, st={};
 const push=(id,i)=>{if(open[id])(segs[id]??=[]).push({s:open[id].state,a:open[id].from,b:i});};
 const set=(id,v,i)=>{if(st[id]===v)return; push(id,i); open[id]={state:v,from:i}; st[id]=v;};
 EV.forEach((e,i)=>{if(e.y==="spawn")set(e.a,"spawned",i); else if(e.y==="lifecycle")set(e.a,e.to,i);});
 for(const id in open){let s=open[id].state; if(s==="waiting"&&STARVED.has(id))s="starved"; (segs[id]??=[]).push({s,a:open[id].from,b:LAST});}
 return segs;};
const segs=segsFor();
const LH=24,LPAD=150,XW=Math.max(1200,N*7),LSVGH=laneOrder.length*LH+34;
const SC={running:"#3987e5",done:"#0ca30c",waiting:"#fab219",spawned:"#52514e",failed:"#d03b3b",terminated:"#8a4a4a",starved:"#d03b3b"};
const x=i=>LPAD+(i/Math.max(LAST,1))*(XW-LPAD-20);
let lsvg=`<svg id="lanesvg" width="${XW}" height="${LSVGH}" xmlns="http://www.w3.org/2000/svg">`;
laneOrder.forEach((id,r)=>{const y=8+r*LH;
 lsvg+=`<text class="axis lanelabel" data-id="${esc(id)}" x="8" y="${y+11}">${esc(id)}</text>`;
 (segs[id]||[]).forEach(s=>{const w=Math.max(x(s.b)-x(s.a),2), fill=SC[s.s]||"#52514e";
  lsvg+=`<rect data-tip="<b>${esc(id)}</b> ${s.s} — e${s.a}→e${s.b}" x="${x(s.a)}" y="${y}" width="${w}" height="13" rx="3" fill="${s.s==="spawned"?"transparent":fill}" ${s.s==="spawned"?`stroke="#898781" stroke-dasharray="4 3"`:s.s==="waiting"?`stroke="#c98500"`:""}/>`;
  if(s.s==="starved") lsvg+=`<text x="${x(s.b)-10}" y="${y+11}" fill="#d03b3b" font-size="11">&#10007;</text>`;});
});
// handoff arcs (writer -> reader)
DATA.handoffs.forEach(hf=>{const r1=laneOrder.indexOf(hf.writer),r2=laneOrder.indexOf(hf.reader); if(r1<0||r2<0)return;
 const y1=8+r1*LH+6.5,y2=8+r2*LH+6.5,xx=x(hf.i);
 lsvg+=`<path data-tip="handoff: <b>${esc(hf.writer)}</b> → <b>${esc(hf.reader)}</b><br>${esc(hf.path)} (${hf.chars.toLocaleString()} chars)" d="M${xx},${y1} Q${xx+14},${(y1+y2)/2} ${xx},${y2}" fill="none" stroke="#e0952b" stroke-width="1.2" opacity=".55"/>`;});
EV.forEach(e=>{if((e.y==="ws_write"||e.y==="g_commit")&&e.a){const r=laneOrder.indexOf(e.a); if(r<0)return;
 const g=e.y==="g_commit";
 lsvg+=`<circle data-tip="<b>${esc(e.a)}</b> ${g?"committed":"wrote"} <b>${esc(e.p)}</b>${g?" v"+e.ver:""} at e${e.i}" cx="${x(e.i)}" cy="${8+r*LH+6.5}" r="3.2" fill="${g?"#5fbf8f":"#fff"}" stroke="${g?"#0ca30c":"#c99be0"}" stroke-width="1.5"/>`;}});
lsvg+=`<line id="cursor1" y1="0" y2="${LSVGH}" stroke="#fff" stroke-width="1.4" opacity=".85"/>`;
lsvg+=`</svg>`; $("#lanes").innerHTML=lsvg;
document.querySelectorAll(".lanelabel").forEach(t=>t.addEventListener("click",()=>window._selAgent(t.dataset.id)));

function paint(){
 $("#scrub").value=CUR; const e=EV[CUR]||{t:0,y:"—",x:"empty trace"};
 $("#eclock").textContent=`event ${CUR}/${LAST} · t+${e.t}s`;
 $("#evcard").innerHTML=`<b>e${CUR} · ${esc(e.y)}</b> — ${esc(e.x)}`;
 $("#evcard").style.borderLeftColor=TDOT[e.y]||"#3987e5";
 paintGraph(); if(SEL)showSel(); inspect();
 const cx=x(CUR); $("#cursor1")?.setAttribute("x1",cx); $("#cursor1")?.setAttribute("x2",cx);
 // context cursor: place at the current agent/round x if available
 if(e.a&&DATA.per_round[e.a]&&window._CCX){const rr=e.r||(DATA.per_round[e.a][0]||{}).round||1;const cxx=window._CCX(rr);$("#ctxcursor")?.setAttribute("x1",cxx);$("#ctxcursor")?.setAttribute("x2",cxx);}
 $("#ctable").innerHTML=circuitHTML(CUR);
 document.querySelectorAll("#ctable tr[data-rule]").forEach(r=>r.addEventListener("click",()=>window._selRule(r.dataset.rule)));
 $("#htable").innerHTML=handoffHTML(CUR);
 document.querySelectorAll("#htable tr[data-seek]").forEach(r=>r.addEventListener("click",()=>seek(+r.dataset.seek)));
 geoHTML(CUR);
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
// shared tooltip + click-to-seek on chart dots
const tip=$("#ttip");
document.addEventListener("mousemove",e=>{const t=e.target.closest("[data-tip]");
 if(t){tip.style.display="block";tip.innerHTML=t.dataset.tip;tip.style.left=Math.min(e.clientX+14,window.innerWidth-440)+"px";tip.style.top=(e.clientY+14)+"px";}
 else tip.style.display="none";});
document.addEventListener("click",e=>{const t=e.target.closest("[data-seek]"); if(t&&t.dataset.seek!==undefined&&t.closest("#ctxsvg"))seek(+t.dataset.seek);});
if(location.hash.match(/^#e\d+$/)) CUR=Math.min(LAST,+location.hash.slice(2));
renderGraph();

paint();
</script></body></html>"""


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python3 -m src.visualize <run_dir> [out.html]")
        return 2

    run_dir = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else run_dir / "view.html"
    data = build_data(run_dir)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(PAGE.replace("__TITLE__", data["run"]).replace("__DATA__", payload), encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
