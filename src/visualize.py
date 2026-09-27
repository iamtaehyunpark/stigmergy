"""Interactive run-replay visualizer (v2 / ET series).

    python3 -m src.visualize <run_dir> [out.html]

One self-contained dark HTML page per run (inline CSS/JS, no network) that
replays a RATD v2 run event by event. Rebuilt for the v2 substrate: multi-round
ReAct agents, the K/W/G memory planes, and the expression-condition circuit.
Reads the v2 run directory: trace.jsonl + state.json + metrics.json +
run_meta.json (Arms P / R / S).

Two things are foregrounded, per the v2 rebuild:

- THE CIRCUIT — rules are (φ, σ, provenance): a Python boolean expression over
  state accessors, a target (spawn a new agent / resume a waiting one), and an
  author. Because a condition references artifacts (`exists("global/x.md")`) and
  agents (`state("a1")`), a rule wires *artifact-author → woken-agent*: that edge
  IS stigmergy. The circuit graph draws the spawn tree solid and the rule wiring
  (wake = agent-gated, stig = artifact-gated) as a togglable overlay; the rule
  table shows every φ, its truth/fate at the cursor, and edits by non-authors.

- THE DATA GEOGRAPHY — where every artifact lives across the three planes:
  K (catalog index), W (per-agent workspaces, open-read), G (linear-versioned
  global with divergence flags). Cross-agent reads are surfaced as handoffs —
  the reads-are-grants delivery channels the theory turns on.

Plus the central ET measurement (§6): per-round prompt size per agent — the
crossover signature (Arm P grows with global state; Arms R/S stay local).

State colors are status roles; edge kinds are categorical slots with dash
patterns as secondary encoding.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# --- v2 condition parsing: pull the state sources a rule's expression touches.
# The namespace is fixed (Playground Spec v2 §3): only these read-only accessors
# are referenceable, so a regex over the frozen accessor set is exact enough to
# recover a rule's wiring for display.
RE_AGENT = re.compile(r"(?:state|children)\(\s*[\"']([^\"']+)[\"']")
RE_FIRED = re.compile(r"fired\(\s*[\"']([^\"']+)[\"']")
RE_PATH = re.compile(r"(?:exists|head|field|history|matching|count)\(\s*[\"']([^\"']+)[\"']")

ARM_LABEL = {"r": "RATD · multi-round", "p": "Planner · centralized",
             "s": "Stigmergic · single-shot"}


def agent_refs(cond: str) -> list[str]:
    return sorted(set(RE_AGENT.findall(cond or "")))


def path_refs(cond: str) -> list[str]:
    return sorted(set(RE_PATH.findall(cond or "")))


def rule_refs(cond: str) -> list[str]:
    return sorted(set(RE_FIRED.findall(cond or "")))


def target_str(tgt: dict) -> str:
    if not isinstance(tgt, dict):
        return str(tgt)
    if tgt.get("type") == "resume":
        return f"resume {tgt.get('agent_id')}"
    if tgt.get("type") == "spawn":
        return f"spawn: {str(tgt.get('task', ''))[:60]}"
    return json.dumps(tgt)[:80]


def summarize(e: dict) -> str:
    t = e.get("event")
    a = e.get("agent")
    if t == "run_start":
        return f"run start — arm {e.get('arm')} — task {e.get('task_id')}"
    if t == "spawn":
        via = f" (via rule {e['rule']})" if e.get("rule") else ""
        return f"{e.get('parent') or '—'} spawned {a}{via} — {str(e.get('task', ''))[:70]}"
    if t == "lifecycle":
        return f"{a}: {e.get('from')} → {e.get('to')}  ({str(e.get('reason', ''))[:60]})"
    if t == "llm_call":
        return f"{a} round {e.get('round')} — LLM call #{e.get('call_no')} — prompt {e.get('prompt_chars', 0):,} chars (window {e.get('window')})"
    if t == "llm_reply":
        cut = " [CUT at token cap]" if e.get("finish_reason") == "length" else ""
        return f"{a} replied — {e.get('completion_tokens', 0):,} tok, {e.get('chars', 0):,} chars{cut}"
    if t == "tool_call":
        err = " ERROR" if e.get("error") else ""
        tr = " [TRUNC]" if e.get("truncated_return") else ""
        return f"{a} · {e.get('tool')}{err} → {e.get('result_chars', 0):,} chars{tr}"
    if t == "parse_errors":
        return f"{a} round {e.get('round')} — {len(e.get('errors', []))} parse error(s), {e.get('n_calls_parsed')} calls parsed"
    if t == "ws_write":
        x = " [CROSS-WORKSPACE]" if e.get("cross_workspace") else ""
        return f"{a} wrote W:{e.get('path')} ({e.get('chars', 0):,} chars){x}"
    if t == "cross_workspace_write":
        return f"{a} wrote into {e.get('owner')}'s workspace: {e.get('path')}"
    if t == "g_commit":
        d = " [DIVERGENT]" if e.get("divergent") else ""
        return f"{a} committed G:{e.get('path')} v{e.get('version')} ({e.get('chars', 0):,} chars){d}"
    if t == "divergence_flagged":
        return f"DIVERGENCE: {e.get('path')} (over {e.get('head_author')}'s head)"
    if t == "rule_add":
        r = e.get("rule", {})
        via = f" via {e['via']}" if e.get("via") else ""
        return f"circuit += [{r.get('id')}]{via} : when {str(r.get('condition', ''))[:60]} → {target_str(r.get('target', {}))}"
    if t == "rule_update":
        return f"{a} edited rule {e.get('rule_id')} ({', '.join(e.get('changed', []))})"
    if t == "rule_disable":
        return f"{a} disabled rule {e.get('rule_id')}"
    if t == "rule_fired":
        return f"rule [{e.get('rule_id')}] FIRED → {target_str(e.get('target', {}))}"
    if t == "rule_eval_error":
        return f"rule [{e.get('rule_id')}] eval error: {str(e.get('error', ''))[:60]}"
    if t == "rule_target_invalid":
        return f"rule [{e.get('rule_id')}] target invalid (agent {e.get('agent_state')})"
    if t == "window_truncated":
        return f"{a}: rolling window truncated"
    if t == "agent_round_rail":
        return f"{a}: hit R_max round rail"
    if t == "rail_hit":
        return f"RAIL HIT: {e.get('rail')}"
    if t in ("implicit_done_readonly", "implicit_continue"):
        return f"{a}: {t.replace('_', ' ')}"
    if t == "health_verdict":
        return f"health: {'QUIESCENT' if e.get('quiescent') else 'not quiescent'}, root {e.get('root_state')}, {'SYSTEMIC FAILURE' if e.get('systemic_failure') else 'ok'}"
    if t == "run_end":
        return f"run end — {e.get('llm_calls')} calls, {e.get('total_tokens', 0):,} tokens, {e.get('wall_clock_s')}s"
    return json.dumps({k: v for k, v in e.items() if k not in ("ts", "seq")}, ensure_ascii=False)[:200]


def build_data(run_dir: Path) -> dict:
    raw = []
    trace = run_dir / "trace.jsonl"
    if trace.exists():
        raw = [json.loads(l) for l in trace.read_text(encoding="utf-8").splitlines() if l.strip()]
    t0 = raw[0]["ts"] if raw else 0

    def load(name):
        p = run_dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    state = load("state.json")
    metrics = load("metrics.json")
    meta = load("run_meta.json")

    agents_state = state.get("agents", {})
    workspaces = state.get("workspaces", {})
    glob = state.get("global", {})
    rules_state = state.get("rules", {})

    # ---- rule scaffolding ----
    rules = {}
    for rid, r in rules_state.items():
        cond = r.get("condition", "")
        rules[rid] = {
            "id": rid, "condition": cond, "target": r.get("target", {}),
            "author": r.get("author"), "author_round": r.get("author_round"),
            "fired": bool(r.get("fired")), "fired_count": r.get("fired_count", 0),
            "enabled": r.get("enabled", True), "edits": r.get("edits", []),
            "refs_agents": agent_refs(cond), "refs_paths": path_refs(cond),
            "refs_rules": rule_refs(cond),
            "added_at": None, "fired_at": None, "disabled_at": None,
        }

    # rule -> child spawned by it (target spawn resolution)
    rule_child: dict[str, str] = {}

    # ---- walk events ----
    events = []
    last_writer: dict[str, str] = {}
    per_round: dict[str, list] = {}   # agent -> [{round, chars, i}]
    handoffs = []
    catalog_calls = 0

    for i, e in enumerate(raw):
        t = e.get("event")
        a = e.get("agent")
        rec = {"i": i, "s": e.get("seq"), "t": round(e.get("ts", 0) - t0, 1),
               "y": t, "a": a, "r": e.get("round"), "x": summarize(e)}

        if t == "spawn":
            rec["parent"] = e.get("parent")
            rec["via"] = e.get("rule")
            rec["ctask"] = str(e.get("task", ""))
            if e.get("rule"):
                rule_child[e["rule"]] = a
        elif t == "lifecycle":
            rec["fr"] = e.get("from")
            rec["to"] = e.get("to")
            rec["reason"] = str(e.get("reason", ""))
        elif t == "llm_call":
            rec["pc"] = e.get("prompt_chars")
            rec["win"] = e.get("window")
            per_round.setdefault(a, []).append(
                {"round": e.get("round"), "chars": e.get("prompt_chars", 0), "i": i})
        elif t == "llm_reply":
            rec["tx"] = e.get("text", "")
            rec["fin"] = e.get("finish_reason")
            rec["ct"] = e.get("completion_tokens")
            rec["pt"] = e.get("prompt_tokens")
        elif t == "tool_call":
            tool = e.get("tool")
            rec["tool"] = tool
            rec["args"] = e.get("args")
            rec["res"] = e.get("result", "")
            rec["err"] = bool(e.get("error"))
            rec["trunc"] = bool(e.get("truncated_return"))
            if tool in ("catalog.search", "catalog.inspect"):
                catalog_calls += 1
            if tool in ("workspace.read", "global.read") and not e.get("error"):
                p = (e.get("args") or {}).get("path")
                w = last_writer.get(p)
                if w and w != a:
                    hf = {"i": i, "reader": a, "path": p, "writer": w,
                          "chars": e.get("result_chars", 0), "round": e.get("round")}
                    handoffs.append(hf)
                    rec["hf"] = hf
        elif t in ("ws_write", "g_commit"):
            p = e.get("path")
            rec["p"] = p
            rec["ch"] = e.get("chars")
            if t == "g_commit":
                rec["ver"] = e.get("version")
                rec["div"] = bool(e.get("divergent"))
            else:
                rec["cross"] = bool(e.get("cross_workspace"))
            if a:
                last_writer[p] = a
        elif t == "rule_add":
            r = e.get("rule", {})
            rid = r.get("id")
            rec["rid"] = rid
            rec["via"] = e.get("via")
            if rid in rules and rules[rid]["added_at"] is None:
                rules[rid]["added_at"] = i
        elif t == "rule_fired":
            rid = e.get("rule_id")
            rec["rid"] = rid
            if rid in rules:
                rules[rid]["fired_at"] = i
        elif t in ("rule_update", "rule_disable"):
            rec["rid"] = e.get("rule_id")
            rec["changed"] = e.get("changed", [])
            if t == "rule_disable" and e.get("rule_id") in rules:
                rules[e["rule_id"]]["disabled_at"] = i
        elif t == "run_start":
            rec["task_text"] = e.get("task", "")
        events.append(rec)

    # ---- agents (final state + provenance) ----
    born = {}
    for i, e in enumerate(raw):
        if e.get("event") == "spawn" and e.get("agent") not in born:
            born[e["agent"]] = i
    agents = []
    pa = metrics.get("per_agent", {})
    for aid, a in agents_state.items():
        m = pa.get(aid, {})
        agents.append({
            "id": aid, "role": a.get("role"), "parent": a.get("parent"),
            "state": a.get("state"), "rounds": a.get("rounds", m.get("rounds", 0)),
            "task": a.get("task", ""), "capsule": a.get("capsule", ""),
            "initial_refs": a.get("initial_refs", []),
            "spawned_by_rule": a.get("spawned_by_rule"),
            "done_summary": a.get("done_summary"), "fail_reason": a.get("fail_reason"),
            "born": born.get(aid, 0),
            "prompt_tokens": m.get("prompt_tokens", 0),
            "completion_tokens": m.get("completion_tokens", 0),
            "chars_per_round": m.get("prompt_chars_per_round", []),
        })

    # ---- data geography: planes (computed first; the graph reads them) ----
    ws_out = {}
    for p, w in workspaces.items():
        ws_out[p] = {"owner": p.split("/")[1] if "/" in p else "?",
                     "author": w.get("author"), "chars": len(str(w.get("content", ""))),
                     "writes": w.get("writes", 1), "content": w.get("content", "")}
    g_out = {}
    for p, art in glob.items():
        g_out[p] = {"head": art.get("head"), "divergent": bool(art.get("divergent")),
                    "versions": [{"version": v.get("version"), "author": v.get("author"),
                                  "round": v.get("round"), "summary": v.get("summary", ""),
                                  "chars": len(str(v.get("content", ""))),
                                  "content": v.get("content", "")}
                                 for v in art.get("versions", [])]}

    # ---- the circuit as a tripartite graph: agents · rules · artifacts ----
    # The old model collapsed rules into agent→agent edges, which erased the
    # rules themselves (a `True` self-resume has no agent/artifact refs, so it
    # vanished entirely) and hid the stigmergic medium. This model keeps all
    # three node kinds so the whole loop is visible:
    #   agent --write--> artifact --gate--> rule --fire--> agent   (stigmergy)
    #   agent --write--> artifact --read--> agent                  (handoff)
    #   agent --spawn--> agent                                     (spawn tree)
    #   agent --authors--> rule --resume--> same agent             (self-revive)
    aset = set(agents_state.keys())

    first_write: dict[str, int] = {}
    writers_of: dict[str, list] = {}
    for ev in events:
        if ev["y"] in ("ws_write", "g_commit") and ev.get("p"):
            p = ev["p"]
            first_write.setdefault(p, ev["i"])
            writers_of.setdefault(p, [])
            if ev["a"] and ev["a"] not in writers_of[p]:
                writers_of[p].append(ev["a"])

    def plane_of(p: str) -> str:
        if p.startswith("agents/"):
            return "W"
        return "G"

    def rule_rank(r: dict) -> int:
        for v in (r["added_at"], r["fired_at"]):
            if v is not None:
                return v
        return born.get(r["author"], 0)

    # circuit-relevant artifacts: everything shared (G), everything a rule reads,
    # everything read across agents (handoffs). Private scratch stays in the
    # geography panel — it isn't part of the coordination circuit.
    art_paths = set(g_out.keys())
    for r in rules.values():
        art_paths.update(r["refs_paths"])
    for hf in handoffs:
        art_paths.add(hf["path"])

    def art_rank(p: str) -> int:
        if p in first_write:
            return first_write[p]
        refs = [rule_rank(r) for r in rules.values() if p in r["refs_paths"]]
        return min(refs) if refs else 0

    A, R, MP = "A:", "R:", "M:"
    gnodes = []
    for a in agents:
        gnodes.append({"nid": A + a["id"], "kind": "agent", "ref": a["id"],
                       "rank": a["born"], "role": a["role"],
                       "label": a["id"], "sub": (a["task"] or "")[:22]})
    for r in rules.values():
        tgt = r["target"]
        trivial = ((r["condition"] or "").strip() in ("True", "")
                   and tgt.get("type") == "resume" and tgt.get("agent_id") == r["author"])
        gnodes.append({"nid": R + r["id"], "kind": "rule", "ref": r["id"],
                       "rank": rule_rank(r), "label": r["id"],
                       "sub": (r["condition"] or "")[:26], "author": r["author"],
                       "trivial": trivial})
    for p in sorted(art_paths):
        gnodes.append({"nid": MP + p, "kind": "artifact", "ref": p,
                       "rank": art_rank(p), "plane": plane_of(p),
                       "written": p in first_write,
                       "divergent": bool(g_out.get(p, {}).get("divergent")),
                       "chars": (g_out[p]["versions"][-1]["chars"] if p in g_out and g_out[p]["versions"]
                                 else ws_out.get(p, {}).get("chars", 0)),
                       "label": p.split("/")[-1], "sub": p})

    nidset = {n["nid"] for n in gnodes}
    gedges = []
    seen_e = set()

    def add_e(f, t, kind, at, rule=None):
        if f == t or (f, t, kind) in seen_e:
            return
        seen_e.add((f, t, kind))
        gedges.append({"from": f, "to": t, "kind": kind,
                       "at": at if at is not None else 0, "rule": rule})

    for a in agents:
        if a["parent"] and a["parent"] in aset:
            add_e(A + a["parent"], A + a["id"], "spawn", a["born"])
    for rid, r in rules.items():
        rr = rule_rank(r)
        add_e(A + r["author"], R + rid, "authors", rr, rule=rid)
        tgt = r["target"]
        to = tgt.get("agent_id") if tgt.get("type") == "resume" else rule_child.get(rid)
        if to and to in aset:
            add_e(R + rid, A + to, "fire", r["fired_at"] if r["fired"] else rr, rule=rid)
        for g in r["refs_agents"]:
            if g in aset:
                add_e(A + g, R + rid, "state", rr, rule=rid)
        for fr in r["refs_rules"]:
            if fr in rules:
                add_e(R + fr, R + rid, "state", rr, rule=rid)
        for p in r["refs_paths"]:
            if MP + p in nidset:
                add_e(MP + p, R + rid, "gate", rr, rule=rid)
    for ev in events:
        if ev["y"] in ("ws_write", "g_commit") and ev.get("p") and (MP + ev["p"]) in nidset and ev["a"]:
            add_e(A + ev["a"], MP + ev["p"], "write", ev["i"])
    for hf in handoffs:
        if (MP + hf["path"]) in nidset:
            add_e(MP + hf["path"], A + hf["reader"], "read", hf["i"])

    graph = {"nodes": gnodes, "edges": gedges}

    return {
        "run": run_dir.name,
        "arm": metrics.get("arm") or meta.get("arm"),
        "arm_label": ARM_LABEL.get(metrics.get("arm") or meta.get("arm"), ""),
        "task_id": metrics.get("task_id"),
        "task_text": (meta.get("task") or {}).get("task", "") or (raw[0].get("task") if raw else ""),
        "model": meta.get("model"), "rails": meta.get("rails", {}),
        "metrics": metrics, "health": metrics.get("health", {}),
        "agents": agents, "graph": graph, "rules": list(rules.values()),
        "events": events, "handoffs": handoffs, "per_round": per_round,
        "workspaces": ws_out, "global": g_out,
        "catalog_calls": catalog_calls,
    }


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title><style>
:root{--page:#0d0d0d;--card:#1a1a19;--card2:#232322;--ink:#fff;--ink2:#c3c2b7;--mut:#898781;--grid:#2c2c2a;--base:#383835;--ring:rgba(255,255,255,.1);
--e-spawn:#3987e5;--e-wake:#9085e9;--e-stig:#e0952b;--s-run:#3987e5;--s-done:#0ca30c;--s-wait:#fab219;--s-fail:#d03b3b;--s-spawned:#6f6d67;--plane-k:#5aa9c9;--plane-w:#c99be0;--plane-g:#5fbf8f}
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
<div id="ttip"></div>
<script>const DATA = __DATA__;
const $=q=>document.querySelector(q), esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const EV=DATA.events, N=Math.max(EV.length,1), LAST=N-1;
document.title=DATA.run; $("#ttl").textContent="Run: "+DATA.run;
const AG=DATA.agents, byId={}; AG.forEach(a=>byId[a.id]=a);
const RULES=DATA.rules, ruleById={}; RULES.forEach(r=>ruleById[r.id]=r);
const h=DATA.health||{}, m=DATA.metrics||{}, chips=[];
if(DATA.arm_label) chips.push(`<span class="chip arm">${esc(DATA.arm_label)}</span>`);
if(DATA.task_id) chips.push(`<span class="chip">task ${esc(DATA.task_id)}</span>`);
chips.push(`<span class="chip ${h.systemic_failure?"bad":"ok"}">${h.systemic_failure?"SYSTEMIC FAILURE":"healthy"}</span>`);
if(h.quiescent!==undefined) chips.push(`<span class="chip ${h.quiescent?"ok":"bad"}">${h.quiescent?"quiescent":"not quiescent"}</span>`);
if(h.rail_hit) chips.push(`<span class="chip bad">rail: ${esc(h.rail_hit)}</span>`);
for(const [k,lab] of [["n_agents","agents"],["llm_calls","LLM calls"],["total_tokens","tokens"],["n_rules","rules"],["rules_fired","fired"],["global_artifacts","G artifacts"]]) if(m[k]!==undefined) chips.push(`<span class="chip">${lab}: ${(m[k]||0).toLocaleString()}</span>`);
if(m.divergent_artifacts) chips.push(`<span class="chip bad">divergent: ${m.divergent_artifacts}</span>`);
if(m.rule_edits_by_nonauthor) chips.push(`<span class="chip bad">non-author edits: ${m.rule_edits_by_nonauthor}</span>`);
if(m.wall_clock_s!==undefined) chips.push(`<span class="chip">${m.wall_clock_s}s</span>`);
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
    }
    if((e.y==="ws_write"||e.y==="g_commit")&&e.p){mem.add(e.p);(writes[e.a]??=[]).push(e.p);}
    if(e.y==="rule_add"&&e.rid)rs[e.rid]="armed";
    if(e.y==="rule_fired"&&e.rid)rs[e.rid]="fired";
    if(e.y==="rule_disable"&&e.rid)rs[e.rid]="disabled";
  }
  if(upto>=LAST){for(const id of STARVED) if(st[id]==="waiting")st[id]="starved";}
  return {st,round,writes,mem,rs};
}
// ---------- tripartite circuit graph ----------
const GN=DATA.graph.nodes, GE=DATA.graph.edges, gById={}; GN.forEach(n=>gById[n.nid]=n);
const DIM={agent:{w:196,h:54},rule:{w:186,h:46},artifact:{w:186,h:34}};
const EMK=["spawn","write","read","gate","state","fire","authors"];
const EMC={spawn:"#3987e5",write:"#c99be0",read:"#5fbf8f",gate:"#e0952b",state:"#9085e9",fire:"#9085e9",authors:"#4a4844"};
// edges that impose left→right causal order (used to assign columns); the rest
// (fire, read) are feedback/handoff and are drawn but not used for ranking.
const FWD=new Set(["spawn","write","gate","authors","state"]);
let SEL=null, SELRULE=null, curNodes=[], curEdges=[];
function firstWriteIdx(path){for(const e of EV)if((e.y==="ws_write"||e.y==="g_commit")&&e.p===path)return e.i; return null;}
// Layered (Sugiyama-lite) layout: columns = causal depth, barycenter ordering
// within each column to pull connected nodes level with each other and cut
// crossings. Generous spacing — the canvas is big, so use it.
function layout(nodes,edges){
 const idset=new Set(nodes.map(n=>n.nid));
 const fwd=edges.filter(e=>FWD.has(e.kind)&&idset.has(e.from)&&idset.has(e.to));
 const inF={},outF={}; nodes.forEach(n=>{inF[n.nid]=[];outF[n.nid]=[];});
 fwd.forEach(e=>{outF[e.from].push(e.to);inF[e.to].push(e.from);});
 const layer={}; nodes.forEach(n=>layer[n.nid]=0);
 let changed=true,guard=0;
 while(changed&&guard++<nodes.length+3){changed=false;
  fwd.forEach(e=>{if(layer[e.to]<layer[e.from]+1){layer[e.to]=layer[e.from]+1;changed=true;}});}
 const maxLayer=Math.max(0,...Object.values(layer));
 const byLayer={}; nodes.forEach(n=>{(byLayer[layer[n.nid]]??=[]).push(n);});
 Object.values(byLayer).forEach(arr=>arr.sort((a,b)=>(a.rank-b.rank)||String(a.label).localeCompare(String(b.label),undefined,{numeric:true})));
 // barycenter uses ALL connections (incl. fire/read feedback), so a rule is
 // pulled level with the agent it resumes and the artifact it gates on — that
 // alignment is what actually kills crossings, not the forward edges alone.
 const adj={}; nodes.forEach(n=>adj[n.nid]=[]);
 edges.forEach(e=>{if(idset.has(e.from)&&idset.has(e.to)){adj[e.from].push(e.to);adj[e.to].push(e.from);}});
 const oi={}, reindex=()=>{for(const L in byLayer)byLayer[L].forEach((n,i)=>oi[n.nid]=i);};
 reindex();
 for(let pass=0;pass<10;pass++){
  const Ls=Object.keys(byLayer).map(Number).sort((a,b)=>pass%2?b-a:a-b);
  Ls.forEach(L=>{byLayer[L].forEach(n=>{const idx=adj[n.nid].map(m=>oi[m]).filter(v=>v!=null);
     n._b=idx.length?idx.reduce((s,v)=>s+v,0)/idx.length:oi[n.nid];});
    byLayer[L].sort((a,b)=>(a._b-b._b)||(a.rank-b.rank)); reindex();});}
 const COLW=330,ROWH=82,PADX=44,PADY=40;
 const maxRows=Math.max(1,...Object.values(byLayer).map(a=>a.length));
 const H=PADY*2+maxRows*ROWH;
 Object.keys(byLayer).map(Number).forEach(L=>{const arr=byLayer[L],y0=PADY+(maxRows-arr.length)*ROWH/2;
  arr.forEach((n,i)=>{const d=DIM[n.kind]; n._w=d.w;n._h=d.h;n._x=PADX+L*COLW;
   n._y=y0+i*ROWH+(ROWH-d.h)/2;n._cx=n._x+d.w;n._lx=n._x;n._my=n._y+d.h/2;});});
 return {W:PADX*2+maxLayer*COLW+DIM.agent.w+40, H};}
function edgePath(e){const s=gById[e.from],t=gById[e.to]; if(!(s&&"_x"in s&&t&&"_x"in t))return"";
 if(t._x>s._x){const x1=s._cx,y1=s._my,x2=t._lx,y2=t._my,dx=Math.max(46,(x2-x1)*0.5);
  return `M${x1},${y1} C${x1+dx},${y1} ${x2-dx},${y2} ${x2},${y2}`;}
 // backward / same-column (feedback): leave the left side and loop back, bowing
 // vertically so return wires don't stack on the forward ones
 const x1=s._lx,y1=s._my,x2=t._cx,y2=t._my,dx=Math.max(60,(x1-x2)*0.28),bow=(y1<=y2?-1:1)*Math.max(30,Math.abs(y1-y2)*0.15);
 return `M${x1},${y1} C${x1-dx},${y1+bow} ${x2+dx},${y2+bow} ${x2},${y2}`;}
function nodeGlyph(n){const tf=`class="node CLS" data-nid="${esc(n.nid)}" transform="translate(${n._x},${n._y})"`;
 if(n.kind==="agent")return `<g ${tf.replace("CLS","gn-agent")}><rect width="${n._w}" height="${n._h}" rx="8"/><text x="12" y="21">${esc(n.label)}</text><text x="12" y="38" class="sub" data-sub>${esc(n.sub)}</text><text x="${n._w-10}" y="18" text-anchor="end" class="role">${esc(n.role||"")}</text></g>`;
 if(n.kind==="rule")return `<g ${tf.replace("CLS","gn-rule")}><rect width="${n._w}" height="${n._h}" rx="20"/><text x="15" y="19">&#9670; ${esc(n.label)}</text><text x="15" y="34" class="sub mono">${esc(n.sub)}</text></g>`;
 return `<g ${tf.replace("CLS","gn-art plane-"+n.plane)}><rect width="${n._w}" height="${n._h}" rx="16"/><text x="13" y="22">${n.plane==="G"?"&#9636;":"&#9634;"} ${esc(n.label)}</text></g>`;}
const NREVIVE=GN.filter(n=>n.kind==="rule"&&n.trivial).length;
$("#vcount").textContent=NREVIVE?`(${NREVIVE} hidden)`:"";
function renderGraph(){
 const showR=$("#togR").checked, showA=$("#togA").checked, showV=$("#togV").checked;
 const vis=GN.filter(n=>n.kind==="agent"||(n.kind==="rule"&&showR&&(!n.trivial||showV))||(n.kind==="artifact"&&showA));
 const visSet=new Set(vis.map(n=>n.nid));
 const allE=GE.filter(e=>visSet.has(e.from)&&visSet.has(e.to));
 const {W,H}=layout(vis,allE); curNodes=vis;
 // provenance (authors) edges guide layout but aren't drawn — they only add noise
 curEdges=allE.filter(e=>e.kind!=="authors");
 let s=`<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg"><defs>`;
 s+=EMK.map(k=>`<marker id="m-${k}" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z" fill="${EMC[k]}"/></marker>`).join("");
 s+=`</defs>`;
 curEdges.forEach((e,i)=>{const f=gById[e.from],t=gById[e.to];
  s+=`<path id="e${i}" class="edge ek-${e.kind}" d="${edgePath(e)}" marker-end="url(#m-${e.kind})"><title>${esc(e.kind)}${e.rule?" ["+esc(e.rule)+"]":""}: ${esc(f.label)} &#8594; ${esc(t.label)}</title></path>`;});
 s+=vis.map(nodeGlyph).join("")+"</svg>";
 $("#gsvg").innerHTML=s;
 document.querySelectorAll("#gsvg .node").forEach(g=>g.addEventListener("click",()=>nodeClick(g.dataset.nid)));
 paintGraph();}
$("#togR").addEventListener("change",renderGraph); $("#togA").addEventListener("change",renderGraph); $("#togV").addEventListener("change",renderGraph);
$("#gsvg").addEventListener("click",ev=>{if(!ev.target.closest(".node")&&(SEL||SELRULE)){SEL=null;SELRULE=null;paint();}});
function nodeClick(nid){const n=gById[nid]; if(!n)return; SEL=nid; SELRULE=(n.kind==="rule")?n.ref:null;
 if(n.kind==="rule"){const r=ruleById[n.ref]; seek(r.fired_at??r.added_at??CUR);}
 else if(n.kind==="artifact"){const w=firstWriteIdx(n.ref); if(w!=null)seek(w); else paint();}
 else paint();}
window._selRule=(rid)=>{SEL="R:"+rid;SELRULE=rid;const r=ruleById[rid];seek(r.fired_at??r.added_at??CUR);};
window._selAgent=(id)=>{SEL="A:"+id;SELRULE=null;paint();};
function showSel(){if(!SEL){return;} const n=gById[SEL]; if(!n){$("#detail").innerHTML="";return;}
 if(n.kind==="agent")return showAgent(n.ref);
 if(n.kind==="rule")return showRule(n.ref);
 return showArtifact(n.ref);}
function showAgent(id){const a=byId[id]; if(!a){$("#detail").innerHTML="";return;}
 const cur=replay(CUR), state=cur.st[id]??"(not yet spawned)", w=cur.writes[id]??[];
 const authored=RULES.filter(r=>r.author===id);
 const reads=DATA.handoffs.filter(hf=>hf.reader===id&&hf.i<=CUR);
 $("#detail").innerHTML=`<h3 style="margin:0 0 8px;color:var(--ink)">${esc(id)} <span class="chip">${esc(state)}</span> <span class="tag">${esc(a.role||"")}</span></h3>
 <p><b>task</b> ${esc(a.task)||"—"}</p>${a.capsule?`<p><b>capsule</b> ${esc(a.capsule)}</p>`:""}
 <p><b>parent</b> <span class="mono">${esc(a.parent??"— (root)")}</span>${a.spawned_by_rule?` <span class="tag">via ${esc(a.spawned_by_rule)}</span>`:""}</p>
 <p><b>rounds</b> ${a.rounds} · <b>tokens</b> ${(a.prompt_tokens+a.completion_tokens).toLocaleString()} (${a.prompt_tokens.toLocaleString()} in / ${a.completion_tokens.toLocaleString()} out)</p>
 ${a.initial_refs&&a.initial_refs.length?`<p><b>initial refs</b> <span class="mono">${a.initial_refs.map(esc).join("<br>")}</span></p>`:""}
 <p><b>writes so far</b> <span class="mono">${[...new Set(w)].map(esc).join("<br>")||"nothing yet"}</span></p>
 ${reads.length?`<p><b>reads (handoffs in)</b> <span class="mono">${reads.map(r=>esc(r.path)+" ←"+esc(r.writer)).join("<br>")}</span></p>`:""}
 ${authored.length?`<p><b>authored rules</b> ${authored.map(r=>`<span class="tag" style="cursor:pointer" onclick="window._selRule('${r.id}')">${esc(r.id)}</span>`).join("")}</p>`:""}
 ${a.done_summary?`<p><b>done</b> <span style="color:var(--mut)">${esc(a.done_summary.slice(0,400))}</span></p>`:""}
 ${a.fail_reason?`<p style="color:var(--s-fail)"><b>failed</b> ${esc(a.fail_reason)}</p>`:""}`;}
function showRule(rid){const r=ruleById[rid]; if(!r){$("#detail").innerHTML="";return;}
 const cur=replay(CUR), st=cur.rs[rid]||"pending";
 const nonAuthor=(r.edits||[]).filter(e=>e.by&&e.by!==r.author);
 $("#detail").innerHTML=`<h3 style="margin:0 0 8px;color:var(--ink)">&#9670; rule ${esc(rid)} <span class="chip">${esc(st)}</span></h3>
 <p><b>condition &phi;</b><br><span class="mono" style="color:var(--ink2)">${esc(r.condition)}</span></p>
 <p><b>target &sigma;</b> <span class="mono">${esc(target_str(r.target))}</span></p>
 <p><b>author</b> <span class="mono" style="cursor:pointer" onclick="window._selAgent('${esc(r.author)}')">${esc(r.author)}</span> · round ${r.author_round??"—"} · fired ×${r.fired_count||0}</p>
 <p><b>reads agents</b> <span class="mono">${(r.refs_agents||[]).join(", ")||"—"}</span></p>
 <p><b>reads artifacts</b> <span class="mono">${(r.refs_paths||[]).map(esc).join("<br>")||"—"}</span></p>
 <p><b>fate</b> ${r.added_at!=null?`authored @e${r.added_at}`:"authored (no add event — wait/continue sugar)"}${r.fired_at!=null?` · <span style="color:var(--s-done)">fired @e${r.fired_at}</span>`:(r.fired?" · fired":" · <span style='color:var(--s-fail)'>never fired</span>")}</p>
 ${nonAuthor.length?`<p style="color:var(--e-stig)"><b>&#9888; edited by non-authors</b><br>${nonAuthor.map(e=>`<span class="mono">${esc(e.by)} @r${e.round} (${(Object.keys(e.after||{}).filter(k=>JSON.stringify(e.after[k])!==JSON.stringify((e.before||{})[k]))).join(", ")||"edit"})</span>`).join("<br>")}</p>`:""}`;}
function showArtifact(path){const g=DATA.global[path], w=DATA.workspaces[path], cur=replay(CUR);
 const writers=[...new Set(EV.filter(e=>(e.y==="ws_write"||e.y==="g_commit")&&e.p===path).map(e=>e.a))];
 const readers=DATA.handoffs.filter(hf=>hf.path===path);
 const gaters=RULES.filter(r=>(r.refs_paths||[]).includes(path));
 const exists=cur.mem.has(path);
 let vers="";
 if(g){vers=`<p><b>versions</b> (linear, head v${g.head}${g.divergent?' <span class="tag err">DIVERGENT</span>':""})<br>${g.versions.map(v=>`<span class="mono">v${v.version} · ${esc(v.author)} r${v.round} · ${v.chars.toLocaleString()}ch</span>`).join("<br>")}</p>`;}
 $("#detail").innerHTML=`<h3 style="margin:0 0 8px;color:var(--ink)">${g?"&#9636;":"&#9634;"} ${esc(path.split("/").pop())} <span class="chip">${g?"G global":"W workspace"}</span>${exists?"":' <span class="tag">not yet written</span>'}</h3>
 <p class="mono" style="color:var(--mut);word-break:break-all">${esc(path)}</p>
 <p><b>written by</b> <span class="mono">${writers.map(esc).join(", ")||'<span style="color:var(--s-fail)">— never written (awaited)</span>'}</span></p>
 ${vers}
 <p><b>read by (handoffs)</b> <span class="mono">${readers.map(r=>esc(r.reader)+" ("+r.chars.toLocaleString()+"ch, e"+r.i+")").join("<br>")||"—"}</span></p>
 <p><b>gates rules</b> ${gaters.map(r=>`<span class="tag" style="cursor:pointer" onclick="window._selRule('${r.id}')">${esc(r.id)}</span>`).join("")||"—"}</p>`;}
// ---------- per-round context chart ----------
{const pr=DATA.per_round, ids=Object.keys(pr); const CC={};
 const palette=["#3987e5","#9085e9","#e0952b","#5fbf8f","#d03b3b","#5aa9c9","#c99be0","#fab219","#0ca30c","#e5679b"];
 ids.forEach((id,i)=>CC[id]=palette[i%palette.length]);
 const maxR=Math.max(1,...ids.map(id=>pr[id].length)), maxC=Math.max(1,...ids.flatMap(id=>pr[id].map(p=>p.chars)));
 const W=Math.max(720,maxR*46+120),H=300,PADL=64,PADB=28,PADT=12,PADR=16;
 const X=r=>PADL+(r-1)/Math.max(maxR-1,1)*(W-PADL-PADR), Y=c=>H-PADB-(c/maxC)*(H-PADB-PADT);
 let s=`<svg id="ctxsvg" width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">`;
 for(let g=0;g<=4;g++){const c=maxC*g/4,y=Y(c); s+=`<line x1="${PADL}" y1="${y}" x2="${W-PADR}" y2="${y}" stroke="#2c2c2a"/><text class="axis" x="8" y="${y+3}">${Math.round(c/1000)}k</text>`;}
 for(let r=1;r<=maxR;r++){if(maxR<=20||r%2===1)s+=`<text class="axis" x="${X(r)}" y="${H-10}" text-anchor="middle">${r}</text>`;}
 s+=`<text class="axis" x="${PADL}" y="${H-10}" text-anchor="end" style="fill:#6f6d67">round →</text>`;
 ids.forEach(id=>{const pts=pr[id].map(p=>`${X(p.round)},${Y(p.chars)}`).join(" ");
  s+=`<polyline points="${pts}" fill="none" stroke="${CC[id]}" stroke-width="2" opacity=".9"/>`;
  pr[id].forEach(p=>{s+=`<circle data-tip="<b>${esc(id)}</b> round ${p.round}: <b>${p.chars.toLocaleString()}</b> chars" data-seek="${p.i}" cx="${X(p.round)}" cy="${Y(p.chars)}" r="3" fill="${CC[id]}" style="cursor:pointer"/>`;});});
 s+=`<line id="ctxcursor" y1="${PADT}" y2="${H-PADB}" stroke="#fff" stroke-width="1.2" opacity=".7"/></svg>`;
 $("#ctxwrap").innerHTML=s;
 $("#ctxleg").innerHTML=ids.map(id=>`<span><span class="sw" style="border-color:${CC[id]}"></span>${esc(id)} <span style="color:var(--mut)">(${byId[id]?byId[id].role:""}, ${pr[id].length}r)</span></span>`).join("");
 window._CCX=X;}
// ---------- swimlanes ----------
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
// ---------- circuit table ----------
function circuitHTML(cur){if(!RULES.length)return `<p style="color:var(--mut)">No rules authored — this run's structure is entirely spawn-tree (no circuit wiring). Expected for a clean Arm P planner or a decomposition that needed no gating.</p>`;
 return `<table><tr><th>id</th><th>condition &phi;</th><th>target &sigma;</th><th>author</th><th>state at cursor</th></tr>`+RULES.map(t=>{
  const added=t.added_at!==null&&t.added_at<=cur, fired=t.fired_at!==null&&t.fired_at<=cur, disabled=t.disabled_at!==null&&t.disabled_at<=cur;
  const nonAuthor=(t.edits||[]).some(e=>e.by&&e.by!==t.author);
  let cls="r-pending",lab="not yet authored";
  if(disabled){cls="r-disabled";lab="disabled";}
  else if(fired){cls="r-fired";lab=`FIRED @e${t.fired_at}${t.fired_count>1?" ×"+t.fired_count:""}`;}
  else if(added&&cur>=LAST){cls="r-dead";lab="armed, never fired";}
  else if(added){cls="r-armed";lab="armed, waiting";}
  const tgt=t.target.type==="resume"?`resume ${esc(t.target.agent_id)}`:`spawn: ${esc(String(t.target.task||"").slice(0,42))}`;
  return `<tr class="${cls} ${nonAuthor?"r-nonauthor":""}" data-rule="${esc(t.id)}" style="cursor:pointer"><td class="mono">${esc(t.id)}</td><td class="mono" style="max-width:440px;overflow:hidden;text-overflow:ellipsis">${esc(t.condition)}</td><td class="mono">${tgt}</td><td>${esc(t.author)}${nonAuthor?' <span class="tag err">edited</span>':""}</td><td>${lab}</td></tr>`;}).join("")+`</table>`;}
// ---------- handoff table ----------
function handoffHTML(cur){const hs=DATA.handoffs.filter(h=>h.i<=cur);
 if(!DATA.handoffs.length)return `<p style="color:var(--mut)">No cross-agent reads — no stigmergic handoffs (single-agent run, or every agent read only its own work).</p>`;
 return `<p style="color:var(--mut);font-size:12px">${hs.length} / ${DATA.handoffs.length} handoffs so far · total delivered ${hs.reduce((s,h)=>s+h.chars,0).toLocaleString()} chars</p><table><tr><th>#</th><th>writer</th><th>&rarr; reader</th><th>path</th><th>chars</th></tr>`+
 hs.map(hf=>`<tr data-seek="${hf.i}" style="cursor:pointer"><td class="mono">e${hf.i}</td><td class="mono">${esc(hf.writer)}</td><td class="mono">${esc(hf.reader)}</td><td class="mono">${esc(hf.path)}</td><td>${hf.chars.toLocaleString()}</td></tr>`).join("")+`</table>`;}
// ---------- data geography ----------
function geoHTML(cur){const rp=replay(cur), mem=rp.mem;
 // K
 const agAt=AG.filter(a=>rp.st[a.id]!==undefined);
 $("#planeK").innerHTML=`<h3>K — Catalog <small style="color:var(--mut)">index</small></h3>
  <div class="meta" style="color:var(--mut);font-size:11px;margin-bottom:6px">mechanical index · ${DATA.catalog_calls} catalog queries this run</div>
  ${agAt.map(a=>`<div class="art"><span class="p mono">agent:${esc(a.id)}</span> <span class="meta">· ${esc(rp.st[a.id])} · ${esc(a.role)} · round ${rp.round[a.id]||0}</span></div>`).join("")||'<div class="meta">no agents yet</div>'}`;
 // W grouped by owner
 const wpaths=Object.keys(DATA.workspaces).sort();
 const byOwner={}; wpaths.forEach(p=>{const o=DATA.workspaces[p].owner; (byOwner[o]??=[]).push(p);});
 $("#planeW").innerHTML=`<h3>W — Workspaces <small style="color:var(--mut)">per-agent · open read</small></h3>`+
  (Object.keys(byOwner).length?Object.keys(byOwner).sort().map(o=>`<div class="grp">agents/${esc(o)}/</div>`+byOwner[o].map(p=>{const w=DATA.workspaces[p],live=mem.has(p);
   return `<div class="art ${live?"":"ghost"}"><span class="p mono">${esc(p.replace("agents/"+o+"/",""))}</span> <span class="meta">· ${w.chars.toLocaleString()} chars${w.author!==o?` · by ${esc(w.author)}`:""}${w.writes>1?` · ${w.writes} writes`:""}</span></div>`;}).join("")).join(""):'<div class="meta">no workspace files</div>');
 // G
 const gpaths=Object.keys(DATA.global).sort();
 $("#planeG").innerHTML=`<h3>G — Global <small style="color:var(--mut)">linear-versioned · shared</small></h3>`+
  (gpaths.length?gpaths.map(p=>{const a=DATA.global[p],live=mem.has(p),head=a.versions[a.versions.length-1]||{};
   return `<div class="art ${live?"":"ghost"} ${a.divergent?"div":""}"><span class="p mono">${esc(p)}</span> <span class="meta">· v${a.head}${a.divergent?" ⑂DIVERGENT":""} · ${(head.chars||0).toLocaleString()} chars · by ${esc(head.author)} (r${head.round})</span>${a.versions.length>1?`<div class="meta">${a.versions.length} versions: ${a.versions.map(v=>"v"+v.version+"·"+v.author).join(", ")}</div>`:""}</div>`;}).join(""):'<div class="meta">no global artifacts yet</div>');}
// ---------- trajectory ----------
const TDOT={ws_write:"#c99be0",g_commit:"#5fbf8f",lifecycle:"#3987e5",rule_add:"#9085e9",rule_fired:"#9085e9",rule_update:"#e0952b",rule_disable:"#898781",spawn:"#3987e5",llm_call:"#52514e",llm_reply:"#6f6d67",tool_call:"#44443f",divergence_flagged:"#e0952b",rule_target_invalid:"#d03b3b",parse_errors:"#d03b3b",rail_hit:"#d03b3b",health_verdict:"#0ca30c",run_end:"#0ca30c",run_start:"#0ca30c",cross_workspace_write:"#e0952b"};
const types=[...new Set(EV.map(e=>e.y))], DEFHIDE=new Set(["llm_call","tool_call"]), on=new Set(types.filter(t=>!DEFHIDE.has(t)));
$("#tfilters").innerHTML=types.map(t=>`<label class="${on.has(t)?"on":""}" data-t="${esc(t)}">${esc(t)}</label>`).join("");
function drawT(){const q=$("#tsearch").value.toLowerCase();
 $("#ttable").innerHTML=`<table><tr><th>#</th><th>t+s</th><th>agent</th><th>event</th><th>what happened</th></tr>`+EV.filter(e=>on.has(e.y)&&(!q||e.x.toLowerCase().includes(q))).map(e=>
  `<tr id="ev${e.i}" class="${e.i===CUR?"cur":e.i>CUR?"future":""}" data-seek="${e.i}" style="cursor:pointer"><td class="mono">${e.i}</td><td class="mono">${e.t}</td><td class="mono">${esc(e.a||"")}</td><td class="mono"><span class="tdot" style="background:${TDOT[e.y]||"#898781"}"></span>${esc(e.y)}</td><td>${esc(e.x)}</td></tr>`).join("")+`</table>`;}
document.querySelectorAll("#tfilters label").forEach(l=>l.addEventListener("click",()=>{const t=l.dataset.t; on.has(t)?on.delete(t):on.add(t); l.classList.toggle("on"); drawT();}));
$("#tsearch").addEventListener("input",drawT);
// ---------- event inspector ----------
function kv(rows){return `<table>${rows.map(([k,v])=>`<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join("")}</table>`;}
function lookupArtifact(p,ver){if(DATA.global[p]){const a=DATA.global[p];const v=ver?a.versions.find(x=>x.version===ver):a.versions[a.versions.length-1];return v?v.content:"";} if(DATA.workspaces[p])return DATA.workspaces[p].content; return null;}
function inspect(){const e=EV[CUR]||{}; let hh="";
 if(e.y==="llm_call"){hh=`<h4>INPUT — prompt assembled for ${esc(e.a)} (round ${e.r})</h4>`+kv([["prompt size",`<b>${(e.pc||0).toLocaleString()}</b> chars`],["rolling window",`${e.win} prior rounds`],["agent role",esc(byId[e.a]?.role||"")]])+`<p class="k" style="margin-top:8px">The reply this produced is at the next event — step → to read what the agent generated.</p>`;}
 else if(e.y==="llm_reply"){const cut=e.fin==="length";
  hh=`<h4>OUTPUT — ${esc(e.a)} reply <span class="tag">${(e.ct||0).toLocaleString()} tok out</span>${cut?'<span class="tag cut">CUT at token cap</span>':""}</h4><pre>${esc(e.tx||"")}</pre>`;}
 else if(e.y==="tool_call"){const err=e.err;
  hh=`<h4>TOOL — ${esc(e.a)} called <b>${esc(e.tool)}</b> ${err?'<span class="tag err">ERROR</span>':""}${e.trunc?'<span class="tag cut">truncated return</span>':""}${e.hf?'<span class="tag">handoff ←'+esc(e.hf.writer)+'</span>':""}</h4>`+
   `<div class="k">args</div><pre>${esc(JSON.stringify(e.args,null,2))}</pre><div class="k">result (trace-capped 2000 chars)</div><pre>${esc(e.res||"")}</pre>`;}
 else if(e.y==="g_commit"||e.y==="ws_write"){const body=lookupArtifact(e.p,e.ver);
  hh=`<h4>ARTIFACT — ${esc(e.a)} ${e.y==="g_commit"?"committed to G":"wrote to W"} <span class="mono">${esc(e.p)}</span>${e.ver?" v"+e.ver:""} (${(e.ch||0).toLocaleString()} chars)${e.div?'<span class="tag err">DIVERGENT</span>':""}${e.cross?'<span class="tag cut">cross-workspace</span>':""}</h4>${body!==null?`<pre>${esc(body)}</pre>`:'<p class="k">(intermediate write — only final content is retained in state.json)</p>'}`;}
 else if(e.y==="rule_add"){const r=ruleById[e.rid]||{};
  hh=`<h4>CIRCUIT — ${esc(e.a)} authored rule <b>${esc(e.rid)}</b>${e.via?` <span class="tag">via ${esc(e.via)}</span>`:""}</h4>`+
   kv([["condition φ",`<span class="mono">${esc(r.condition)}</span>`],["target σ",`<span class="mono">${esc(target_str(r.target))}</span>`],
       ["references agents",`<span class="mono">${(r.refs_agents||[]).join(", ")||"—"}</span>`],
       ["references artifacts",`<span class="mono">${(r.refs_paths||[]).map(esc).join("<br>")||"—"}</span>`]])+
   `<p class="k" style="margin-top:8px">The condition is a Python boolean expression over read-only state accessors; it fires mechanically (exactly once per armed state) when it evaluates true.</p>`;}
 else if(e.y==="rule_fired"){const r=ruleById[e.rid]||{};
  hh=`<h4>CIRCUIT — rule <b>${esc(e.rid)}</b> FIRED → ${esc(target_str(r.target))}</h4>`+kv([["condition became true",`<span class="mono">${esc(r.condition)}</span>`],["author",esc(r.author)]]);}
 else if(e.y==="rule_update"){hh=`<h4>CIRCUIT — ${esc(e.a)} edited rule <b>${esc(e.rid)}</b> (${(e.changed||[]).join(", ")})</h4><p class="k">${e.a!==(ruleById[e.rid]||{}).author?'<span class="tag err">non-author edit — emergence signal</span>':"author edit"}</p>`;}
 else if(e.y==="spawn"){hh=`<h4>${esc(e.parent||"runtime")} spawned <b>${esc(e.a)}</b>${e.via?` <span class="tag">via rule ${esc(e.via)}</span>`:""}</h4><pre>${esc(e.ctask||"")}</pre>`;}
 else if(e.y==="lifecycle"){hh=`<h4>${esc(e.a)}: ${esc(e.fr)} → ${esc(e.to)}</h4><div class="reason">${esc(e.reason||"")}</div>`;}
 else if(e.y==="health_verdict"){hh=`<h4>HEALTH VERDICT</h4><pre>${esc(JSON.stringify({quiescent:h.quiescent,root_state:h.root_state,waiting_at_end:h.waiting_at_end,failed_agents:h.failed_agents,systemic_failure:h.systemic_failure,failure_reasons:h.failure_reasons},null,2))}</pre>`;}
 else hh=`<span class="k">no rich payload on <b>${esc(e.y)}</b> — the input/output side lives on llm_call / llm_reply / tool_call / g_commit / rule_*. Step with ←/→.</span>`;
 $("#evdetail").innerHTML=hh;}
function target_str(t){if(!t)return"";if(t.type==="resume")return"resume "+t.agent_id;if(t.type==="spawn")return"spawn: "+String(t.task||"").slice(0,60);return JSON.stringify(t);}
// ---------- paint ----------
let CUR=LAST;
function paintGraph(){const cur=replay(CUR);
 // neighbourhood of the current selection (for dimming everything else)
 const nbr=new Set(); if(SEL){nbr.add(SEL); curEdges.forEach(e=>{if(e.from===SEL)nbr.add(e.to); if(e.to===SEL)nbr.add(e.from);
   if(SELRULE&&e.rule===SELRULE){nbr.add(e.from);nbr.add(e.to);}});}
 document.querySelectorAll("#gsvg .node").forEach(el=>{const n=gById[el.dataset.nid]; if(!n)return; let cls="node ";
  if(n.kind==="agent"){const s=cur.st[n.ref]; cls+="gn-agent "+(s?("st-"+s):"ghost")+(s==="starved"?" starved":"");
   const sub=el.querySelector("[data-sub]"); if(sub){const rn=cur.round[n.ref]||0,w=(cur.writes[n.ref]||[]).length; sub.textContent=s?`${s} · r${rn}${w?" · "+w+"w":""}`:n.sub;}}
  else if(n.kind==="rule"){cls+="gn-rule rs-"+(cur.rs[n.ref]||"pending");}
  else{const live=cur.mem.has(n.ref); cls+="gn-art plane-"+n.plane+(n.written?(live?"":" ghost"):" phantom")+(n.divergent?" divg":"");}
  if(SEL===n.nid)cls+=" sel"; else if(SEL&&!nbr.has(n.nid))cls+=" dim";
  el.setAttribute("class",cls);});
 curEdges.forEach((e,i)=>{const p=document.getElementById("e"+i); if(!p)return;
  p.classList.toggle("ghost",e.at>CUR);
  const rel=(SEL&&(e.from===SEL||e.to===SEL))||(SELRULE&&e.rule===SELRULE);
  p.classList.toggle("hl",!!rel); p.classList.toggle("fade",(SEL||SELRULE)&&!rel);});}
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
 document.querySelectorAll("#ttable tr[data-seek]").forEach(r=>r.addEventListener("click",()=>seek(+r.dataset.seek)));}
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
