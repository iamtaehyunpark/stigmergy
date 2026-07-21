# ET Summary — three arms (P centralized, R RATD multi-round, S RATD single-shot)

Judge: qwen3.6 (same as agents), frozen prompts/judge_v1.md +
rubrics/et/L*.md, system-blind, fixed-seed order. n=4 per cell.
Per-run scores listed (temp-0 clustering may reduce effective n).

| Level | Arm | fail | overall (mean±sd, per-run) | ctx chars/activation (mean) | total tokens (mean) | calls (mean) | agents (mean) |
|---|---|---|---|---|---|---|---|
| L1 | p | 0/4 | 10.0±0.0 (10, 10, 10, 10) | 12,266 | 16,082 | 5.0 | 1.0 |
| L1 | r | 0/4 | 10.0±0.0 (10, 10, 10, 10) | 13,121 | 17,118 | 5.0 | 1.0 |
| L1 | s | 0/4 | 10.0±0.0 (10, 10, 10, 10) | 11,390 | 3,680 | 1.0 | 1.0 |
| L2 | p | 0/2 | 10.0±0.0 (10, 10) | 29,321 | 170,534 | 21.0 | 4.0 |
| L2 | r | 0/2 | 10.0±0.0 (10, 10) | 20,399 | 36,358 | 6.0 | 1.0 |
| L2 | s | 0/2 | 10.0±0.0 (10, 10) | 11,622 | 11,312 | 3.0 | 1.0 |
| L3 | p | 0/2 | 3.0±0.0 (3, 3) | 83,464 | 2,543,565 | 133.0 | 10.0 |
| L3 | r | 0/2 | 5.0±0.0 (5, 5) | 52,868 | 834,252 | 64.0 | 5.0 |
| L3 | s | 0/2 | 3.0±0.0 (3, 3) | 25,850 | 313,336 | 43.0 | 9.0 |
| L4 | p | 1/1 | 5.0±0.0 (5) | 95,580 | 3,557,454 | 158.0 | 10.0 |
| L4 | r | 1/1 | 3.0±0.0 (3) | 80,959 | 2,215,459 | 114.0 | 11.0 |
| L4 | s | 0/1 | 3.0±0.0 (3) | 14,876 | 203,779 | 33.0 | 6.0 |
| L5 | p | 0/1 | 10.0±0.0 (10) | 28,411 | 211,504 | 24.0 | 5.0 |
| L5 | r | 0/1 | 10.0±0.0 (10) | 33,487 | 177,977 | 18.0 | 1.0 |
| L5 | s | 0/1 | 10.0±0.0 (10) | 19,681 | 93,902 | 10.0 | 1.0 |

## Per-run detail

- p_L1_r1 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=12,266 max=16,491 tokens=16,082
- p_L1_r2 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=12,266 max=16,491 tokens=16,082
- p_L1_r3 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=12,266 max=16,491 tokens=16,082
- p_L1_r4 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=12,266 max=16,491 tokens=16,082
- p_L2_r1 fail=False rail=- overall=10 (acc 9, compl 10, struct 10, consist 10) ctx/act=29,321 max=90,959 tokens=170,534
- p_L2_r2 fail=False rail=- overall=10 (acc 9, compl 10, struct 10, consist 10) ctx/act=29,321 max=90,959 tokens=170,534
- p_L3_r1 fail=False rail=- overall=3 (acc 9, compl 2, struct 4, consist 8) ctx/act=83,464 max=239,791 tokens=2,543,565
- p_L3_r2 fail=False rail=- overall=3 (acc 9, compl 2, struct 4, consist 8) ctx/act=83,464 max=239,791 tokens=2,543,565
- p_L4_r1 fail=True rail=wall_clock overall=5 (acc 9, compl 4, struct 8, consist 9) [fallback-artifact] ctx/act=95,580 max=264,300 tokens=3,557,454
- p_L5_r1 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=28,411 max=69,076 tokens=211,504
- r_L1_r1 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=13,121 max=17,426 tokens=17,118
- r_L1_r2 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=13,121 max=17,426 tokens=17,118
- r_L1_r3 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=13,121 max=17,426 tokens=17,118
- r_L1_r4 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=13,121 max=17,426 tokens=17,118
- r_L2_r1 fail=False rail=- overall=10 (acc 9, compl 10, struct 10, consist 10) ctx/act=20,399 max=39,130 tokens=36,358
- r_L2_r2 fail=False rail=- overall=10 (acc 9, compl 10, struct 10, consist 10) ctx/act=20,399 max=39,130 tokens=36,358
- r_L3_r1 fail=False rail=- overall=5 (acc 9, compl 4, struct 8, consist 9) ctx/act=52,868 max=139,255 tokens=834,252
- r_L3_r2 fail=False rail=- overall=5 (acc 9, compl 4, struct 8, consist 9) ctx/act=52,868 max=139,255 tokens=834,252
- r_L4_r1 fail=True rail=- overall=3 (acc 9, compl 2, struct 6, consist 8) ctx/act=80,959 max=183,513 tokens=2,215,459
- r_L5_r1 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=33,487 max=45,932 tokens=177,977
- s_L1_r1 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=11,390 max=11,390 tokens=3,680
- s_L1_r2 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=11,390 max=11,390 tokens=3,680
- s_L1_r3 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=11,390 max=11,390 tokens=3,680
- s_L1_r4 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=11,390 max=11,390 tokens=3,680
- s_L2_r1 fail=False rail=- overall=10 (acc 9, compl 10, struct 10, consist 10) ctx/act=11,622 max=12,013 tokens=11,312
- s_L2_r2 fail=False rail=- overall=10 (acc 9, compl 10, struct 10, consist 10) ctx/act=11,622 max=12,013 tokens=11,312
- s_L3_r1 fail=False rail=- overall=3 (acc 9, compl 2, struct 3, consist 8) [fallback-artifact] ctx/act=25,850 max=87,235 tokens=313,336
- s_L3_r2 fail=False rail=- overall=3 (acc 9, compl 2, struct 3, consist 8) [fallback-artifact] ctx/act=25,850 max=87,235 tokens=313,336
- s_L4_r1 fail=False rail=- overall=3 (acc 9, compl 2, struct 6, consist 8) [fallback-artifact] ctx/act=14,876 max=34,760 tokens=203,779
- s_L5_r1 fail=False rail=- overall=10 (acc 10, compl 10, struct 10, consist 10) ctx/act=19,681 max=41,497 tokens=93,902
