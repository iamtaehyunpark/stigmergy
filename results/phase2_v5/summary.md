# Phase 2 Summary

- Runs: 6
- Convergence: 4/6
- Schema agreement rate: 100.00% (24/24)
- Trigger fire errors: 0
- Ready-but-unfired triggers: 0
- Conflicts: 0
- Budget violations attempted: 0
- Worker schema mismatches: 0
- Rail hits: 0
- Cross-branch reads: 46

## Runs

### t06_r1

- Task: t06
- Converged: True
- Root outputs: root.4/comparative_report
- Root outputs done: root.4/comparative_report
- LLM calls: 10
- Graph depth: 1
- Agent count: 5
- Defer count: 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### t06_r2

- Task: t06
- Converged: True
- Root outputs: root.4/final_report
- Root outputs done: root.4/final_report
- LLM calls: 10
- Graph depth: 1
- Agent count: 5
- Defer count: 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### t15_r1

- Task: t15
- Converged: True
- Root outputs: root.6/business_plan
- Root outputs done: root.6/business_plan
- LLM calls: 14
- Graph depth: 1
- Agent count: 7
- Defer count: 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### t15_r2

- Task: t15
- Converged: True
- Root outputs: root.6/business_plan
- Root outputs done: root.6/business_plan
- LLM calls: 14
- Graph depth: 1
- Agent count: 7
- Defer count: 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### t09_r1

- Task: t09
- Converged: False
- Root outputs: root.2/backend_code.zip, root.2/api_spec.json, root.3/frontend_code.zip, root.4/test_results.json, root.4/test_code.zip
- Root outputs done: root.2/backend_code.zip, root.3/frontend_code.zip, root.4/test_results.json, root.4/test_code.zip
- LLM calls: 11
- Graph depth: 2
- Agent count: 7
- Defer count: 1
- Qualitative: Did not converge to the declared root output within rails.

### t09_r2

- Task: t09
- Converged: False
- Root outputs: root.2/backend_code.zip, root.2/api_spec.json, root.3/frontend_code.zip, root.4/test_results.json, root.4/test_code.zip
- Root outputs done: root.2/backend_code.zip, root.3/frontend_code.zip, root.4/test_results.json, root.4/test_code.zip
- LLM calls: 11
- Graph depth: 2
- Agent count: 7
- Defer count: 1
- Qualitative: Did not converge to the declared root output within rails.
