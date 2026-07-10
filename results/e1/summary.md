# E1 Summary — RATD vs replanning central planner

Judge: qwen3.6 (same as agents), frozen prompts/judge_v1.md +
rubrics/L*.md, system-blind, fixed-seed order. n=3 per cell —
feasibility-scale evidence, not significance. Temp-0 clustering
may reduce effective n; per-run scores listed for that reason.

| Level | System | conv | overall (mean±sd, per-run) | ctx chars/decision (mean) | decisions | LLM calls (mean) |
|---|---|---|---|---|---|---|
| L1 | ratd | 3/3 | 9.0±0.0 (9, 9, 9) | 7,248 | 1.0 | 2.0 |
| L1 | planner | 3/3 | 9.7±0.6 (10, 9, 10) | 4,605 | 5.0 | 9.0 |
| L2 | ratd | 3/3 | 9.0±0.0 (9, 9, 9) | 7,283 | 4.0 | 9.0 |
| L2 | planner | 3/3 | 10.0±0.0 (10, 10, 10) | 5,505 | 6.0 | 11.0 |
| L3 | ratd | 1/3 | 1.0±0.0 (1, 1, 1) | 7,638 | 16.0 | 31.7 |
| L3 | planner | 3/3 | 3.7±4.6 (1, 9, 1) | 30,472 | 8.0 | 17.0 |
| L4 | ratd | 3/3 | 3.7±2.3 (5, 5, 1) | 8,176 | 10.7 | 22.0 |
| L4 | planner | 3/3 | 3.0±3.5 (7, 1, 1) | 41,581 | 17.0 | 34.3 |

## Per-run detail

- L1_r1 [ratd] conv=True overall=9 (acc 9, compl 8, struct 9, consist 10) ctx/decision=7,248 max=7,248
- L1_r2 [ratd] conv=True overall=9 (acc 9, compl 8, struct 9, consist 10) ctx/decision=7,248 max=7,248
- L1_r3 [ratd] conv=True overall=9 (acc 9, compl 8, struct 9, consist 10) ctx/decision=7,248 max=7,248
- L2_r1 [ratd] conv=True overall=9 (acc 9, compl 10, struct 9, consist 10) ctx/decision=7,283 max=7,348
- L2_r2 [ratd] conv=True overall=9 (acc 9, compl 10, struct 9, consist 10) ctx/decision=7,283 max=7,348
- L2_r3 [ratd] conv=True overall=9 (acc 9, compl 10, struct 9, consist 10) ctx/decision=7,283 max=7,348
- L3_r1 [ratd] conv=False overall=1 (acc 1, compl 1, struct 1, consist 1) [auto-1] ctx/decision=7,579 max=8,151
- L3_r2 [ratd] conv=False overall=1 (acc 1, compl 1, struct 1, consist 1) [auto-1] ctx/decision=7,581 max=8,151
- L3_r3 [ratd] conv=True overall=1 (acc 1, compl 1, struct 1, consist 1) ctx/decision=7,753 max=9,722
- L4_r1 [ratd] conv=True overall=5 (acc 9, compl 4, struct 8, consist 9) ctx/decision=8,065 max=10,181
- L4_r2 [ratd] conv=True overall=5 (acc 9, compl 4, struct 8, consist 9) ctx/decision=8,100 max=10,866
- L4_r3 [ratd] conv=True overall=1 (acc 2, compl 1, struct 3, consist 2) ctx/decision=8,364 max=10,806
- L1_r1 [planner] conv=True overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/decision=4,789 max=8,179
- L1_r2 [planner] conv=True overall=9 (acc 9, compl 10, struct 10, consist 10) ctx/decision=4,511 max=7,613
- L1_r3 [planner] conv=True overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/decision=4,516 max=7,625
- L2_r1 [planner] conv=True overall=10 (acc 9, compl 10, struct 10, consist 10) ctx/decision=5,540 max=10,650
- L2_r2 [planner] conv=True overall=10 (acc 9, compl 10, struct 10, consist 10) ctx/decision=5,502 max=10,532
- L2_r3 [planner] conv=True overall=10 (acc 9, compl 10, struct 10, consist 10) ctx/decision=5,474 max=10,455
- L3_r1 [planner] conv=True overall=1 (acc 1, compl 1, struct 1, consist 1) ctx/decision=29,627 max=51,585
- L3_r2 [planner] conv=True overall=9 (acc 9, compl 10, struct 9, consist 10) ctx/decision=32,150 max=55,228
- L3_r3 [planner] conv=True overall=1 (acc 1, compl 1, struct 1, consist 1) ctx/decision=29,641 max=52,804
- L4_r1 [planner] conv=True overall=7 (acc 9, compl 6, struct 8, consist 9) ctx/decision=43,902 max=63,817
- L4_r2 [planner] conv=True overall=1 (acc 1, compl 1, struct 1, consist 1) ctx/decision=40,194 max=63,501
- L4_r3 [planner] conv=True overall=1 (acc 1, compl 1, struct 1, consist 1) ctx/decision=40,645 max=62,737
