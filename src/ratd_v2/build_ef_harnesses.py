"""Build auditable EF harnesses by exact surgery on frozen ET Arm S."""
from __future__ import annotations

import hashlib
from pathlib import Path

MARK = "# YOUR ACTIVATION MODEL"
TERMINAL = """- End the ops list with exactly one of: `done` / `fail`. If you end with
  neither: an emission that changed state (wrote, committed, spawned,
  added rules) is re-activated automatically; an emission that only READ
  is re-activated once, and a second consecutive read-only emission
  records you done — pure observation cannot progress by re-activation,
  because nothing you learned survives unless you persist it. Declare
  `done` explicitly when your task is finished.
"""
CHAIN = """- If you are re-activated, your next activation receives the results of
  THIS emission's tool calls — that is your only delivery channel besides
  memory. Reads you emit now are answered then.
"""
NOPOLL = """- Never poll. Repeating a search or read round after round to watch for
  a change burns your budget; a circuit rule costs nothing while its
  condition is false and fires exactly when it becomes true.
"""

class BuildError(RuntimeError): pass

def bullet(text: str, prefix: str, new: str | None = None) -> str:
    lines = text.splitlines(keepends=True)
    hits = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(hits) != 1: raise BuildError(f"expected one {prefix!r}, found {len(hits)}")
    i, j = hits[0], hits[0] + 1
    while j < len(lines) and lines[j].startswith("  "): j += 1
    return "".join(lines[:i] + ([] if new is None else [new]) + lines[j:])

def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1: raise BuildError(f"expected one occurrence: {old!r}")
    return text.replace(old, new)

def spawn_only(text: str) -> str:
    text = bullet(text, "- End the ops list", TERMINAL)
    text = bullet(text, "- If you chain", CHAIN)
    text = once(text, "persist, chain, act on what arrives.", "persist, act on what arrives.")
    text = bullet(text, "- `wait` args")
    text = bullet(text, "- `continue` args")
    text = bullet(text, "- Never poll.", NOPOLL)
    text = once(text, "(spawn an agent, or resume a waiting one)", "(spawn an agent)")
    return once(text, '` or `{"type": "resume", "agent_id": "..."}`.', "`.")

def frame(text: str, value: str) -> str:
    if MARK not in text: raise BuildError(f"missing {MARK}")
    return value.rstrip() + "\n\n" + text[text.index(MARK):]

def main() -> int:
    base = Path("prompts/et/harness_stig.md").read_text()
    src, out = Path("prompts/ef/src"), Path("prompts/ef")
    router = (src / "frame_router.md").read_text()
    router_so = (src / "frame_router_spawnonly.md").read_text()
    cells = {"nn": base, "rn": frame(base, router), "ns": spawn_only(base),
             "rs": frame(spawn_only(base), router_so)}
    if cells["nn"] != base: raise BuildError("nn drifted from ET baseline")
    for key in ("ns", "rs"):
        if any(s in cells[key] for s in ("`wait`", "`continue`", '"type": "resume"')):
            raise BuildError(f"{key} still documents revival")
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for key, content in cells.items():
        path = out / f"harness_{key}.md"; path.write_text(content)
        digest = hashlib.sha256(content.encode()).hexdigest()
        print(f"wrote {path} {digest}"); manifest.append(f"{digest}  {path}")
    (out / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n")
    return 0

if __name__ == "__main__": raise SystemExit(main())
