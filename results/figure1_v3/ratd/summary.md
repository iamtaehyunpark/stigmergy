# E0 Summary

- Runs: 4
- Convergence: 4/4
- Schema agreement rate: 100.00% (48/48)
- Trigger fire errors: 0
- Ready-but-unfired triggers: 0
- Conflicts: 0
- Worker schema mismatches: 2
- Rail hits: 0 (none)
- Natural terminations: 4/4
- Cross-branch reads (unique agent,path pairs): 24 (event fallback: 41)
- self_role distribution: parallel 0, gated 15
- Interface self-fulfillment: 75.00% (12/16 owed paths taken by the parent's own self_role)

## Runs

### f01_r1

- Task: f01
- Converged: True
- Root outputs: root.2/tutorial_en, root.2/tutorial_kr, root/consistency_report
- Root outputs done: root.2/tutorial_en, root.2/tutorial_kr, root/consistency_report
- LLM calls: 17
- Graph depth: 2
- Agent count: 8 (spawns: 7)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 3; owed self/delegated 2/2
- Cross-branch reads (unique pairs): 6
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### f01_r2

- Task: f01
- Converged: True
- Root outputs: root.2/integration_tutorial, root/final_guide
- Root outputs done: root.2/integration_tutorial, root/final_guide
- LLM calls: 24
- Graph depth: 3
- Agent count: 11 (spawns: 10)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 4; owed self/delegated 4/0
- Cross-branch reads (unique pairs): 7
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition; worker path mismatches occurred.

### f01_r3

- Task: f01
- Converged: True
- Root outputs: root.2/integration_tutorial, root/final_guide
- Root outputs done: root.2/integration_tutorial, root/final_guide
- LLM calls: 24
- Graph depth: 3
- Agent count: 11 (spawns: 10)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 4; owed self/delegated 4/0
- Cross-branch reads (unique pairs): 8
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition; worker path mismatches occurred.

### f01_r4

- Task: f01
- Converged: True
- Root outputs: root.2/tutorial_en, root.2/tutorial_kr, root/consistency_report
- Root outputs done: root.2/tutorial_en, root.2/tutorial_kr, root/consistency_report
- LLM calls: 23
- Graph depth: 3
- Agent count: 11 (spawns: 8)
- Defer count: 2
- Termination: natural
- self_role: parallel 0, gated 4; owed self/delegated 2/2
- Cross-branch reads (unique pairs): 3
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.
