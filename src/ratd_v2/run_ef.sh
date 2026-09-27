#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/../.."
export RATD_LOCAL_ENDPOINT="${RATD_LOCAL_ENDPOINT:-http://127.0.0.1:8001/v1/chat/completions}"
OUT=results/ef; DROP=wait,continue; REPS="${REPS:-1}"
run_cell () { local c=$1 t=$2 r=$3; shift 3; python3 -m src.ratd_v2.run --arm s --label "$c" --tasks tasks/ef_tasks.json --task-ids "$t" --harness-dir prompts/ef --harness-override "stig=harness_${c}.md" --reps 1 --rep-start "$r" --out-dir "$OUT" "$@" || echo "RUN-FAILED ${c}_${t}_r${r}"; }
for t in T1 T2; do for r in $REPS; do run_cell nn "$t" "$r"; run_cell ns "$t" "$r" --surface-drop "$DROP" --no-self-resume; run_cell rn "$t" "$r"; run_cell rs "$t" "$r" --surface-drop "$DROP" --no-self-resume; done; done
echo EF-LADDER-DONE
