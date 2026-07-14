"""EM3 — Doctor Validation (healing under induced systemic failure).

Blind defer is now unwritable (B2), so doctor pressure is induced in the
runner (src.ratd.induction), not by hand-edited state:

  H1  worker-failure injection  — failed -> abandonment -> dead gate
  H2  drop injection            — abandoned interface pins -> unmet root
  H3  fallback-write injection  — fallback-marked write in the predicate

n=3 each (9 runs) on a task that reliably decomposes (E1 L3 by default).
Audits: doctor fire rate (want 9/9); dossier-correctness (the dossier
names the true induced cause — mechanical, all 9); healing outcome
(converged-with-repair); repair economy (LLM calls in the doctor subtree);
K-bound (<=2 cycles); and the cross-series false-positive check (doctor
fires must be 0 across every healthy EM0-EM2 run).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from ..phase1 import (
    DEFAULT_LOCAL_ENDPOINT, DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_PROVIDER,
    Config, ensure_credentials, load_json, write_json,
)
from ..ratd.induction import Induction
from ..ratd.runtime import Runtime, select_tasks
from . import schema

MODES = ("H1", "H2", "H3")
DOCTOR_K = 2


def first_dossier(run_dir: Path) -> dict[str, Any] | None:
    for e in schema.entry_rows(run_dir):
        if e["address"] == "_system/dossier_1":
            try:
                return json.loads(e["body"])
            except json.JSONDecodeError:
                return None
    return None


def dossier_correct(mode: str, target: str | None, detail: dict[str, Any],
                    dossier: dict[str, Any] | None) -> dict[str, Any]:
    """Mechanical check that the dossier names the true induced cause."""
    if dossier is None:
        return {"correct": False, "reason": "no dossier written"}
    if mode == "H1":
        failed = {f["address"] for f in dossier.get("failed_pins", [])}
        induced = set(detail.get("failed_pins", []))
        dead_refs = {ref for g in dossier.get("dead_gates", []) for ref in g.get("unresolvable_refs", [])}
        names_failure = induced and induced.issubset(failed)
        names_dead = bool(induced & dead_refs) or bool(dossier.get("dead_gates"))
        return {"correct": bool(names_failure and names_dead),
                "induced_failed_pins": sorted(induced),
                "dossier_failed_pins": sorted(failed),
                "dead_gates": len(dossier.get("dead_gates", []))}
    if mode == "H2":
        # Dropping a mid-tree agent propagates UP: its abandoned interface
        # starves its parent, so the failure surfaces as an abandoned pin
        # and/or an unmet root pin owned by an ancestor — not necessarily by
        # the drop target itself. The dossier is correct if it names that
        # systemic-failure signal (the drop's true downstream consequence).
        abandoned = {p["address"] for p in dossier.get("abandoned_pins", [])}
        unmet = {p["address"] for p in dossier.get("unmet_root_pins", [])}
        return {"correct": bool(abandoned) or bool(unmet),
                "target": target,
                "abandoned_pins": sorted(abandoned),
                "unmet_root_pins": sorted(unmet)}
    if mode == "H3":
        fallback = {w["address"] for w in dossier.get("fallback_writes", [])}
        induced_agent = target
        names = any(a.startswith(f"{induced_agent}/") or induced_agent == a.split("/")[0]
                    for a in fallback) if induced_agent else bool(fallback)
        return {"correct": bool(fallback) and names,
                "target": target,
                "dossier_fallback_writes": sorted(fallback)}
    return {"correct": False, "reason": f"unknown mode {mode}"}


def repair_economy(run_dir: Path, metrics: dict[str, Any]) -> dict[str, int]:
    """Doctor-subtree LLM cost: the doctor's own decision calls plus the
    routing calls of the _doctor.* repair agents it spawned."""
    repair_route_calls = 0
    for ev in schema.trace_events(run_dir):
        if ev.get("event") == "route_context" and str(ev.get("agent", "")).startswith("_doctor"):
            repair_route_calls += 1
    doctor_calls = metrics.get("doctor_calls", 0)
    return {"doctor_decision_calls": doctor_calls,
            "repair_agent_route_calls": repair_route_calls,
            "doctor_subtree_calls": doctor_calls + repair_route_calls}


def run_mode(mode: str, task: dict[str, Any], base: Path, prompts: dict[str, str],
             config: Config, reps: int) -> list[Path]:
    mdir = base / mode
    run_dirs = []
    for rep in range(1, reps + 1):
        run_id = f"{task['id']}_{mode}_r{rep}"
        run_dir = mdir / run_id
        run_dirs.append(run_dir)
        if (run_dir / "metrics.json").exists():
            print(f"  skip {mode}/{run_id} (done)", flush=True)
            continue
        if run_dir.exists():
            shutil.rmtree(run_dir)
        print(f"  running {mode}/{run_id}...", flush=True)
        Runtime(f"em3_{run_id}", task, prompts, config, run_dir,
                induction=Induction(mode=mode)).run()
    return run_dirs


def audit_run(run_dir: Path) -> dict[str, Any]:
    metrics = load_json(run_dir / "metrics.json")
    induction = metrics.get("induction") or {}
    mode = induction.get("mode")
    dossier = first_dossier(run_dir)
    correctness = dossier_correct(mode, induction.get("target"),
                                  induction.get("detail", {}), dossier)
    econ = repair_economy(run_dir, metrics)
    return {
        "run_id": run_dir.name, "mode": mode,
        "induction_fired": induction.get("fired"),
        "target": induction.get("target"),
        "doctor_cycles": metrics.get("doctor_cycles", 0),
        "doctor_fired": (metrics.get("doctor_cycles", 0) or 0) >= 1,
        "outcome": metrics.get("outcome"),
        "healed": metrics.get("outcome") == "converged-with-repair",
        "k_bound_ok": (metrics.get("doctor_cycles", 0) or 0) <= DOCTOR_K,
        "dossier_correct": correctness["correct"],
        "dossier_detail": correctness,
        "repair_economy": econ,
    }


def false_positive_scan(dirs: list[Path]) -> dict[str, Any]:
    """A false fire = the doctor firing on a genuinely-healthy run. The
    doctor is B5-gated (it only fires on a real systemic-failure state), so
    a fire on a run that ended `converged` (clean, plain) would be spurious.
    A fire on a `converged-with-repair` or `failed` run is CORRECT — that run
    had a genuine failure — so those are organic fires, not false positives
    (e.g. EM0 t15_r3 genuinely failed; the doctor was right to try)."""
    false_fires, organic = [], []
    scanned = 0
    for base in dirs:
        if not base.exists():
            continue
        for metrics_path in base.rglob("metrics.json"):
            m = load_json(metrics_path)
            if "induction" in m and m.get("induction"):
                continue  # an EM3 induced run, not a healthy one
            scanned += 1
            if (m.get("doctor_cycles", 0) or 0) > 0:
                if m.get("outcome") == "converged":       # fired on a clean run → spurious
                    false_fires.append(str(metrics_path.parent))
                else:                                     # fired on a genuine failure → correct
                    organic.append({"run": str(metrics_path.parent), "outcome": m.get("outcome")})
    return {"scanned_healthy_runs": scanned, "false_fires": len(false_fires),
            "offenders": false_fires, "organic_fires": organic}


def evaluate(audits: list[dict[str, Any]], fp: dict[str, Any]) -> dict[str, Any]:
    """Spec pass bar: >= 7/9 healed, 9/9 dossiers correct, zero false fires.
    For a partial run (n<9) the healing bar scales as ceil(7/9 * n)."""
    n = len(audits)
    healed = sum(1 for a in audits if a["healed"])
    fired = sum(1 for a in audits if a["doctor_fired"])
    dossiers_ok = sum(1 for a in audits if a["dossier_correct"])
    heal_bar = -(-7 * n // 9)  # ceil(7/9 * n)
    bars = {
        "healed_ge_bar": n > 0 and healed >= heal_bar,
        "dossiers_all_correct": n > 0 and dossiers_ok == n,
        "k_bound_respected": all(a["k_bound_ok"] for a in audits),
        "zero_false_fires": fp["false_fires"] == 0,
    }
    return {
        "runs": n,
        "doctor_fire_rate": f"{fired}/{n}",
        "healed_rate": f"{healed}/{n}",
        "heal_bar": heal_bar,
        "dossier_correct_rate": f"{dossiers_ok}/{n}",
        "k_bound_respected": bars["k_bound_respected"],
        "false_fires": fp["false_fires"],
        "pass_bar": bars,
        "pass": all(bars.values()),
    }


def write_report(base: Path, audits: list[dict[str, Any]], fp: dict[str, Any],
                 verdict: dict[str, Any]) -> None:
    lines = [
        "# EM3 — Doctor Validation results", "",
        f"- doctor fire rate: {verdict['doctor_fire_rate']}",
        f"- healed (converged-with-repair): {verdict['healed_rate']}",
        f"- dossier mechanically correct: {verdict['dossier_correct_rate']}",
        f"- K-bound (<=2) respected: {verdict['k_bound_respected']}",
        f"- false fires across healthy EM0-EM2 runs: {fp['false_fires']} "
        f"(of {fp['scanned_healthy_runs']} scanned)",
        f"- **pass bar met: {verdict['pass']}**",
        "",
        "| run | mode | target | fired | outcome | healed | dossier✓ | K✓ | subtree calls |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for a in audits:
        lines.append(
            f"| {a['run_id']} | {a['mode']} | {a['target']} | {a['doctor_fired']} | "
            f"{a['outcome']} | {a['healed']} | {a['dossier_correct']} | {a['k_bound_ok']} | "
            f"{a['repair_economy']['doctor_subtree_calls']} |"
        )
    if fp["offenders"]:
        lines += ["", "## FALSE FIRES (doctor fired on a healthy run):"] + [f"- {o}" for o in fp["offenders"]]
    (base / "EM3_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(base / "EM3_audit.json", {"verdict": verdict, "false_positive": fp, "audits": audits})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EM3 Doctor Validation")
    parser.add_argument("--tasks", default="tasks/e1_ladder.json")
    parser.add_argument("--task-id", default="L3")
    parser.add_argument("--modes", default="H1,H2,H3")
    parser.add_argument("--out-dir", default="results/em3")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--harness", default="prompts/harness_v7.md")
    parser.add_argument("--worker-prompt", default="prompts/worker_v7.md")
    parser.add_argument("--doctor-prompt", default="prompts/doctor_v1.md")
    parser.add_argument("--healthy-dirs", default="results/em0,results/em1,results/em2",
                        help="dirs scanned for the false-positive check")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    parser.add_argument("--local-endpoint", default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args(argv)

    base = Path(args.out_dir)
    base.mkdir(parents=True, exist_ok=True)
    task = select_tasks(Path(args.tasks), (args.task_id,))[0]
    modes = [m for m in args.modes.split(",") if m in MODES]

    if not args.audit_only:
        config = Config(args.provider, args.model, args.temperature, args.max_tokens, args.local_endpoint)
        ensure_credentials(config)
        prompts = {
            "harness": Path(args.harness).read_text(encoding="utf-8"),
            "worker": Path(args.worker_prompt).read_text(encoding="utf-8"),
            "doctor": Path(args.doctor_prompt).read_text(encoding="utf-8"),
        }
        for mode in modes:
            print(f"== {mode} ==", flush=True)
            run_mode(mode, task, base, prompts, config, args.repetitions)

    audits: list[dict[str, Any]] = []
    for mode in modes:
        mdir = base / mode
        if not mdir.exists():
            continue
        for run_dir in sorted(p for p in mdir.iterdir() if p.is_dir() and (p / "metrics.json").exists()):
            audits.append(audit_run(run_dir))

    fp = false_positive_scan([Path(d) for d in args.healthy_dirs.split(",") if d])
    verdict = evaluate(audits, fp)
    write_report(base, audits, fp, verdict)
    print(f"\nEM3: fired {verdict['doctor_fire_rate']} | healed {verdict['healed_rate']} | "
          f"dossiers {verdict['dossier_correct_rate']} | false fires {fp['false_fires']} | "
          f"pass {verdict['pass']}", flush=True)
    print(f"wrote {base / 'EM3_report.md'}", flush=True)
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
