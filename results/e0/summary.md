# E0 Summary

- Runs: 12
- Convergence: 12/12
- Schema agreement rate: 100.00% (271/271)
- Trigger fire errors: 0
- Ready-but-unfired triggers: 0
- Conflicts: 0
- Worker schema mismatches: 3
- Rail hits: 0 (none)
- Natural terminations: 12/12
- Cross-branch reads (unique agent,path pairs): 12 (event fallback: 23)
- self_role distribution: parallel 0, gated 69
- Interface self-fulfillment: 100.00% (93/93 owed paths taken by the parent's own self_role)

## Runs

### d01_r1

- Task: d01
- Converged: True
- Root outputs: root.2/backend_code, root.2/api_spec, root.3/frontend_code, root.4/integration_tests, root/final_summary
- Root outputs done: root.2/backend_code, root.2/api_spec, root.3/frontend_code, root.4/integration_tests, root/final_summary
- LLM calls: 10
- Graph depth: 1
- Agent count: 5 (spawns: 4)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 1; owed self/delegated 0/0
- Cross-branch reads (unique pairs): 4
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### d01_r2

- Task: d01
- Converged: True
- Root outputs: root.2/backend_code, root.2/api_spec, root.3/frontend_code, root.4/integration_tests, root/final_report
- Root outputs done: root.2/backend_code, root.2/api_spec, root.3/frontend_code, root.4/integration_tests, root/final_report
- LLM calls: 10
- Graph depth: 1
- Agent count: 5 (spawns: 4)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 1; owed self/delegated 0/0
- Cross-branch reads (unique pairs): 4
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### d01_r3

- Task: d01
- Converged: True
- Root outputs: root.2/backend_code.tar.gz, root.3/frontend_code.tar.gz, root.4/integration_tests.tar.gz, root/final_summary.md
- Root outputs done: root.2/backend_code.tar.gz, root.3/frontend_code.tar.gz, root.4/integration_tests.tar.gz, root/final_summary.md
- LLM calls: 20
- Graph depth: 2
- Agent count: 7 (spawns: 6)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 2; owed self/delegated 1/0
- Cross-branch reads (unique pairs): 4
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition; worker path mismatches occurred.

### d02_r1

- Task: d02
- Converged: True
- Root outputs: root/business_plan
- Root outputs done: root/business_plan
- LLM calls: 96
- Graph depth: 8
- Agent count: 48 (spawns: 47)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 16; owed self/delegated 15/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### d02_r2

- Task: d02
- Converged: True
- Root outputs: root/business_plan
- Root outputs done: root/business_plan
- LLM calls: 43
- Graph depth: 4
- Agent count: 21 (spawns: 20)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 7; owed self/delegated 6/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### d02_r3

- Task: d02
- Converged: True
- Root outputs: root/business_plan
- Root outputs done: root/business_plan
- LLM calls: 48
- Graph depth: 4
- Agent count: 24 (spawns: 23)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 7; owed self/delegated 6/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### d03_r1

- Task: d03
- Converged: True
- Root outputs: root/field_guide_final
- Root outputs done: root/field_guide_final
- LLM calls: 31
- Graph depth: 2
- Agent count: 15 (spawns: 14)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 5; owed self/delegated 4/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### d03_r2

- Task: d03
- Converged: True
- Root outputs: root/glossary, root/final_guide
- Root outputs done: root/glossary, root/final_guide
- LLM calls: 30
- Graph depth: 3
- Agent count: 14 (spawns: 13)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 4; owed self/delegated 3/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### d03_r3

- Task: d03
- Converged: True
- Root outputs: root/field_guide_final
- Root outputs done: root/field_guide_final
- LLM calls: 32
- Graph depth: 2
- Agent count: 16 (spawns: 15)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 5; owed self/delegated 4/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### d04_r1

- Task: d04
- Converged: True
- Root outputs: root/global_consistency_review, root/final_launch_kits
- Root outputs done: root/global_consistency_review, root/final_launch_kits
- LLM calls: 50
- Graph depth: 2
- Agent count: 25 (spawns: 24)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 7; owed self/delegated 18/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### d04_r2

- Task: d04
- Converged: True
- Root outputs: root/global_consistency_review, root/final_launch_kits
- Root outputs done: root/global_consistency_review, root/final_launch_kits
- LLM calls: 50
- Graph depth: 2
- Agent count: 25 (spawns: 24)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 7; owed self/delegated 18/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### d04_r3

- Task: d04
- Converged: True
- Root outputs: root/global_consistency_review, root/final_launch_kits
- Root outputs done: root/global_consistency_review, root/final_launch_kits
- LLM calls: 50
- Graph depth: 2
- Agent count: 25 (spawns: 24)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 7; owed self/delegated 18/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.
