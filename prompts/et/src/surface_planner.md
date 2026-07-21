## Additional tools available to you

- `spawn` args `{task, capsule, initial_refs?}` — create a worker agent
  immediately. It receives your `task` text and your `capsule` (2–4
  sentences: why this work exists, what you need back, constraints, how
  it serves the ROOT GOAL), and starts with no context beyond that plus
  the shared memory — point it at concrete paths via `initial_refs`.
  Workers cannot spawn or author rules; they report by writing to memory
  and declaring done/failed, which you can observe via the catalog and
  `state(...)` conditions in `wait`.
