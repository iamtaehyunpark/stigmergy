# Phase 2 Summary

- Runs: 6
- Convergence: 3/6
- Schema agreement rate: 83.87% (26/31)
- Trigger fire errors: 0
- Ready-but-unfired triggers: 0
- Conflicts: 0
- Budget violations attempted: 0
- Worker schema mismatches: 0
- Rail hits: 0
- Cross-branch reads: 33

## Runs

### t06_r1

- Task: t06
- Converged: True
- Root outputs: root.2/features_summary, root.3/pricing_summary, root.4/performance_summary, root.5/final_report
- Root outputs done: root.2/features_summary, root.3/pricing_summary, root.4/performance_summary, root.5/final_report
- LLM calls: 12
- Graph depth: 1
- Agent count: 6
- Defer count: 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### t06_r2

- Task: t06
- Converged: True
- Root outputs: root.2/features_analysis, root.3/pricing_analysis, root.4/performance_analysis, root.5/final_report
- Root outputs done: root.2/features_analysis, root.3/pricing_analysis, root.4/performance_analysis, root.5/final_report
- LLM calls: 12
- Graph depth: 1
- Agent count: 6
- Defer count: 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### t15_r1

- Task: t15
- Converged: False
- Root outputs: root.6/business_plan
- Root outputs done: (none)
- LLM calls: 14
- Graph depth: 2
- Agent count: 8
- Defer count: 0
- Qualitative: Did not converge to the declared root output within rails.

### t15_r2

- Task: t15
- Converged: False
- Root outputs: root.6/business_plan
- Root outputs done: (none)
- LLM calls: 10
- Graph depth: 1
- Agent count: 6
- Defer count: 1
- Qualitative: Did not converge to the declared root output within rails.

### t09_r1

- Task: t09
- Converged: True
- Root outputs: root.2/backend_code, root.2/api_spec, root.3/frontend_code, root.4/integration_tests
- Root outputs done: root.2/backend_code, root.2/api_spec, root.3/frontend_code, root.4/integration_tests
- LLM calls: 10
- Graph depth: 1
- Agent count: 5
- Defer count: 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### t09_r2

- Task: t09
- Converged: False
- Root outputs: root.2/backend_code, root.2/api_spec, root.3/frontend_code, root.4/test_code, root.4/test_report
- Root outputs done: (none)
- LLM calls: 8
- Graph depth: 2
- Agent count: 5
- Defer count: 0
- Qualitative: Did not converge to the declared root output within rails.
