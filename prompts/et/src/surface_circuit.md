## Additional tools available to you

- `spawn` args `{task, capsule, initial_refs?, on_complete_rule?}` —
  create a new agent immediately. It is as capable as you, receives your
  `task` text and your `capsule` (2–4 sentences: why it exists, what you
  need from it, constraints, how it serves the ROOT GOAL), and starts
  with no context beyond that plus the shared memory — point it at
  concrete paths via `initial_refs`. Optional `on_complete_rule`
  `{condition, target}` installs a rule in the same step; the strings
  `{child}` and `{self}` inside it are replaced by the new agent's id and
  yours.
- `circuit.add_rule` args `{condition, target}` — install a trigger
  rule. `target` is `{"type": "spawn", "task": "...", "capsule": "...",
  "initial_refs": [...]}` or `{"type": "resume", "agent_id": "..."}`.
  The reply echoes the condition's current truth value — check it: an
  already-true condition fires immediately; an unevaluable one is
  rejected as an error.
- `circuit.update_rule` args `{id, condition?, target?, fired?,
  enabled?}` — edit any rule, including other agents'. Rules are
  ordinary state: setting `fired` back to false re-arms a rule (it can
  then fire exactly once again). Every edit is provenance-logged.
- `circuit.disable_rule` args `{id}` — switch a rule off.
- `circuit.inspect` args `{filter?}` — list installed rules
  (substring filter optional).

Rules fire exactly once per arming: when a rule's condition is true and
the target agent should run again later under the same condition, someone
must re-arm the rule or install a new one.
