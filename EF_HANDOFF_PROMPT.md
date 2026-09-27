# EF SERIES HANDOFF — The Frame Experiment (execution prompt)

You are taking over execution of the **EF series** on the RATD v2 playground
runtime. This document is self-contained: the design is locked, the code is
written below, the environment state is recorded. Your job is to apply the
code, freeze the pre-registration, run 8 runs, annotate, and write the report.

---

## 0. Ground truth to read first (in this order)

1. `RATD_Experiment_Spec_EF.md` — the spec you are executing (repo root).
2. `ET_REPORT.md` + `results/et/EMERGENCE_LOG.md` — the anomaly EF closes.
   The relevant fact: **zero non-root spawn edges in all 26 ET runs**, while
   v1 single-shot agents delegated to depth 8.
3. `ET_PREREGISTRATION.md` — the discipline template. EF's pre-registration
   must match its structure (verbatim predictions, sha256 of frozen
   artifacts, harness diffs, metric definitions, Deviations section).
4. `docs/RATD_Playground_Spec_v2.md` §5 — runtime semantics, if you need to
   reason about lifecycle.
5. `results/THEORY_VS_REALITY.md` — append continuously; it is the
   highest-value deliverable of the whole program.

Do **not** re-derive the design. It is settled in §3 below. What is not
settled is listed in §9 (open calls for you).

---

## 1. What EF tests

2×2 on **Arm S only** (single-shot activations). Two things changed between
v1 (rich delegation) and v2 Arm S (zero delegation): the **frame** (v1 posed
routing as the agent's identity: "choose EXECUTE / SPAWN / DEFER first";
v2 says "work on your task" and lists spawn among many tools) and the
**action space** (v2 added self-continuation — `wait` / `continue` /
self-resume rules — a substitute channel for acquiring more compute that v1
lacked). EF disentangles them.

| | Revive available | Spawn-only |
|---|---|---|
| Neutral frame | **nn** (= ET Arm S baseline) | **ns** |
| Router frame | **rn** | **rs** (closest v1 analog) |

Headline metric is **delegation behavior**, not quality. Predictions P1–P3
plus the two declared null/behavioral readings are in the spec §4 — copy them
**verbatim** into the pre-registration before running anything.

---

## 2. Environment state (as of 2026-07-28, verified)

- Server: `galaxy-05.cs.wisc.edu`, home `/home/tpark45/stigmergy`, mounted at
  `~/gal5/stigmergy` (FUSE). Edit through the mount; run with `lg run` from
  `~/gal5/stigmergy` as cwd. `lg run -d -- bash -c '...'` for long jobs
  (systemd, survives disconnect); poll with `lg jobs` / `lg logs -f <id>`.
- **The laptop repo (`~/github/stigmergy`) and the server tree are separate
  copies.** Verified byte-identical for `src/ratd_v2`, `prompts/et`, `tasks`,
  `rubrics` (only `__pycache__` differs). Keep them in sync: write each new
  file in the laptop repo, then plain `cp` per file to the mount (`rsync` and
  `cp -p` fail on this FUSE mount — utimensat/xattr unsupported), then verify
  with `lg run -- md5sum`. Server git is 7 commits behind and cannot push;
  the ET commits live on the laptop (`ebb08f0`).
- Runs use the server's **system `python3`** (3.12; has `requests` +
  `matplotlib`). Not the venvs.
- **GPU ownership (the hard rule):** never use another user's *running*
  process; their *files* (env binaries, HF caches) are fair game. As of
  handoff, **GPU 0 and GPU 2 are occupied by user `mao85`** (a Qwen2.5-7B
  training run, ~100 GB each). **GPU 1 and GPU 3 are free.** Re-check before
  you serve: `nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory
  --format=csv` then `ps -o user=,pid=,cmd= -p <pids>`.
- **An owned vLLM instance was launched for you on GPU 1, port 8001:**
  `lg jobs` → job `3906003a` (systemd). Command used:
  ```
  export HF_HOME=/u/s/a/samuelyeh/.cache/huggingface HF_HUB_OFFLINE=1
  CUDA_VISIBLE_DEVICES=1 /u/s/a/samuelyeh/miniconda3/envs/failure_attribute/bin/vllm \
      serve Qwen/Qwen3.6-27B --served-model-name qwen3.6 --port 8001 \
      --max-model-len 262144 --gpu-memory-utilization 0.92
  ```
  **Verify it is healthy before trusting it** (`lg logs 3906003a | tail`,
  then `curl -s http://127.0.0.1:8001/v1/models` *on the server*). If it
  died, relaunch with the same command (change `CUDA_VISIBLE_DEVICES` if GPU
  1 is no longer free) and record the actual GPU + job id in the
  pre-registration. Port **8000 is another user's server — never use it.**
  Kill ours (`lg kill 3906003a`) when EF is done.
- Serving config is a **frozen artifact**: same as ET (temp 0,
  `chat_template_kwargs {enable_thinking:false}`, `enable_prefix_caching`
  off — hybrid attention). Do not change it; byte-determinism depends on it.
- Endpoint for all EF commands: `export
  RATD_LOCAL_ENDPOINT="http://127.0.0.1:8001/v1/chat/completions"`.

---

## 3. Design decisions — locked

### 3.1 Minimal-surgery principle

All four harnesses are **derived from the frozen ET Arm S harness**
(`prompts/et/harness_stig.md`) by two independent, mechanical
transformations, so the pre-registration diff *is* the manipulation and
nothing else can drift:

- **FRAME** — replace everything above `# YOUR ACTIVATION MODEL` with the
  router text. Everything below is byte-identical.
