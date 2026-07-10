# E0 Summary

- Runs: 12
- Convergence: 10/12
- Schema agreement rate: 89.01% (81/91)
- Trigger fire errors: 0
- Ready-but-unfired triggers: 0
- Conflicts: 0
- Worker schema mismatches: 2
- Rail hits: 0 (none)
- Natural terminations: 12/12
- Cross-branch reads (unique agent,path pairs): 12 (event fallback: 24)
- self_role distribution: parallel 0, gated 25
- Interface self-fulfillment: 100.00% (16/16 owed paths taken by the parent's own self_role)

## Runs

### L1_r1

- Task: L1
- Converged: True
- Root outputs: root/explainer
- Root outputs done: root/explainer
- LLM calls: 2
- Graph depth: 0
- Agent count: 1 (spawns: 0)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 0; owed self/delegated 0/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### L1_r2

- Task: L1
- Converged: True
- Root outputs: root/explainer
- Root outputs done: root/explainer
- LLM calls: 2
- Graph depth: 0
- Agent count: 1 (spawns: 0)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 0; owed self/delegated 0/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### L1_r3

- Task: L1
- Converged: True
- Root outputs: root/explainer
- Root outputs done: root/explainer
- LLM calls: 2
- Graph depth: 0
- Agent count: 1 (spawns: 0)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 0; owed self/delegated 0/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### L2_r1

- Task: L2
- Converged: True
- Root outputs: root/comparative_report
- Root outputs done: root/comparative_report
- LLM calls: 9
- Graph depth: 1
- Agent count: 4 (spawns: 3)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 1; owed self/delegated 0/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### L2_r2

- Task: L2
- Converged: True
- Root outputs: root/comparative_report
- Root outputs done: root/comparative_report
- LLM calls: 9
- Graph depth: 1
- Agent count: 4 (spawns: 3)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 1; owed self/delegated 0/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### L2_r3

- Task: L2
- Converged: True
- Root outputs: root/comparative_report
- Root outputs done: root/comparative_report
- LLM calls: 9
- Graph depth: 1
- Agent count: 4 (spawns: 3)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 1; owed self/delegated 0/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a shallow graph matching the broad human decomposition.

### L3_r1

- Task: L3
- Converged: False
- Root outputs: root/final_book
- Root outputs done: (none)
- LLM calls: 30
- Graph depth: 2
- Agent count: 16 (spawns: 15)
- Defer count: 1
- Termination: natural
- self_role: parallel 0, gated 5; owed self/delegated 4/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Did not converge to the declared root output within rails.

### L3_r2

- Task: L3
- Converged: False
- Root outputs: root/final_book
- Root outputs done: (none)
- LLM calls: 30
- Graph depth: 2
- Agent count: 16 (spawns: 15)
- Defer count: 1
- Termination: natural
- self_role: parallel 0, gated 5; owed self/delegated 4/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Did not converge to the declared root output within rails.

### L3_r3

- Task: L3
- Converged: True
- Root outputs: root/field_guide_final
- Root outputs done: root/field_guide_final
- LLM calls: 35
- Graph depth: 2
- Agent count: 16 (spawns: 15)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 5; owed self/delegated 4/0
- Cross-branch reads (unique pairs): 0
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition; worker path mismatches occurred.

### L4_r1

- Task: L4
- Converged: True
- Root outputs: root.5/canonical_terminology_standard, root/final_guide
- Root outputs done: root.5/canonical_terminology_standard, root/final_guide
- LLM calls: 28
- Graph depth: 3
- Agent count: 13 (spawns: 12)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 3; owed self/delegated 2/0
- Cross-branch reads (unique pairs): 4
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition; worker path mismatches occurred.

### L4_r2

- Task: L4
- Converged: True
- Root outputs: root.5/canonical_terminology_standard, root/final_guide
- Root outputs done: root.5/canonical_terminology_standard, root/final_guide
- LLM calls: 26
- Graph depth: 3
- Agent count: 13 (spawns: 12)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 3; owed self/delegated 2/0
- Cross-branch reads (unique pairs): 4
- Qualitative: Converged with a recursive multi-level graph matching the broad human decomposition.

### L4_r3

- Task: L4
- Converged: True
- Root outputs: root.5/canonical_terminology_standard, root/drafting_plan
- Root outputs done: root.5/canonical_terminology_standard, root/drafting_plan
- LLM calls: 12
- Graph depth: 1
- Agent count: 6 (spawns: 5)
- Defer count: 0
- Termination: natural
- self_role: parallel 0, gated 1; owed self/delegated 0/0
- Cross-branch reads (unique pairs): 4
- Qualitative: Converged with a shallow graph matching the broad human decomposition.
