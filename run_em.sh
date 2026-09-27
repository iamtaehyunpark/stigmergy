#!/bin/bash
# EM-series driver — runs on galaxy-05. Resumable (each runner skips
# completed runs via metrics.json). Logs each phase with timestamps.
set -uo pipefail
cd /home/tpark45/stigmergy
export RATD_LOCAL_ENDPOINT="http://127.0.0.1:8000/v1/chat/completions"

# max_tokens 16000: 4000 truncated deep-task worker JSON mid-string
# (chapter drafts, final assembly) -> worker_invalid fallbacks -> spurious
# systemic failure. 16000 lets artifacts complete as valid JSON; verified
# on d03 (converged, 0 fallback, 20/20 pins). Uniform across the series.
MT=16000

stamp() { date "+%Y-%m-%d %H:%M:%S"; }
phase() { echo; echo "======== $1 $(stamp) ========"; }

# Run a phase, retrying up to 4x. Each retry resumes (completed runs are
# skipped via metrics.json), so a mid-phase crash never loses progress and
# never cascades into the next phase on a partial result.
run_phase() {
  local name="$1"; shift
  local try
  for try in 1 2 3 4; do
    phase "$name (attempt $try)"
    if "$@"; then echo "$name OK (attempt $try)"; return 0; fi
    echo "$name attempt $try exited $?; resuming in 20s..."; sleep 20
  done
  echo "$name STILL FAILING after 4 attempts — leaving partial results, continuing"
  return 1
}

rm -rf results/_sanity results/_fixtest 2>/dev/null

run_phase "EM0 Regression Gauntlet" python3 -m src.em.em0 --out-dir results/em0 --max-tokens $MT
run_phase "EM1 Two-Regime Test"     python3 -m src.em.em1 --out-dir results/em1 --max-tokens $MT
run_phase "EM2 Quality Completion"  python3 -m src.em.em2 --out-dir results/em2 --max-tokens $MT
run_phase "EM3 Doctor Validation"   python3 -m src.em.em3 --out-dir results/em3 --max-tokens $MT

phase "Assemble EM_REPORT"
python3 -m src.em.report --results-dir results; echo "report exit: $?"

phase "ALL DONE"