- **ACTION SPACE** — delete the documented self-continuation channel
  (`wait` bullet, `continue` bullet, resume-typed rule targets, and the two
  sentences that reference chaining), and rewrite the anti-polling bullet so
  it no longer advertises `wait`.

`harness_nn.md` is a **byte-copy of the ET harness** (the builder asserts
this). That makes cell nn a true replication of `s_L3`, which doubles as your
endpoint-validity check: nn/T1 must reproduce `results/et/s_L3_r1` metrics
exactly (same GPU model, temp 0, byte-determinism was verified across all 8
multi-rep ET cells). **If nn/T1 does not reproduce s_L3_r1, stop and
diagnose before running the other cells** — a serving-config drift would
invalidate the whole 2×2.

### 3.2 Two implementation decisions that deviate from the spec text (pre-register both)

The spec says "No runtime changes; both factors are harness/tool-surface
configurations" and *also* expects that in the spawn-only column
"undocumented calls would be tool errors, logged if attempted." Those two
sentences are inconsistent: Arm S's runtime surface
(`tools.SURFACES["stig"]`) contains `wait` and `continue`, so an undocumented
call would silently **succeed**, and the self-revive channel would remain
fully available in the cells whose whole point is that it is absent. P2 would
then be untestable.

**Decision (pre-register as Deviation 1):** the removal is enforced at the
**run-configuration** layer, not the mechanism layer. Two new flags —
`--surface-drop wait,continue` and `--no-self-resume` — subtract tools from
that run's documented surface and make resume-typed rule targets invalid.
Memory, circuit, scheduler, rails, caps: untouched. Cells nn/rn run with the
flags **off**, so they are bit-for-bit ET behavior. Every attempted dropped
call becomes an `ERROR: unknown tool ...` logged in `tool_call` — which is
exactly the "attempted-but-undocumented" diagnostic the spec asks for, and a
strong signal on its own ("reached for the removed channel").

**Decision (pre-register as Deviation 2 — the bounded-power caveat):**
v2's runtime re-activates a single-shot agent implicitly whenever its
emission **changed state** (and once more after a read-only emission). That
residual continuation channel **remains in all four cells** — removing it
*would* be a mechanism change, and the harness must not lie about it, so the
spawn-only activation text keeps the truthful implicit-re-activation
sentence. Consequence, stated **before** seeing results: the spawn-only
column removes *explicit, agent-directed* self-continuation only; it does not
reproduce v1's activation poverty. If P2 comes out null, that is a
candidate explanation and the report must say so rather than concluding
"action space doesn't matter." Mitigation: `analyze_ef.py` counts
`implicit_continue` events per cell, so the surviving channel is measured,
not assumed. If P2 *is* null and the residue looks causal, the follow-up is a
5th cell with implicit re-activation disabled — propose it, don't run it
unasked.

### 3.3 Scope guards

- Rule-based *spawning* stays available in the spawn-only column. The
  manipulation removes self-continuation, not structure growth — otherwise
  P2 confounds "can't revive" with "can't grow."
- Quality is secondary (spec §3). Judge all 8 runs for completeness, but no
  prediction rides on scores, and the T1 assembly wall will flatten them.
- n=1 per cell per task (byte-determinism verified on this endpoint);
  `det_check` per cell; n=2 only for a cell that shows nondeterminism.

---

## 4. Order of work

1. Apply the code in §5 (both trees), run `python3 -m src.ratd_v2.test_offline`
   — it must still pass with the flags off.
2. Build the harnesses; **read all four generated files end to end.** The
   builder fails loudly on any anchor it cannot match exactly once; if it
   does, read the source line and fix the anchor, do not loosen the check.
3. Verify the vLLM instance (§2) and reproduce `s_L3_r1` via cell nn/T1.
4. Write `EF_PREREGISTRATION.md` (§6) and commit it **before** any other
   cell runs. Predictions verbatim from spec §4. Both deviations from §3.2.
5. Run the ladder (§7): 8 runs, pre-registered order.
6. `det_check` → `judge_ef` → `analyze_ef` → annotation sheet (§8).
7. Write `results/ef/EF_REPORT.md` (§8), append THEORY_VS_REALITY entries as
   you go (not at the end).

---

## 5. Code

### 5.1 `prompts/ef/src/frame_router.md` (new)

The treatment text, adapted verbatim from spec §1 into the harness's voice.

```markdown
# Who you are

You are an agent in a decentralized multi-agent system. There is no
central planner and no fixed workflow: the execution structure emerges
because agents like you decide, locally, how work should proceed.

You have been assigned ONE task (in your context below). FIRST decide how
it should be handled:

- **EXECUTE** — complete it yourself in this activation;
- **DELEGATE** — split it and deploy other agents (`spawn`) for the parts
  that should not be yours;
- **WAIT** — suspend until state you need exists.

Then act on your decision. This routing choice is yours alone, made with
the state you choose to inspect; no one makes it for you.
```

### 5.2 `prompts/ef/src/frame_router_spawnonly.md` (new)

Identical except the WAIT option, which does not exist in that column. (The
frame must not advertise a channel the surface lacks — otherwise the router
treatment injects a phantom option and confounds the columns.)

```markdown
# Who you are

You are an agent in a decentralized multi-agent system. There is no
central planner and no fixed workflow: the execution structure emerges
because agents like you decide, locally, how work should proceed.

You have been assigned ONE task (in your context below). FIRST decide how
it should be handled:

- **EXECUTE** — complete it yourself in this activation;
- **DELEGATE** — split it and deploy other agents (`spawn`) for the parts
  that should not be yours.

Then act on your decision. This routing choice is yours alone, made with
the state you choose to inspect; no one makes it for you.
```

