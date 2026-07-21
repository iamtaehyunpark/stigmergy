#!/usr/bin/env bash
# ET ladder — pre-registered order: interleave arms within level, rep by
# rep, levels 1 -> 5. Idempotent: completed runs are skipped (metrics.json
# present), partial runs are cleared and rerun.
#
# ADAPTIVE REPLICATION (pre-registration deviation, logged 2026-07-21,
# outcome-blind): the owned serial endpoint is byte-deterministic at temp 0
# (verified: all L1/L2 replicates token-identical), so reps 3-4 of a cell
# whose reps 1-2 match exactly add no information. Reps 1-2 always run
# (rep 2 IS the determinism verification, via src.ratd_v2.det_check);
# any cell whose reps diverge gets the full n=4.
set -u
cd "$(dirname "$0")/../.."
# our own vLLM (GPU 0); port 8000 belongs to another user — never use it
export RATD_LOCAL_ENDPOINT="http://127.0.0.1:8001/v1/chat/completions"
OUT=results/et
REPS="${REPS:-1 2}"   # adaptive replication: 1-2 by default; divergent cells rerun with REPS="3 4"
for level in L1 L2 L3 L4 L5; do
  for rep in $REPS; do
    for arm in r p s; do
      python3 -m src.ratd_v2.run --arm "$arm" --tasks tasks/et_ladder.json \
        --task-ids "$level" --reps 1 --rep-start "$rep" --out-dir "$OUT" \
        || echo "RUN-FAILED ${arm}_${level}_r${rep}"
    done
  done
done
echo LADDER-DONE
