#!/usr/bin/env bash
# ET 60-run ladder — pre-registered order: interleave arms within level,
# rep by rep, levels 1 -> 5. Idempotent: completed runs are skipped
# (metrics.json present), partial runs are cleared and rerun.
set -u
cd "$(dirname "$0")/../.."
# our own vLLM (GPU 0); port 8000 belongs to another user — never use it
export RATD_LOCAL_ENDPOINT="http://127.0.0.1:8001/v1/chat/completions"
OUT=results/et
for level in L1 L2 L3 L4 L5; do
  for rep in 1 2 3 4; do
    for arm in r p s; do
      python3 -m src.ratd_v2.run --arm "$arm" --tasks tasks/et_ladder.json \
        --task-ids "$level" --reps 1 --rep-start "$rep" --out-dir "$OUT" \
        || echo "RUN-FAILED ${arm}_${level}_r${rep}"
    done
  done
done
echo LADDER-DONE
