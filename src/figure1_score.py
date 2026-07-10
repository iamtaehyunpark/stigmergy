"""Figure-1 scoring (spec 1.3).

Per run, computes:
- terminology-consistency: identifier-like terms are extracted from the
  Part-A terminology/glossary artifact(s) and matched verbatim against
  the Part-B tutorial artifact(s). This is the decisiveness measure:
  if RATD's consistency <= baseline's, the cross-link was not decisive.
- emergent cross edges (RATD only): dependency edges authored mid-run
  by an agent other than root - (a) spawn/self_role conditions written
  by a non-root agent referencing paths outside that agent's own
  subtree, (b) DEFER wake conditions referencing paths outside the
  deferring agent's own branch/ancestry. Root-authored conditions are
  NOT counted: a one-shot planner could have written those too. The
  baseline's emergent count is 0 by construction (structure frozen at
  t=0); its planned cross-branch reads are reported separately.
- defer/wake cycles and unique cross-branch (agent, path) read pairs.

Artifact detection is by key-name pattern and is reported in the output
for audit; runs where detection fails are flagged, not silently scored.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from .phase1 import condition_refs, load_json, write_json

TERMINOLOGY_KEY = re.compile(r"terminolog|glossar|convention|naming|vocab|casing|style_rule|canonical", re.I)
TUTORIAL_KEY = re.compile(r"tutorial|walkthrough|integration|code_sample", re.I)

TERM_PATTERNS = [
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),          # snake_case
    re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"),          # ERROR_CODES
    re.compile(r"\b[a-z]+(?:[A-Z][a-z0-9]+)+\b"),              # camelCase
    re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)+\b"),          # kebab-case
    re.compile(r"/[a-z][a-z0-9_{}/-]{3,}"),                    # endpoint paths
]


def extract_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for pat in TERM_PATTERNS:
        terms.update(m for m in pat.findall(text) if len(m) >= 4)
    return terms


def load_entries(run_dir: Path) -> dict[str, str]:
    sqlite_path = run_dir / "state.sqlite"
    if sqlite_path.exists():
        db = sqlite3.connect(sqlite_path)
        return {str(k): str(v) for k, v in db.execute("SELECT namespace_key, value FROM entries WHERE status='done'")}
    entries_path = run_dir / "entries.json"
    if entries_path.exists():
        return {str(k): str(v) for k, v in load_json(entries_path).items()}
    return {}


def split_parts(entries: dict[str, str]) -> tuple[list[str], list[str]]:
    """Return (terminology_paths, tutorial_paths) at the interface level only.

    Only depth-1 namespaces (root.N/...) count: these are the branch
    interfaces other branches can actually reference and read. Deeper
    artifacts (root.N.M/...) are internal working products invisible
    outside their branch; counting their terms in the denominator
    penalized whichever system decomposed more deeply (the v1 scoring
    asymmetry). The final integrated root/ artifact is excluded.
    """
    term_paths, tut_paths = [], []
    for path in sorted(entries):
        ns = path.split("/")[0]
        if ns == "root" or ns.count(".") != 1:
            continue
        key = path.split("/", 1)[1] if "/" in path else path
        if TERMINOLOGY_KEY.search(key):
            term_paths.append(path)
        elif TUTORIAL_KEY.search(key):
            tut_paths.append(path)
    return term_paths, tut_paths


def consistency(entries: dict[str, str]) -> dict[str, Any]:
    term_paths, tut_paths = split_parts(entries)
    term_text = "\n".join(entries[p] for p in term_paths)
    # The tutorial side aggregates the WHOLE producing branch: when the
    # branch decomposes, the interface artifact can be a stub while the
    # real content lives in child artifacts (v3 r2/r3: 15-char stub over
    # 16k chars of sections). The consuming text is what the branch
    # shipped, at any depth. Terminology side stays interface-level:
    # the denominator is what consumers could actually reference.
    tut_branches = {p.split("/")[0] for p in tut_paths}
    tut_paths = sorted(
        p for p in entries
        if any(p.split("/")[0] == b or p.split("/")[0].startswith(b + ".") for b in tut_branches)
    )
    tut_text = "\n".join(entries[p] for p in tut_paths)
    terms = sorted(extract_terms(term_text))
    matched = sorted(t for t in terms if t in tut_text)
    return {
        "terminology_paths": term_paths,
        "tutorial_paths": tut_paths,
        "detection_ok": bool(term_paths) and bool(tut_paths),
        "term_count": len(terms),
        "matched_count": len(matched),
        "consistency": (len(matched) / len(terms)) if terms else None,
        "terms": terms,
        "matched": matched,
    }


def in_subtree(ns: str, owner: str) -> bool:
    return ns == owner or ns.startswith(owner + ".")


def is_ancestor(ns: str, agent: str) -> bool:
    return agent == ns or agent.startswith(ns + ".")


def ratd_trace_metrics(run_dir: Path) -> dict[str, Any]:
    defer_wakes = 0
    defers = 0
    emergent: set[tuple[str, str]] = set()
    cross_pairs: set[tuple[str, str]] = set()
    trace = run_dir / "trace.jsonl"
    if not trace.exists():
        return {"defer_count": 0, "defer_wake_fires": 0, "emergent_cross_edges": 0, "emergent_edges": [], "cross_branch_unique_pairs": 0}
    for line in trace.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        event = rec.get("event")
        if event == "defer":
            defers += 1
        elif event == "trigger_fire" and ":defer" in str(rec.get("id", "")):
            defer_wakes += 1
        elif event == "cross_branch_read":
            cross_pairs.add((rec["agent"], rec["path"]))
        elif event == "spawn" and rec.get("parent") != "root":
            parent = str(rec["parent"])
            child = rec["child"]
            for ref in condition_refs(str(child.get("condition") or "")):
                if not in_subtree(ref.split("/")[0], parent):
                    emergent.add((str(child["task_id"]), ref))
        elif event == "self_role" and rec.get("agent") != "root":
            agent = str(rec["agent"])
            for ref in condition_refs(str(rec.get("condition") or "")):
                if not in_subtree(ref.split("/")[0], agent):
                    emergent.add((agent, ref))
        elif event == "trigger_add" and ":defer" in str(rec.get("id", "")):
            agent = str(rec.get("agent"))
            for ref in condition_refs(str(rec.get("condition") or "")):
                ns = ref.split("/")[0]
                if not in_subtree(ns, agent) and not is_ancestor(ns, agent):
                    emergent.add((agent, ref))
    return {
        "defer_count": defers,
        "defer_wake_fires": defer_wakes,
        "emergent_cross_edges": len(emergent),
        "emergent_edges": sorted(f"{a} <- {r}" for a, r in emergent),
        "cross_branch_unique_pairs": len(cross_pairs),
    }


def score_run(run_dir: Path, system: str) -> dict[str, Any]:
    metrics_path = run_dir / "metrics.json"
    metrics = load_json(metrics_path) if metrics_path.exists() else {}
    row: dict[str, Any] = {
        "run_id": run_dir.name,
        "system": system,
        "converged": metrics.get("converged"),
        "llm_calls": metrics.get("llm_calls"),
    }
    if system == "ratd":
        row.update(ratd_trace_metrics(run_dir))
    else:
        row.update({
            "defer_count": 0,
            "defer_wake_fires": 0,
            "emergent_cross_edges": 0,
            "planned_cross_branch_unique_pairs": metrics.get("planned_cross_branch_unique_pairs"),
        })
    row.update(consistency(load_entries(run_dir)))
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Figure-1 scorer")
    parser.add_argument("--ratd-dir", default="results/figure1/ratd")
    parser.add_argument("--baseline-dir", default="results/figure1/baseline")
    parser.add_argument("--out", default="results/figure1/FIGURE1_scores.json")
    args = parser.parse_args(argv)

    rows: list[dict[str, Any]] = []
    for system, base in (("ratd", Path(args.ratd_dir)), ("baseline", Path(args.baseline_dir))):
        if not base.exists():
            continue
        for run_dir in sorted(p for p in base.iterdir() if p.is_dir() and (p / "metrics.json").exists()):
            rows.append(score_run(run_dir, system))
    write_json(Path(args.out), rows)

    def fmt(v: Any) -> str:
        return f"{v:.2%}" if isinstance(v, float) else str(v)

    print(f"{'run':<14} {'system':<9} {'conv':<5} {'consist':<8} {'terms':<6} {'emerg':<6} {'defers':<7} detection")
    for r in rows:
        print(
            f"{r['run_id']:<14} {r['system']:<9} {str(r['converged']):<5} "
            f"{fmt(r['consistency']) if r['consistency'] is not None else 'n/a':<8} "
            f"{r['term_count']:<6} {r['emergent_cross_edges']:<6} {r['defer_count']:<7} "
            f"{'ok' if r['detection_ok'] else 'FAILED: ' + ','.join(r['terminology_paths'] + r['tutorial_paths']) or 'none'}"
        )
    for system in ("ratd", "baseline"):
        vals = [r["consistency"] for r in rows if r["system"] == system and r["consistency"] is not None]
        if vals:
            print(f"{system} mean consistency: {sum(vals)/len(vals):.2%} over {len(vals)} scored runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
