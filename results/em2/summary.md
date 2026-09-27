# E1 Summary — RATD vs replanning central planner

Judge: qwen3.6 (same as agents), frozen prompts/judge_v1.md +
rubrics/L*.md, system-blind, fixed-seed order. n=3 per cell —
feasibility-scale evidence, not significance. Temp-0 clustering
may reduce effective n; per-run scores listed for that reason.

| Level | System | conv | overall (mean±sd, per-run) | ctx chars/decision (mean) | decisions | LLM calls (mean) |
|---|---|---|---|---|---|---|
| L3 | ratd | 3/3 | 8.3±1.2 (9, 9, 7) | 9,217 | 22.0 | 46.3 |
| L3 | planner | 3/3 | 7.7±2.3 (9, 5, 9) | 34,376 | 8.0 | 15.0 |
| L4 | ratd | 3/3 | 5.0±0.0 (5, 5, 5) | 11,110 | 13.3 | 25.3 |
| L4 | planner | 3/3 | 5.0±0.0 (5, 5, 5) | 41,836 | 17.0 | 33.0 |

## Per-run detail

- L3_r1 [ratd] conv=True overall=9 (acc 9, compl 8, struct 9, consist 9) ctx/decision=9,384 max=16,875
- L3_r2 [ratd] conv=True overall=9 (acc 9, compl 10, struct 9, consist 9) ctx/decision=8,888 max=16,444
- L3_r3 [ratd] conv=True overall=7 (acc 9, compl 6, struct 9, consist 9) ctx/decision=9,378 max=16,875
- L4_r1 [ratd] conv=True overall=5 (acc 9, compl 4, struct 8, consist 9) ctx/decision=10,888 max=18,052
- L4_r2 [ratd] conv=True overall=5 (acc 9, compl 4, struct 8, consist 9) ctx/decision=11,519 max=18,346
- L4_r3 [ratd] conv=True overall=5 (acc 9, compl 4, struct 8, consist 9) ctx/decision=10,923 max=18,053
- L3_r1 [planner] conv=True overall=9 (acc 9, compl 8, struct 9, consist 9) ctx/decision=34,316 max=60,226
- L3_r2 [planner] conv=True overall=5 (acc 9, compl 4, struct 5, consist 8) ctx/decision=34,286 max=60,136
- L3_r3 [planner] conv=True overall=9 (acc 9, compl 8, struct 9, consist 9) ctx/decision=34,527 max=61,178
- L4_r1 [planner] conv=True overall=5 (acc 9, compl 4, struct 6, consist 9) ctx/decision=41,976 max=61,310
- L4_r2 [planner] conv=True overall=5 (acc 9, compl 4, struct 6, consist 8) ctx/decision=41,766 max=62,364
- L4_r3 [planner] conv=True overall=5 (acc 9, compl 4, struct 6, consist 8) ctx/decision=41,767 max=62,370
