#!/bin/bash
# Detached commit+push of the EM milestone — survives connection drops.
set -uo pipefail
cd /home/tpark45/stigmergy
echo "=== add $(date +%H:%M:%S) ==="
git add -A
echo "staged: $(git diff --cached --name-only | wc -l) files"
echo "=== commit $(date +%H:%M:%S) ==="
git commit -q \
  -m "EM-series: spec-v1.0 runtime + EM harness + 72-run validation + viz" \
  -m "src/ratd (spec v1.0: pins/gates/catalog/store/doctor/induction), src/em (EM0-EM3 runners, scorers, schema adapters, circuit inspector, interactive replay), prompts (harness_v7[_nolist], worker_v7, doctor_v1), tasks/em1_tasks, docs (spec + tracker Part E + EM runbook). 72 runs under results/em0-3 with per-run circuit.png/replay.html. Findings: substrate validated (26/27 EM0 converge, 0 conflicts); EM2 quality parity at ~4x lower context, assembly-stub class closed; EM1 harness_v7 delivery collapse (confounded); EM3 doctor heals reachable classes, H3 fallback un-healable (C3 boundary). See results/EM_REPORT.md + THEORY_VS_REALITY.md." \
  -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
echo "committed: $(git log --oneline -1)"
echo "=== push $(date +%H:%M:%S) ==="
git push origin main
echo "=== PUSH_DONE $(date +%H:%M:%S) ==="
git log --oneline -1