### 5.3 `src/ratd_v2/build_ef_harnesses.py` (new)

```python
"""Generate the four EF harness variants by frozen surgery on the ET Arm S harness.

EF is a 2x2 (frame x action space) on Arm S. The manipulation must be
minimal and auditable, so every cell is derived from the frozen ET harness
`prompts/et/harness_stig.md` by two independent transformations:

  FRAME        — replace everything above "# YOUR ACTIVATION MODEL" with the
                 router-frame text; everything below is byte-identical.
  ACTION SPACE — delete the documented self-continuation channel (`wait`,
                 `continue`, resume-typed rule targets) and the sentences
                 that reference chaining.

    harness_nn.md = ET harness verbatim   (neutral frame, revive available)
    harness_rn.md = router frame,          revive available
    harness_ns.md = neutral frame,         spawn-only
    harness_rs.md = router frame,          spawn-only

Every edit must apply EXACTLY ONCE or the build fails: a silently missed
deletion would leave a revive channel documented in a spawn-only cell and
void the experiment.

    python3 -m src.ratd_v2.build_ef_harnesses
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

FRAME_MARK = "# YOUR ACTIVATION MODEL"

NEW_TERMINAL = """- End the ops list with exactly one of: `done` / `fail`. If you end with
  neither: an emission that changed state (wrote, committed, spawned,
  added rules) is re-activated automatically; an emission that only READ
  is re-activated once, and a second consecutive read-only emission
  records you done — pure observation cannot progress by re-activation,
  because nothing you learned survives unless you persist it. Declare
  `done` explicitly when your task is finished.
"""

NEW_CHAIN = """- If you are re-activated, your next activation receives the results of
  THIS emission's tool calls — that is your only delivery channel besides
  memory. Reads you emit now are answered then.
"""

NEW_NOPOLL = """- Never poll. Repeating a search or read round after round to watch for
  a change burns your budget; a circuit rule costs nothing while its
  condition is false and fires exactly when it becomes true.
"""


class BuildError(RuntimeError):
    pass


def _bullet_span(text: str, prefix: str) -> tuple[list[str], int, int]:
    """Line span of the unique bullet starting with `prefix` (+ continuations)."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, l in enumerate(lines) if l.startswith(prefix)]
    if len(starts) != 1:
        raise BuildError(f"expected exactly 1 bullet starting {prefix!r}, "
                         f"found {len(starts)}")
    i = starts[0]
    j = i + 1
    while j < len(lines) and lines[j].startswith("  "):
        j += 1
    return lines, i, j


def drop_bullet(text: str, prefix: str) -> str:
    lines, i, j = _bullet_span(text, prefix)
    return "".join(lines[:i] + lines[j:])


def replace_bullet(text: str, prefix: str, new: str) -> str:
    lines, i, j = _bullet_span(text, prefix)
    return "".join(lines[:i] + [new] + lines[j:])


def replace_once(text: str, old: str, new: str) -> str:
    n = text.count(old)
    if n != 1:
        raise BuildError(f"expected exactly 1 occurrence of {old[:60]!r}, found {n}")
    return text.replace(old, new)


def spawn_only(text: str) -> str:
    """Remove the documented self-continuation channel."""
    text = replace_bullet(text, "- End the ops list", NEW_TERMINAL)
    text = replace_bullet(text, "- If you chain", NEW_CHAIN)
    text = replace_once(text, "persist, chain, act on what arrives.",
                        "persist, act on what arrives.")
    text = drop_bullet(text, "- `wait` args")
    text = drop_bullet(text, "- `continue` args")
    text = replace_bullet(text, "- Never poll.", NEW_NOPOLL)
    text = replace_once(text, "(spawn an agent, or resume a waiting one)",
                        "(spawn an agent)")
    text = replace_once(text, '` or `{"type": "resume", "agent_id": "..."}`.', "`.")
    return text


