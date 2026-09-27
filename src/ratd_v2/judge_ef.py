"""Blind fixed-seed EF judging using the frozen ET judge protocol."""
from __future__ import annotations
import argparse, os, random
from pathlib import Path
from . import judge as J
from .client import Config, DEFAULT_LOCAL_ENDPOINT, DEFAULT_MODEL, DEFAULT_PROVIDER, ensure_credentials, write_json
def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument("--runs-dir",default="results/ef"); p.add_argument("--out-dir",default="results/ef"); p.add_argument("--local-endpoint",default=os.environ.get("RATD_LOCAL_ENDPOINT",DEFAULT_LOCAL_ENDPOINT)); a=p.parse_args()
 c=Config(os.environ.get("RATD_PROVIDER",DEFAULT_PROVIDER),os.environ.get("RATD_MODEL",DEFAULT_MODEL),0.0,4000,a.local_endpoint); ensure_credentials(c); J.ARM_NAMES=("nn","ns","rn","rs")
 rows=J.collect(Path(a.runs_dir)); random.Random(0).shuffle(rows); rubrics={x:(Path("rubrics/ef")/f"{x}.md").read_text() for x in ("T1","T2")}; prompt=Path("prompts/judge_v1.md").read_text()
 for row in rows: print(f"judging {row['run_id']}...",flush=True); row["judge"]=J.judge_one(row,rubrics[row["level"]],prompt,c)
 for row in rows: row.pop("artifact",None)
 out=Path(a.out_dir); write_json(out/"judge_scores.json",rows)
 lines=["# EF quality summary (secondary metric)","","| task | cell | overall | acc | comp | struct | consist | fallback artifact | systemic failure |","|---|---|---|---|---|---|---|---|---|"]
 for task in ("T1","T2"):
  for cell in ("nn","ns","rn","rs"):
   for r in [z for z in rows if z["level"]==task and z["arm"]==cell]:
    j=r["judge"]; lines.append(f"| {task} | {cell} | **{j['overall']}** | {j['accuracy']} | {j['completeness']} | {j['structure']} | {j['consistency']} | {'yes' if r['artifact_fallback'] else 'no'} | {'YES' if r['systemic_failure'] else 'no'} |")
 (out/"quality_summary.md").write_text("\n".join(lines)+"\n"); return 0
if __name__ == "__main__": raise SystemExit(main())
