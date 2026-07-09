# RATD Feasibility Probe — Final Report

**Date:** 2026-07-09
**Scope:** the three kill-order questions of `RATD_Probe_Spec.md` (Q1–Q3)
**Model under test:** local `qwen3.6` via vLLM OpenAI-compatible endpoint
(`127.0.0.1:8000`), temperature 0, JSON-constrained decoding
**Verdict:** **Q1 YES · Q2 YES · Q3 YES** — the probe chain is closed.

---

## 1. Executive summary

A small local model, given only the RATD harness prompt, (Q1) routes
EXECUTE / SPAWN / DEFER correctly on 20/20 tasks single-shot; (Q2)
independently generates namespace/key strings that compose across agents
at 100% schema agreement; and (Q3) drives full recursive runs to
convergence 6/6 within safety rails, including a depth-2 task with
cross-level interface delegation and a defer/wake cycle.

Getting there surfaced two genuine architecture-level defects — not
prompt problems — both now fixed and documented: **interface orphaning**
(recursion + strict namespace isolation + trigger gating were jointly
inconsistent) and **dropped DEFERs** (the runtime implemented ΔC
semantics for SPAWN but not DEFER). These are the probe's most valuable
outputs beyond the verdicts themselves.

---

## 2. Q1 — Routing (Phase 1, no runtime)

20 tasks, one call each, scored against `RATD_Probe_Spec.md` §1.5
(pass bar: valid_json ≥ 19/20, action_match ≥ 16/20, mean decomposition
sanity ≥ 1.3, condition correctness ≥ 80%).

| Harness | valid_json | action_match | decomp | conditions | Result |
|---|---|---|---|---|---|
| v1 (original) | 13/20 | 13/20 | — | — | FAIL |
| v2 (formatting/DEFER/budget guidance) | 15/20 | 20/20 | 2.00 | 100% | FAIL (budget arithmetic) |
| v2 + repair loop (≤2 validator-feedback retries) | 20/20 | 20/20 | 2.00 | 100% | (declared, not the scored claim) |
| **v3 (fixed per-child budget)** | **20/20** | **20/20** | **2.00** | **100%** | **PASS, single-shot** |

Failure-mode trajectory: v1 failed on Markdown-fenced/truncated JSON and
two DEFER tasks routed as SPAWN (the model invented missing
prerequisites). v2 fixed both; the residual was purely **budget
arithmetic** — the model allocated the full budget B across children,
ignoring the k-reserve, despite worked examples. v3 removed the
arithmetic (fixed allocation patterns) and passed cleanly.

Routing judgment was never the bottleneck: action_match has been 20/20
since v2, across every configuration. Residual outside the bar:
namespace discipline 18/20 (two aggregator children declared their
output in the parent namespace) — an early signal of the interface
question that Phase 2 later forced.

Evidence: `results/phase1_v3_singleshot/` (passing run),
`results/phase1_singleshot/` (v2 single-shot), `results/phase1/`
(v2 with repair), `results/phase1/iteration_log.md` (full trajectory).

## 3. Q2 — Schema composition (Phase 2)

The Q2 headline metric is schema agreement: the fraction of
condition-referenced paths actually written by the producing agent at
the exact declared path, where producer and consumer generated the
string independently.

| Phase 2 iteration | Convergence | Schema agreement |
|---|---|---|
| harness_v3 baseline | 4/6 | 14/14 (100%) |
| harness_v4 | 3/6 | 26/31 (83.9%) |
| harness_v5 | 4/6 | 24/24 (100%) |
| **v5 + DEFER fix (final)** | **6/6** | **26/26 (100%)** |

The v4 dip was not string mismatch: the 5 missing agreements were
interface paths that *no agent was permitted to write* (see §5.1).
Whenever writing was legal, independently-generated strings matched —
including when the model drifted off the snake_case convention (it
consistently used `schema.json`, `backend_code.zip` on both sides of
each contract). One caveat on that last point: the two phases enforce
different path rules. Phase 1 scoring applies the full path grammar
(`PATH_RE`: snake_case keys, no dots) at four sites; the Phase 2
validator checks only namespace prefixes, never the grammar. So
`schema.json` would have failed Phase 1 and passed Phase 2 — the drift
is evidence that string *matching* is robust, not that the system
tolerates convention drift under enforcement; the grammar was silently
relaxed between phases. Zero write conflicts and zero trigger-fire
errors occurred in all 24 runs across all four iterations.

**Q2: YES.** String-level composition of trigger conditions across
independently-prompted agents is reliable at this scale.

## 4. Q3 — Recursive convergence (Phase 2)

Final configuration (`results/phase2_v5b/`): 3 tasks × 2 replicates,
all converged within rails (60 LLM calls, depth 6, 20 min — no rail
was ever hit):

| Task | Shape | Agents | Depth | LLM calls | Notes |
|---|---|---|---|---|---|
| t06 (vector-DB report) | parallel → synthesize | 5 | 1 | 10 | matched human decomposition, both reps |
| t15 (business plan) | 5 sections + gated integrator | 7 | 1 | 14 | both reps |
| t09 (todo app) | recursive, mixed seq/parallel | 8 | 2 | 13 | 1 defer/wake per run; interface delegated across levels |

t09 end-to-end exercises the whole circuit: root spawns four children
with data-dependency conditions; the backend child decomposes further
and delegates its parent-assigned interface (`root.2/api_spec.json`) to
a grandchild; that grandchild, blind to a sibling branch, DEFERs on the
memory it needs; the wake trigger fires (condition already true), the
woken agent gains visibility through its condition refs, writes the
inherited interface path, and unblocks the test agent. Cross-branch
reads — flagged in the theory as a Figure-1 candidate — show
memory-mediated coordination operating routinely, but the defensible
count is **26 unique (agent, path) pairs** across the final run set,
not the raw event counts (46 in metrics, 50 in traces): visibility is
relogged on every context build (route + worker), roughly doubling
event-level figures. Any future use of this metric should count unique
pairs.