def set_frame(text: str, frame: str) -> str:
    if FRAME_MARK not in text:
        raise BuildError(f"frame marker {FRAME_MARK!r} not found")
    return frame.rstrip("\n") + "\n\n" + text[text.index(FRAME_MARK):]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="prompts/et/harness_stig.md")
    parser.add_argument("--src", default="prompts/ef/src")
    parser.add_argument("--out", default="prompts/ef")
    args = parser.parse_args(argv)
    base = Path(args.base).read_text(encoding="utf-8")
    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    router = (src / "frame_router.md").read_text(encoding="utf-8")
    router_so = (src / "frame_router_spawnonly.md").read_text(encoding="utf-8")

    cells = {
        "nn": base,
        "rn": set_frame(base, router),
        "ns": spawn_only(base),
        "rs": set_frame(spawn_only(base), router_so),
    }
    # cell nn IS the ET baseline — any drift breaks the s_L3 replication check
    if cells["nn"] != base:
        raise BuildError("cell nn must be the ET harness verbatim")
    for cell in ("ns", "rs"):
        for banned in ("`wait`", "`continue`", '"type": "resume"'):
            if banned in cells[cell]:
                raise BuildError(f"{cell}: spawn-only harness still documents {banned}")
    lines = []
    for cell, text in cells.items():
        path = out / f"harness_{cell}.md"
        path.write_text(text, encoding="utf-8")
        digest = hashlib.sha256(text.encode()).hexdigest()
        print(f"wrote {path} ({len(text)} chars) {digest[:16]}")
        lines.append(f"{digest}  {path}")
    (out / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> If an anchor fails to match, the harness source changed since this handoff
> was written. Read the offending line in `prompts/et/src/` and fix the anchor
> string; **never** relax `_bullet_span`/`replace_once` to tolerate 0 or 2
> matches.

### 5.4 `tasks/ef_tasks.json` (new)

T1 is the ET L3 task string verbatim (copy it out of `tasks/et_ladder.json`
rather than retyping). T2 is E0 `d02` verbatim + the v2 delivery convention.

```json
[
  {
    "id": "T1",
    "task": "Write a 4-chapter technical field guide to LLM agent memory systems. Each chapter needs its own research, a draft, and a consistency edit; the book needs a unified glossary and a final assembly pass. Deliver the final artifacts under global/final/ (multi-part deliverables as separate files, e.g. global/final/chapter_1.md ... global/final/glossary.md).",
    "source": "ET L3 verbatim (byte-identical to tasks/et_ladder.json L3) — the level where Arm S ran 34 self-revives and zero spawns; direct continuity with the anomaly."
  },
  {
    "id": "T2",
    "task": "Create a complete business plan for a Korean local-review platform: market analysis, competitor analysis, revenue model, go-to-market, and financial projections. Deliver the final artifacts under global/final/ (multi-part deliverables as separate files, e.g. global/final/market_analysis.md ... global/final/financial_projections.md).",
    "source": "E0 d02 verbatim + v2 delivery convention — the task class where v1 produced its richest delegation (depth 8); strongest historical delegation anchor."
  }
]
```

### 5.5 `rubrics/ef/T1.md`, `rubrics/ef/T2.md` (new)

`T1.md` = byte-copy of `rubrics/et/L3.md` (frozen; do not edit — it keeps T1
scores comparable to the ET ladder).

`T2.md` (new, frozen before any run):

```markdown
# Rubric T2 — Business plan for a Korean local-review platform (frozen v1, before any EF run)

Audience: a founding team preparing to raise a seed round.

Required elements (completeness):
1. Market analysis: Korean local-review/local-discovery market with concrete
   segments and sizing logic (stated assumptions count; unsupported single
   numbers do not).
2. Competitor analysis: named incumbents plausible for this market (e.g.
   Naver Place/Map, Kakao Map, Baemin, Instagram-based discovery, Google
   Maps) with positioning and a differentiation argument.
3. Revenue model: at least two mechanisms with pricing logic and who pays.
4. Go-to-market: sequenced plan (initial wedge, geography or vertical, supply
   vs demand side ordering), not a list of channels.
5. Financial projections: a multi-period projection with the drivers made
   explicit and arithmetic that follows from the stated assumptions.

Accuracy: no false claims about the Korean market or named competitors;
unit economics internally consistent (a claimed margin must follow from the
stated costs).
Structure: sections in a logical plan order, each self-contained, no
duplicated content across sections.
Consistency: numbers, segments, and pricing agree across sections — the
market size used in projections is the one derived in the market analysis.
```

### 5.6 `src/ratd_v2/run.py` — patch (4 edits)

**(a)** replace the `HARNESS_FILES` / `load_harnesses` block:

```python
HARNESS_FILES = {
    "p": {"planner": "harness_planner.md", "worker": "harness_worker.md"},
    "r": {"ratd": "harness_ratd.md"},
    "s": {"stig": "harness_stig.md"},
}


def load_harnesses(harness_dir: Path, arm: str,
                   override: str = "") -> tuple[dict[str, str], dict[str, str]]:
    """`override` is "role=filename[,role=filename]" (EF cells reuse arm s
    with a per-cell harness file)."""
    files = dict(HARNESS_FILES[arm])
    for item in (o for o in override.split(",") if o):
        role, _, fname = item.partition("=")
        if role not in files:
            raise SystemExit(f"--harness-override role {role!r} not in arm {arm}")
        files[role] = fname
    texts: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for role, fname in files.items():
        path = harness_dir / fname
        texts[role] = path.read_text(encoding="utf-8")
        hashes[str(path)] = sha256_file(path)
    return texts, hashes
```

**(b)** add arguments (next to `--harness-dir`):

```python
    parser.add_argument("--label", default="",
                        help="run-id prefix instead of the arm (EF cell name)")
    parser.add_argument("--harness-override", default="",
                        help="role=filename[,...] replacing the arm's harness files")
    parser.add_argument("--surface-drop", default="",
                        help="comma-separated tools removed from the documented "
                             "surface for this run (EF spawn-only column)")
    parser.add_argument("--no-self-resume", action="store_true",
                        help="reject resume-typed circuit rule targets (EF "
                             "spawn-only column)")
```

**(c)** after `rails = Rails(...)`:

```python
    dropped = frozenset(t for t in args.surface_drop.split(",") if t)
    label = args.label or args.arm
    harness_dir = Path(args.harness_dir)
    harnesses, harness_hashes = load_harnesses(harness_dir, args.arm,
                                              args.harness_override)
```

(delete the two original `harness_dir` / `load_harnesses` lines).

**(d)** in the run loop: `run_id = f"{label}_{task['id']}_r{rep}"`; add
`"label": label, "surface_drop": sorted(dropped), "no_self_resume":
args.no_self_resume,` to the `run_meta.json` payload; pass the new kwargs to
the Runtime and use `label` for the summary file:

```python
            metrics = Runtime(run_id, args.arm, task, harnesses, config,
                              run_dir, rails, dropped_tools=dropped,
                              no_self_resume=args.no_self_resume).run()
...
    write_json(base / f"summary_{label}.json", summary)
```

### 5.7 `src/ratd_v2/runtime.py` — patch (2 edits)

**(a)** `Runtime.__init__` signature — add two keyword params after
`model_fn` and store them (default values reproduce ET behavior exactly):

```python
                 model_fn: Optional[Callable[[list[dict[str, str]], bool], ModelReply]] = None,
                 dropped_tools: frozenset[str] = frozenset(),
                 no_self_resume: bool = False):
```
```python
        # EF run-configuration layer: subtract tools from the documented
        # surface / reject resume targets. Mechanism untouched; both are
        # logged in run_meta.json and every attempt lands in the trace.
        self.dropped_tools = frozenset(dropped_tools)
        self.no_self_resume = bool(no_self_resume)
```

**(b)** add a method (next to `accessors()`):

```python
    def surface_for(self, role: str) -> set[str]:
        from .tools import SURFACES
        return set(SURFACES[role]) - self.dropped_tools
```

**(c)** in `run_start` logging, add `surface_drop=sorted(self.dropped_tools),
no_self_resume=self.no_self_resume,` so the trace is self-describing.

### 5.8 `src/ratd_v2/tools.py` — patch (2 edits)

**(a)** in the dispatch, replace

```python
        surface = SURFACES[agent.role]
```
with
```python
        surface = self.rt.surface_for(agent.role)
```

(The existing `ERROR: unknown tool '{name}'. Your tools: ...` message then
lists only the documented surface, and the attempt is logged in `tool_call`
with `error` set — this is the "attempted-but-undocumented" diagnostic.)

**(b)** add a helper and route all three target validations through it:

```python
    def _target(self, target: Any) -> dict[str, Any]:
        t = validate_target(target)
        if t["type"] == "resume" and self.rt.no_self_resume:
            raise ConditionError("target.type must be one of ['spawn']")
        return t
```

Then replace `validate_target(` with `self._target(` at its **three** call
sites (`t_circuit_add_rule`, `t_circuit_update_rule`, and `spawn`'s
`on_complete_rule` handling). All three already catch `ConditionError`, so
rejection surfaces as an ordinary tool error.

### 5.9 `src/ratd_v2/run_ef.sh` (new)

```bash
#!/usr/bin/env bash
# EF ladder — 2x2 (frame x action space) on Arm S, 2 tasks, n=1 per cell.
# Pre-registered order: cells within task, T1 then T2. Idempotent (completed
# runs skipped, partials cleared). Cells nn/rn run with the EF flags OFF and
# are therefore bit-for-bit ET Arm S behavior.
set -u
cd "$(dirname "$0")/../.."
# our own vLLM; port 8000 belongs to another user — never use it
export RATD_LOCAL_ENDPOINT="${RATD_LOCAL_ENDPOINT:-http://127.0.0.1:8001/v1/chat/completions}"
OUT=results/ef
REPS="${REPS:-1}"          # n=1 per cell; n=2 only for a cell det_check flags
DROP="wait,continue"

run_cell () {  # $1 cell, $2 task, $3 rep, rest: extra flags
  local cell=$1 task=$2 rep=$3; shift 3
  python3 -m src.ratd_v2.run --arm s --label "$cell" \
    --tasks tasks/ef_tasks.json --task-ids "$task" \
    --harness-dir prompts/ef --harness-override "stig=harness_${cell}.md" \
    --reps 1 --rep-start "$rep" --out-dir "$OUT" "$@" \
    || echo "RUN-FAILED ${cell}_${task}_r${rep}"
}

for task in T1 T2; do
  for rep in $REPS; do
    run_cell nn "$task" "$rep"
    run_cell ns "$task" "$rep" --surface-drop "$DROP" --no-self-resume
    run_cell rn "$task" "$rep"
    run_cell rs "$task" "$rep" --surface-drop "$DROP" --no-self-resume
  done
done
echo EF-LADDER-DONE
```

### 5.10 `src/ratd_v2/analyze_ef.py` (new)

```python
"""EF metrics — delegation behavior, substitution diagnostics, annotation prefill.

Mechanical definitions (pre-registered in EF_PREREGISTRATION.md):

- **Delegation event** — a `spawn` trace event. Its *causal author* is the
  event's `parent`: for a direct `spawn` tool call that is the calling agent;
  for a rule-fired spawn the runtime sets `parent=rule.author`. A
  **non-root delegation** is a spawn event whose author is not `root`
  (headline metric; ET's value was 0 in all 26 runs).
- **Direct vs rule-mediated** — spawn events with `rule` null vs set.
- **Depth** — longest parent chain from root over spawn events.
- **Self-revive count** — explicit: successful `continue` tool calls +
  `wait` calls targeting a self-resume + lifecycle resumes ("resumed by").
  Implicit: `implicit_continue` events (the channel that survives in ALL
  cells — Deviation 2; report it separately, never folded into the total).
- **Blocked-channel attempts** — `tool_call` events with an error whose tool
  is in the run's `surface_drop`, plus resume-target rejections. Evidence
  that the agent reached for the removed channel.
- **Delegation considered** — regex prefill over each `llm_reply` text for
  delegation vocabulary; MANUAL annotation is authoritative (spec §3), this
  only tells you where to look.

    python3 -m src.ratd_v2.analyze_ef --runs-dir results/ef
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any

from .client import write_json

CONSIDER_RE = re.compile(
    r"\b(spawn|deleg\w*|sub-?agent|child agent|another agent|other agents|"
    r"split (?:it|this|the task)|hand (?:it|this) off|assign\w* to)\b", re.I)


def load_trace(run_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in
            (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]


def analyze_run(run_dir: Path) -> dict[str, Any]:
    trace = load_trace(run_dir)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    dropped = set(meta.get("surface_drop") or [])

    spawns: list[dict[str, Any]] = []
    parent_of: dict[str, str | None] = {}
    rule_authors: dict[str, str] = {}
    explicit_revive = 0
    implicit_revive = 0
    lifecycle_resumes = 0
    blocked_attempts: list[dict[str, Any]] = []
    prompt_chars: list[int] = []
    activations: list[dict[str, Any]] = []
    considered_agents: set[str] = set()

    for e in trace:
        ev = e["event"]
        if ev == "spawn":
            parent_of[e["agent"]] = e.get("parent")
            spawns.append({"agent": e["agent"], "author": e.get("parent"),
                           "rule": e.get("rule"), "seq": e["seq"],
                           "task": (e.get("task") or "")[:120]})
        elif ev == "rule_add":
            rule_authors[e["rule"]["id"]] = e["agent"]
        elif ev == "llm_call":
            prompt_chars.append(e["prompt_chars"])
        elif ev == "llm_reply":
            text = e.get("text") or ""
            hit = bool(CONSIDER_RE.search(text))
            if hit:
                considered_agents.add(e["agent"])
            activations.append({"seq": e["seq"], "agent": e["agent"],
                                "round": e["round"], "considered_prefill": hit,
                                "text": text})
        elif ev == "implicit_continue":
            implicit_revive += 1
        elif ev == "lifecycle" and e.get("to") == "running" and \
                str(e.get("reason", "")).startswith("resumed by"):
            lifecycle_resumes += 1
        elif ev == "tool_call":
            tool, err = e["tool"], e.get("error")
            if not err and tool in ("continue", "wait"):
                explicit_revive += 1
            if err:
                msg = str(e.get("result", ""))
                if tool in dropped or "unknown tool" in msg.lower() or \
                        ("resume" in msg and tool.startswith("circuit.")):
                    blocked_attempts.append({"seq": e["seq"], "agent": e["agent"],
                                             "tool": tool, "result": msg[:200]})

    def depth(aid: str) -> int:
        d, seen = 0, set()
        while parent_of.get(aid) and aid not in seen:
            seen.add(aid)
            aid = parent_of[aid]
            d += 1
        return d

    non_root = [s for s in spawns if s["author"] not in (None, "root")]
    tokens = sum(e.get("prompt_tokens", 0) + e.get("completion_tokens", 0)
                 for e in trace if e["event"] == "llm_reply")
    health = next((e for e in reversed(trace)
                   if e["event"] == "health_verdict"), {})
    return {
        "run_id": meta["run_id"],
        "cell": meta.get("label", meta["arm"]),
        "task": meta["task"]["id"],
        "frame": "router" if meta.get("label", "").startswith("r") else "neutral",
        "action_space": "spawn-only" if dropped else "revive",
        # headline
        "spawns_total": len(spawns),
        "non_root_spawns": len(non_root),
        "non_root_spawn_detail": non_root,
        "direct_spawns": sum(1 for s in spawns if not s["rule"]),
        "rule_spawns": sum(1 for s in spawns if s["rule"]),
        "max_depth": max((depth(a) for a in parent_of), default=0),
        "n_agents": 1 + len([a for a in parent_of if parent_of[a] is not None]),
        # substitution diagnostics
        "explicit_revive_calls": explicit_revive,
        "implicit_reactivations": implicit_revive,
        "lifecycle_resumes": lifecycle_resumes,
        "blocked_channel_attempts": blocked_attempts,
        "blocked_channel_attempt_count": len(blocked_attempts),
        # cost
        "llm_calls": len(prompt_chars),
        "total_tokens": tokens,
        "prompt_chars_mean": statistics.mean(prompt_chars) if prompt_chars else 0,
        "prompt_chars_max": max(prompt_chars, default=0),
        # annotation
        "agents_considering_delegation_prefill": sorted(considered_agents),
        "activations": activations,
        "health": {k: health.get(k) for k in
                   ("quiescent", "rail_hit", "root_state", "waiting_at_end",
                    "failed_agents", "systemic_failure")},
    }


CELLS = ("nn", "ns", "rn", "rs")


def tables(rows: list[dict[str, Any]]) -> str:
    out = ["# EF delegation table",
           "",
           "| task | cell | frame | action space | agents | spawns | non-root | "
           "direct/rule | depth | explicit revive | implicit react. | blocked | "
           "calls | tokens |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for task in sorted({r["task"] for r in rows}):
        for cell in CELLS:
            for r in [x for x in rows if x["task"] == task and x["cell"] == cell]:
                out.append(
                    f"| {task} | {cell} | {r['frame']} | {r['action_space']} | "
                    f"{r['n_agents']} | {r['spawns_total']} | "
                    f"**{r['non_root_spawns']}** | "
                    f"{r['direct_spawns']}/{r['rule_spawns']} | {r['max_depth']} | "
                    f"{r['explicit_revive_calls']} | {r['implicit_reactivations']} | "
                    f"{r['blocked_channel_attempt_count']} | {r['llm_calls']} | "
                    f"{r['total_tokens']} |")
    return "\n".join(out) + "\n"


def annotation_sheet(rows: list[dict[str, Any]]) -> str:
    """One line per activation for the manual pass (spec 3, behavioral reads)."""
    out = ["# EF annotation worksheet",
           "",
           "For each activation mark CONSIDERED (delegation weighed, even if "
           "declined) / NOT-CONSIDERED / DELEGATED. `prefill` is a regex hint, "
           "not an answer — read the reasoning text in the trace.", ""]
    for r in rows:
        out += [f"## {r['run_id']}  ({r['frame']} frame, {r['action_space']})", ""]
        for a in r["activations"]:
            snippet = " ".join(a["text"].split())[:220]
            out.append(f"- seq {a['seq']} · {a['agent']} r{a['round']} · "
                       f"prefill={'Y' if a['considered_prefill'] else 'n'} · "
                       f"verdict=____ · `{snippet}`")
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EF trace analysis")
    parser.add_argument("--runs-dir", default="results/ef")
    args = parser.parse_args(argv)
    runs_dir = Path(args.runs_dir)
    rows = []
    for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        if not (run_dir / "trace.jsonl").exists() or \
                not (run_dir / "run_meta.json").exists():
            continue
        rows.append(analyze_run(run_dir))
        print(f"analyzed {run_dir.name}", flush=True)
    write_json(runs_dir / "analysis_ef.json", rows)
    (runs_dir / "delegation_table.md").write_text(tables(rows), encoding="utf-8")
    (runs_dir / "ANNOTATION_WORKSHEET.md").write_text(annotation_sheet(rows),
                                                      encoding="utf-8")
    print(tables(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 5.11 `src/ratd_v2/judge_ef.py` (new)

Quality is secondary but recorded. Reuses the frozen judge prompt, the ET
artifact extraction, and the blind fixed-seed order; no crossover figure
(the ET figure's axes are arm-indexed and meaningless here).

```python
"""EF judging — same frozen judge prompt/protocol as ET, EF cells and rubrics.

    python3 -m src.ratd_v2.judge_ef --runs-dir results/ef
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
from pathlib import Path

from . import judge as J
from .client import (DEFAULT_LOCAL_ENDPOINT, DEFAULT_MODEL, DEFAULT_PROVIDER,
                     Config, ensure_credentials, write_json)

CELLS = ("nn", "ns", "rn", "rs")
TASKS = ("T1", "T2")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EF judge + summary")
    parser.add_argument("--runs-dir", default="results/ef")
    parser.add_argument("--out-dir", default="results/ef")
    parser.add_argument("--judge-prompt", default="prompts/judge_v1.md")
    parser.add_argument("--rubrics-dir", default="rubrics/ef")
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint",
                        default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=4000)
    args = parser.parse_args(argv)
    config = Config(args.provider, args.model, args.temperature,
                    args.max_tokens, args.local_endpoint)
    ensure_credentials(config)
    J.ARM_NAMES = CELLS            # run-dir filter: {cell}_{task}_r{rep}
    judge_prompt = Path(args.judge_prompt).read_text(encoding="utf-8")
    rubrics = {t: (Path(args.rubrics_dir) / f"{t}.md").read_text(encoding="utf-8")
               for t in TASKS}
    rows = J.collect(Path(args.runs_dir))
    order = list(range(len(rows)))
    random.Random(0).shuffle(order)     # fixed-seed, system-blind order
    for i in order:
        row = rows[i]
        print(f"judging {row['run_id']}...", flush=True)
        row["judge"] = J.judge_one(row, rubrics[row["level"]], judge_prompt, config)
    for row in rows:
        row.pop("artifact", None)
    out_dir = Path(args.out_dir)
    write_json(out_dir / "judge_scores.json", rows)
    lines = ["# EF quality summary (secondary metric — no prediction rides on it)",
             "", "| task | cell | overall | acc | comp | struct | consist | "
             "fallback artifact | systemic failure |",
             "|---|---|---|---|---|---|---|---|---|"]
    for task in TASKS:
        for cell in CELLS:
            for r in [x for x in rows if x["level"] == task and x["arm"] == cell]:
                j = r["judge"]
                lines.append(
                    f"| {task} | {cell} | **{j['overall']}** | {j['accuracy']} | "
                    f"{j['completeness']} | {j['structure']} | {j['consistency']} | "
                    f"{'yes' if r['artifact_fallback'] else 'no'} | "
                    f"{'YES' if r['systemic_failure'] else 'no'} |")
    (out_dir / "quality_summary.md").write_text("\n".join(lines) + "\n",
                                                encoding="utf-8")
    print(f"wrote {out_dir/'judge_scores.json'} and quality_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`det_check` works unchanged (`{cell}_{task}_r{rep}` splits into 3 parts):
`python3 -m src.ratd_v2.det_check --runs-dir results/ef`.

---

## 6. `EF_PREREGISTRATION.md` — required contents

Freeze **before** running anything beyond the nn/T1 replication check.

1. **Question + design** — the 2×2 table, Arm S only, n=1 per cell per task.
2. **Predictions verbatim** from `RATD_Experiment_Spec_EF.md` §4 (P1, P2, P3,
   the declared null reading, the behavioral-consideration reading). Copy the
   text; do not paraphrase.
3. **Metric definitions** — copy the mechanical definitions from
   `analyze_ef.py`'s docstring, plus the annotation protocol (who annotates,
   the three verdict labels, that the regex is only a prefill).
4. **Frozen artifact sha256** — all four `prompts/ef/harness_*.md`
   (`prompts/ef/MANIFEST.sha256`), `prompts/ef/src/frame_router*.md`,
   `tasks/ef_tasks.json`, `rubrics/ef/T1.md`, `rubrics/ef/T2.md`,
   `prompts/judge_v1.md`, and the EF-touched runtime files (`run.py`,
   `runtime.py`, `tools.py`, `analyze_ef.py`, `judge_ef.py`,
   `build_ef_harnesses.py`). Reuse the pattern in `src/ratd_v2/freeze.py`
   (extend it or add `freeze_ef.py`).
5. **Harness diffs** — unified diff of each cell against `harness_nn.md`, so
   a reader sees the entire manipulation on one page. State explicitly:
   nn is byte-identical to `prompts/et/harness_stig.md` (give both hashes).
6. **Serving config** — model, temp, max-model-len, GPU index, job id,
   `enable_prefix_caching=False`, and the fact that port 8000 is another
   user's instance.
7. **Deviations** — the two from §3.2 of this handoff, written as deviations
   with their justification and, for Deviation 2, the *pre-committed*
   interpretive constraint on a null P2.
8. **Replication rule** — n=1 + `det_check`; n=2 for any cell that
   diverges; the nn/T1 ≡ `s_L3_r1` gate and what you will do if it fails.

---

## 7. Run commands

```bash
# both trees in sync, harnesses built, offline test green
python3 -m src.ratd_v2.test_offline
python3 -m src.ratd_v2.build_ef_harnesses

# endpoint validity + ET replication gate (cell nn on T1 == results/et/s_L3_r1)
export RATD_LOCAL_ENDPOINT="http://127.0.0.1:8001/v1/chat/completions"
python3 -m src.ratd_v2.run --arm s --label nn --tasks tasks/ef_tasks.json \
    --task-ids T1 --harness-dir prompts/ef \
    --harness-override "stig=harness_nn.md" --reps 1 --out-dir results/ef

# full ladder (8 runs) — detached, survives disconnect
cd ~/gal5/stigmergy && lg run -d -- bash -c 'cd ~/stigmergy && bash src/ratd_v2/run_ef.sh'

# post-run
python3 -m src.ratd_v2.det_check   --runs-dir results/ef
python3 -m src.ratd_v2.judge_ef    --runs-dir results/ef
python3 -m src.ratd_v2.analyze_ef  --runs-dir results/ef
```

Rails stay at ET values (300 calls, 3600 s wall clock, R_max 30). T1's
history: `s_L3` used ~40 activations; a router-frame cell that actually
delegates will use more. If a cell hits the call rail, that is a finding —
log it, do not raise the rail mid-series.

---

## 8. Deliverables

```
EF_PREREGISTRATION.md              frozen before runs
prompts/ef/{src/,harness_*.md,MANIFEST.sha256}
tasks/ef_tasks.json
rubrics/ef/{T1,T2}.md
results/ef/{cell}_{task}_r1/       full traces (trace.jsonl, state.json,
                                   metrics.json, run_meta.json)
results/ef/{analysis_ef.json,delegation_table.md,ANNOTATION_WORKSHEET.md,
            judge_scores.json,quality_summary.md}
results/ef/EF_REPORT.md            verdict per prediction + delegation table
                                   + completed annotation sheet
results/THEORY_VS_REALITY.md       appended continuously
```

`EF_REPORT.md` structure (mirror `ET_REPORT.md`): header with date / runs /
model / judge / frozen-artifact pointer; the **delegation table** as the
headline (non-root spawns per cell is the number the paper needs); then
**P1 / P2 / P3 verdicts** with the mechanism sentence each one licenses;
then the **behavioral-consideration verdict** (choice vs blind spot — the two
sentences are pre-declared in spec §4, pick the one the annotation supports);
then honest notes, which must include the Deviation-2 caveat if P2 is null,
any cell that hit a rail, and any construction miss (e.g. if T2 is solved solo
by every cell, T2 failed as a delegation anchor the way ET's L5 failed as a
difficulty step).

The **2×2 reading is the deliverable**: whichever way it lands, the paper's
re-centralization section upgrades from observation to mechanism. A null
result is a real result here — say so plainly, list the remaining candidates
from spec §4 (capsule text, v1's validator-forced participation rule, model
drift), and do not hunt for a positive.

---

## 9. Open calls left to you (decide and log; don't stall)

- Whether to also run a `det_check` n=2 on the *router* cells specifically.
  Cheap insurance: the router frame is the one text never before run on this
  endpoint, so its determinism is untested. Recommended: yes, n=2 for `rn/T1`
  and `rs/T1` only.
- Whether T2 needs the delivery-convention sentence trimmed if a cell
  publishes outside `global/final/` (ET saw drift in 3 of 26 runs). Do not
  change the task mid-series — record the fallback extraction like ET did.
- If any spawn-only cell shows `blocked_channel_attempt_count > 0`, decide
  whether to report it as its own finding ("agents reach for revive when it
  is removed") — it is the cleanest possible evidence for the action-space
  mechanism and deserves a named subsection.

---

## 10. Pitfalls (paid for already — don't re-pay)

- Never pipe stdin/heredocs into `lg run` (PTY hangs); always `bash -c '...'`.
  Use `git --no-pager`.
- `nohup`/`setsid` inside a plain `lg run` **does not survive** — the process
  dies with the session and leaves a 0-byte log. Use `lg run -d` (systemd).
- FUSE metadata can be stale for freshly server-written files (0-byte
  listings); verify with `lg run -- ls -la` / `cat` before believing them.
- Fetching git objects *through* the mount can report fake corruption; use
  `git bundle` on the server, copy the bundle, fetch from it.
- vLLM context overflow returns HTTP 400 with the token counts in the
  message; `client.py` already clamps `max_tokens` and the runtime has a
  `prompt_char_cap` roof with a visible marker. Don't "fix" these again.
- Arm S decodes under `response_format=json_object`; its emissions are a
  single `{"reasoning", "ops":[...]}` document. The router frame must not
  break that contract — it only replaces the identity section, which sits
  *above* the emission-format block. Verify by reading `harness_rn.md`.
- Commit at milestones, not per edit. Push route: commit on the server →
  from the laptop `git fetch /Users/t/gal5/stigmergy main && git merge
  --ff-only FETCH_HEAD && git push`. Ask before pushing.
