"""Mechanical EF delegation metrics and manual-annotation worksheet."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from .client import write_json
CELLS = ("nn", "ns", "rn", "rs")
CONSIDER = re.compile(r"\b(spawn|deleg\w*|sub-?agent|child agent|another agent|other agents|split (?:it|this|the task)|hand (?:it|this) off|assign\w* to)\b", re.I)

def analyze(path: Path) -> dict:
    meta = json.loads((path / "run_meta.json").read_text()); events = [json.loads(x) for x in (path / "trace.jsonl").read_text().splitlines()]
    dropped = set(meta.get("surface_drop", [])); parent = {}; spawns=[]; acts=[]; blocked=[]; implicit=explicit=resumes=0
    for e in events:
        if e["event"] == "spawn": parent[e["agent"]] = e.get("parent"); spawns.append(e)
        elif e["event"] == "implicit_continue": implicit += 1
        elif e["event"] == "lifecycle" and e.get("to") == "running" and str(e.get("reason", "")).startswith("resumed by"): resumes += 1
        elif e["event"] == "tool_call":
            if not e.get("error") and e.get("tool") in ("wait", "continue"): explicit += 1
            if e.get("error") and (e.get("tool") in dropped or "resume" in str(e.get("result", "")).lower()): blocked.append(e)
        elif e["event"] == "llm_reply": acts.append({"seq":e["seq"],"agent":e["agent"],"round":e["round"],"prefill":bool(CONSIDER.search(e.get("text", ""))),"text":e.get("text", "")})
    def depth(a):
        n=0; seen=set()
        while parent.get(a) and a not in seen: seen.add(a); a=parent[a]; n+=1
        return n
    nonroot=[e for e in spawns if e.get("parent") not in (None, "root")]
    replies=[e for e in events if e["event"] == "llm_reply"]
    return {"run_id":meta["run_id"],"cell":meta.get("label",meta["arm"]),"task":meta["task"]["id"],"frame":"router" if meta.get("label","").startswith("r") else "neutral","action_space":"spawn-only" if dropped else "revive","spawns_total":len(spawns),"non_root_spawns":len(nonroot),"direct_spawns":sum(not e.get("rule") for e in spawns),"rule_spawns":sum(bool(e.get("rule")) for e in spawns),"max_depth":max(map(depth,parent),default=0),"n_agents":len(parent),"explicit_revive_calls":explicit,"implicit_reactivations":implicit,"lifecycle_resumes":resumes,"blocked_channel_attempt_count":len(blocked),"blocked_channel_attempts":[{"seq":e["seq"],"agent":e["agent"],"tool":e["tool"],"result":str(e.get("result",""))[:200]} for e in blocked],"llm_calls":len(replies),"total_tokens":sum(e.get("prompt_tokens",0)+e.get("completion_tokens",0) for e in replies),"activations":acts}

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--runs-dir",default="results/ef"); a=p.parse_args(); root=Path(a.runs_dir)
    rows=[analyze(x) for x in sorted(root.iterdir()) if x.is_dir() and (x/"trace.jsonl").exists() and (x/"run_meta.json").exists()]
    write_json(root/"analysis_ef.json",rows)
    table=["# EF delegation table","","| task | cell | frame | action space | agents | spawns | non-root | direct/rule | depth | explicit revive | implicit react. | blocked | calls | tokens |","|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for task in sorted({x["task"] for x in rows}):
      for cell in CELLS:
       for x in [y for y in rows if y["task"]==task and y["cell"]==cell]: table.append(f"| {task} | {cell} | {x['frame']} | {x['action_space']} | {x['n_agents']} | {x['spawns_total']} | **{x['non_root_spawns']}** | {x['direct_spawns']}/{x['rule_spawns']} | {x['max_depth']} | {x['explicit_revive_calls']} | {x['implicit_reactivations']} | {x['blocked_channel_attempt_count']} | {x['llm_calls']} | {x['total_tokens']} |")
    (root/"delegation_table.md").write_text("\n".join(table)+"\n")
    sheet=["# EF annotation worksheet","","Mark each activation CONSIDERED / NOT-CONSIDERED / DELEGATED. `prefill` is a regex hint only; manual trace reading is authoritative.",""]
    for x in rows:
      sheet += [f"## {x['run_id']}",""]
      for q in x["activations"]: sheet.append(f"- seq {q['seq']} · {q['agent']} r{q['round']} · prefill={'Y' if q['prefill'] else 'n'} · verdict=____ · `{' '.join(q['text'].split())[:220]}`")
      sheet.append("")
    (root/"ANNOTATION_WORKSHEET.md").write_text("\n".join(sheet)+"\n"); print("\n".join(table)); return 0
if __name__ == "__main__": raise SystemExit(main())