**Q3: YES** — with the honest qualifier that depth ≤ 2 is what B=20
economics affords (see §6).

---

## 5. Findings beyond the verdicts

### 5.1 Interface orphaning (architecture defect, fixed)

A parent assigns a child an output path; every trigger downstream may
gate on it. If that child SPAWNs instead of EXECUTEs, it writes no data
itself — and namespace discipline forbade its children from writing
outside their own namespaces. The declared interface was structurally
unproducible, and every deep run died of it, deterministically.

Fix (harness_v5 + validator): parent-assigned output paths are a
*delegable contract* carried in the intention capsule. A spawning agent
must assign each owed path to exactly one subtask (normally its gated
integrator), and inherited interface paths are the single exception to
namespace discipline. The validator enforces coverage mechanically;
which subtask carries the interface remains the agent's choice.
Theory implication logged in `results/THEORY_VS_REALITY.md`.

### 5.2 Dropped DEFERs (runtime defect, fixed)

The runtime's DEFER branch only logged; the wake condition was never
installed as a trigger, so a deferring agent left the circuit forever.
The fix registers (wake_condition → same agent, re-enqueued with
condition = wake_condition). Two properties fall out by construction:
already-true wakes fire on the next trigger pass (no lost wakeup), and
the wake condition doubles as a **read grant** — the woken agent's
condition refs make exactly the memory it named visible. That coupling
(DEFER as both scheduling and visibility mechanism for cross-branch
dependencies) was not in the theory and is worth promoting into it.

### 5.3 Small-model capability split: judgment vs arithmetic

qwen3.6 handled every *semantic* judgment well — routing, decomposition
shape, dependency conditions, which subtask deserves the deep budget —
and could not reliably do *allocation arithmetic* (sum ≤ B − k), even
with worked examples. The working design keeps quantitative safety in
fixed patterns/rails and leaves semantic choice to the agent. This is a
capability boundary worth stating in the paper: budget *conservation*
is structural; budget *allocation* is an LLM capability assumption.

### 5.4 Conflict-as-feedback never fired

Theory §4 argues conflicts are inevitable and load-bearing. Zero
conflicts occurred in 24 runs. Untested, not falsified: 3–8 agents,
depth ≤ 2, and parent-declared interfaces are plausibly below the
conflict threshold. The scale experiment must measure conflict rate
explicitly; if it stays zero at depth 4–6 with wide fan-out, §4 needs
revisiting.

---

## 6. Declared deviations and threats to validity

- **Constrained decoding:** the local call uses
  `response_format: json_object`. JSON well-formedness is partly the
  inference server's doing; the claim that survives is semantic/
  structural validity, which is the model's.
- **Repair loops:** Phase 1's scored claim is single-shot (retries=0).
  The Phase 2 runtime allows up to 3 validation-feedback attempts per
  action — declared as a system component, consistent with the
  validator-as-type-checker stance.
- **Fixed budget tiers are rails, not intelligence** (see §5.3), and
  the depth limit is the tiers' doing, not pure economics: the v4/v5
  tier table caps reachable depth at 3 by construction (20 → 8 → 2),
  and the observed maximum was 2. Q3's "recursive" evidence is depth
  2 — the tier maximum in practice — and should not be attributed to
  B=20 alone.
- **One small model, temperature 0, n=2 replicates per task.**
  Deterministic replication is weak evidence of robustness; no
  cross-model check was run.
- **Process note:** early Phase 1 work briefly edited `harness_v1.md`
  in place and relied on a then-undeclared repair loop; both were
  corrected (versions restored/split, deviations declared) before any
  scored claim. First-run raw artifacts (13/20) were overwritten before
  output-dir versioning was adopted; those numbers survive only in the
  iteration log.

## 7. What this probe did NOT test

Async/parallel execution, Observers, conflict *resolution* (only
logging; none occurred), retrieval models (memory fits in context at
this scale), goal drift at depth (§5 of theory — depth 2 is too shallow
to measure), the crossover curve against a replanning central planner
(§3's headline experiment), and cost/latency comparisons.

## 8. Recommended next experiments (from theory §10)

1. **Crossover curve** — RATD vs a replanning central planner as task
   size/depth grows; measure quality, context tokens/decision, and
   conflict rate on the same axis.
2. **Budget economics** — free allocation with runtime clipping on a
   stronger model vs fixed tiers; scale B to afford depth ≥ 3 to make
   drift measurable.
3. **Drift at depth** — LLM-judge leaf outputs against root intent,
   parent-only vs parent+root anchoring (§5's falsifiable prediction).
4. **Conflict induction** — tasks engineered with hidden cross-branch
   dependencies to force the §4 mechanism to fire at all.

## 9. Artifact index

| Artifact | Location |
|---|---|
| Final Phase 1 pass | `results/phase1_v3_singleshot/` |
| Final Phase 2 pass | `results/phase2_v5b/` |
| All intermediate runs | `results/phase1*/`, `results/phase2*/` |
| Harness versions v1–v5 | `prompts/` (never overwritten) |
| Iteration log (full causal chain) | `results/phase1/iteration_log.md` |
| Theory-vs-reality entries | `results/THEORY_VS_REALITY.md` |
| Runner / runtime | `src/phase1.py`, `src/phase2.py` |
| Key commits | `1cd44d7` scaffold · `89f2f0c` Phase 1 pass · `83d3273` Phase 2 pass · `be7d8df` v3 baseline artifacts |
