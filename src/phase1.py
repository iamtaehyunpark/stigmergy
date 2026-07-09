from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "qwen3.6"
DEFAULT_PROVIDER = "local"
DEFAULT_LOCAL_ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"
DEFAULT_MAX_TOKENS = 4000
DONE_TERM_RE = re.compile(r'done\("([^"]+)"\)')
PATH_RE = re.compile(r"^root(?:\.\d+)*/[a-z][a-z0-9_]*$")
SUBTASK_ID_RE = re.compile(r"^root(?:\.\d+)+$")


@dataclass(frozen=True)
class Config:
    provider: str
    model: str
    temperature: float
    max_tokens: int
    local_endpoint: str


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)
        f.write("\n")


def build_context(task: dict[str, Any]) -> str:
    task_text = task["task"]
    return "\n".join(
        [
            f"ROOT GOAL: {task_text}",
            "YOUR TASK ID: root",
            f"YOUR TASK: {task_text}",
            "YOUR CAPSULE (why you exist): (you are the root agent)",
            "REMAINING BUDGET: 20",
            'RELEVANT MEMORY (top-k retrieval stub): (empty)',
        ]
    )


def build_repair_message(original_message: str, raw: str, notes: list[str]) -> str:
    return "\n".join(
        [
            "Your previous action document failed structural validation.",
            "Return a corrected action document as strict JSON only.",
            "Do not wrap it in Markdown fences. Do not add prose.",
            "Do not change the assigned task or task_id.",
            "Validation errors:",
            *[f"- {note}" for note in notes],
            "",
            "Original context:",
            original_message,
            "",
            "Previous action document:",
            raw,
        ]
    )


def call_anthropic(system_prompt: str, user_message: str, config: Config) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    payload = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    return _http_json_text(req, provider="anthropic")


def call_openai(system_prompt: str, user_message: str, config: Config) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    return _http_json_text(req, provider="openai")


def call_local(system_prompt: str, user_message: str, config: Config) -> str:
    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"/no_think\n\n{user_message}"},
        ],
    }
    req = urllib.request.Request(
        config.local_endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    return _http_json_text(req, provider="local")


def _http_json_text(req: urllib.request.Request, provider: str) -> str:
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{provider} API error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{provider} API connection failed: {exc.reason}") from exc
    if provider == "anthropic":
        parts = []
        for item in data.get("content", []):
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts).strip()
    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    reasoning = message.get("reasoning")
    if isinstance(reasoning, str):
        return reasoning.strip()
    return ""


def call_model(system_prompt: str, user_message: str, config: Config) -> str:
    if config.provider == "local":
        return call_local(system_prompt, user_message, config)
    if config.provider == "anthropic":
        return call_anthropic(system_prompt, user_message, config)
    if config.provider == "openai":
        return call_openai(system_prompt, user_message, config)
    raise ValueError(f"Unsupported provider: {config.provider}")


def ensure_credentials(config: Config) -> None:
    if config.provider == "local":
        if not config.local_endpoint:
            raise RuntimeError("RATD_LOCAL_ENDPOINT is not set")
        return
    if config.provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    if config.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    if config.provider not in {"local", "anthropic", "openai"}:
        raise RuntimeError(f"Unsupported provider: {config.provider}")


def run_phase1(args: argparse.Namespace) -> int:
    harness = Path(args.harness).read_text(encoding="utf-8")
    tasks = load_json(Path(args.tasks))
    config = Config(
        provider=args.provider,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        local_endpoint=args.local_endpoint,
    )
    ensure_credentials(config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_meta = {
        "provider": config.provider,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "local_endpoint": config.local_endpoint if config.provider == "local" else None,
        "harness": args.harness,
        "started_at": utc_timestamp(),
    }
    write_json(out_dir / "run_meta.json", run_meta)

    selected = tasks[: args.limit] if args.limit else tasks
    for task in selected:
        task_id = task["id"]
        action_path = out_dir / f"{task_id}.json"
        raw_path = out_dir / f"{task_id}.raw.txt"
        if args.skip_existing and raw_path.exists():
            print(f"skip {task_id}: raw response exists")
            continue
        user_message = build_context(task)
        raw = ""
        parsed: dict[str, Any] | None = None
        notes: list[str] = []
        for attempt in range(args.retries + 1):
            label = "calling" if attempt == 0 else f"repairing {attempt}"
            print(f"{label} {task_id}...", flush=True)
            prompt_message = user_message if attempt == 0 else build_repair_message(user_message, raw, notes)
            raw = call_model(harness, prompt_message, config)
            parsed, notes = parse_and_validate_action(raw)
            if parsed is not None and not notes:
                break
        raw_path.write_text(raw + "\n", encoding="utf-8")
        if parsed is None:
            print(f"{task_id}: invalid strict JSON: {'; '.join(notes)}", file=sys.stderr)
            continue
        if notes:
            print(f"{task_id}: invalid action document: {'; '.join(notes)}", file=sys.stderr)
            continue
        write_json(action_path, parsed)
        time.sleep(args.sleep)
    return 0


def parse_and_validate_action(raw: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        maybe = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"raw strict JSON parse failed: {exc.msg}"]
    if not isinstance(maybe, dict):
        return None, ["raw strict JSON is not an object"]
    notes: list[str] = []
    schema_ok, schema_notes = validate_schema(maybe)
    budget_ok, budget_notes = validate_budget(maybe, budget=20)
    namespace_ok, namespace_notes = score_namespace(maybe)
    if not schema_ok:
        notes.extend(schema_notes)
    if not budget_ok:
        notes.extend(budget_notes)
    if not namespace_ok:
        notes.extend(namespace_notes)
    return maybe, notes


def score_phase1(args: argparse.Namespace) -> int:
    tasks = load_json(Path(args.tasks))
    results_dir = Path(args.results_dir)
    rows = []
    for task in tasks:
        rows.append(score_task(task, results_dir))
    results_dir.mkdir(parents=True, exist_ok=True)
    scores_path = results_dir / "scores.csv"
    fieldnames = [
        "id",
        "expected",
        "action",
        "valid_json",
        "action_match",
        "decomposition_sanity",
        "condition_correctness",
        "namespace_discipline",
        "capsule_quality",
        "manual_override_flag",
        "notes",
    ]
    with scores_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print_summary(rows)
    print(f"wrote {scores_path}")
    return 0


def score_task(task: dict[str, Any], results_dir: Path) -> dict[str, Any]:
    task_id = task["id"]
    raw_path = results_dir / f"{task_id}.raw.txt"
    action_path = results_dir / f"{task_id}.json"
    notes: list[str] = []
    parsed: dict[str, Any] | None = None
    valid_json = 0

    if raw_path.exists():
        raw = raw_path.read_text(encoding="utf-8").strip()
        try:
            maybe = json.loads(raw)
            if isinstance(maybe, dict):
                parsed = maybe
            else:
                notes.append("raw strict JSON is not an object")
        except json.JSONDecodeError as exc:
            notes.append(f"raw strict JSON parse failed: {exc.msg}")
    elif action_path.exists():
        try:
            maybe = load_json(action_path)
            if isinstance(maybe, dict):
                parsed = maybe
                notes.append("raw response missing; parsed json used")
            else:
                notes.append("parsed JSON is not an object")
        except json.JSONDecodeError as exc:
            notes.append(f"parsed JSON load failed: {exc.msg}")
    else:
        notes.append("missing raw response and parsed JSON")

    schema_ok = False
    budget_ok = False
    action = ""
    namespace_discipline = 0
    decomposition_sanity = ""
    condition_correctness = ""
    capsule_quality = ""
    manual_override_flag = 0

    if parsed is not None:
        action = str(parsed.get("action", ""))
        schema_ok, schema_notes = validate_schema(parsed)
        budget_ok, budget_notes = validate_budget(parsed, budget=20)
        notes.extend(schema_notes)
        notes.extend(budget_notes)
        namespace_discipline, ns_notes = score_namespace(parsed)
        notes.extend(ns_notes)
        if action == "SPAWN":
            decomposition_sanity, decomp_notes = score_decomposition(parsed)
            condition_correctness, cond_notes = score_conditions(parsed)
            capsule_quality, cap_notes = score_capsules(parsed)
            notes.extend(decomp_notes)
            notes.extend(cond_notes)
            notes.extend(cap_notes)
        valid_json = int(schema_ok and budget_ok)
        if action and action != task["expected"]:
            manual_override_flag = 1

    return {
        "id": task_id,
        "expected": task["expected"],
        "action": action,
        "valid_json": valid_json,
        "action_match": int(action == task["expected"]),
        "decomposition_sanity": decomposition_sanity,
        "condition_correctness": condition_correctness,
        "namespace_discipline": namespace_discipline,
        "capsule_quality": capsule_quality,
        "manual_override_flag": manual_override_flag,
        "notes": "; ".join(notes),
    }


def validate_schema(doc: dict[str, Any]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if doc.get("task_id") != "root":
        notes.append("task_id must be root")
    reasoning = doc.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        notes.append("missing non-empty reasoning")
    action = doc.get("action")
    if action not in {"EXECUTE", "SPAWN", "DEFER"}:
        notes.append("action must be EXECUTE, SPAWN, or DEFER")
        return False, notes
    if action == "EXECUTE":
        outputs = doc.get("result_outputs")
        if not valid_output_list(outputs):
            notes.append("EXECUTE requires result_outputs with path/description")
    elif action == "SPAWN":
        subtasks = doc.get("subtasks")
        if not isinstance(subtasks, list) or not subtasks:
            notes.append("SPAWN requires non-empty subtasks")
        else:
            seen_ids: set[str] = set()
            for subtask in subtasks:
                if not isinstance(subtask, dict):
                    notes.append("subtask must be object")
                    continue
                sid = subtask.get("id")
                if not isinstance(sid, str) or not SUBTASK_ID_RE.match(sid):
                    notes.append(f"invalid subtask id: {sid}")
                elif sid in seen_ids:
                    notes.append(f"duplicate subtask id: {sid}")
                else:
                    seen_ids.add(sid)
                for key in ("goal", "capsule"):
                    if not isinstance(subtask.get(key), str) or not subtask[key].strip():
                        notes.append(f"subtask {sid} missing {key}")
                if not valid_output_list(subtask.get("outputs")):
                    notes.append(f"subtask {sid} requires outputs with path/description")
                condition = subtask.get("condition")
                if condition is not None and not isinstance(condition, str):
                    notes.append(f"subtask {sid} condition must be null or string")
                if not isinstance(subtask.get("budget"), int):
                    notes.append(f"subtask {sid} budget must be int")
    elif action == "DEFER":
        if not isinstance(doc.get("wake_condition"), str) or not doc["wake_condition"].strip():
            notes.append("DEFER requires wake_condition")
    return not notes, notes


def valid_output_list(outputs: Any) -> bool:
    if not isinstance(outputs, list) or not outputs:
        return False
    for output in outputs:
        if not isinstance(output, dict):
            return False
        if not isinstance(output.get("path"), str) or not output["path"].strip():
            return False
        if not isinstance(output.get("description"), str) or not output["description"].strip():
            return False
    return True


def validate_budget(doc: dict[str, Any], budget: int) -> tuple[bool, list[str]]:
    if doc.get("action") != "SPAWN":
        return True, []
    notes: list[str] = []
    subtasks = doc.get("subtasks")
    if not isinstance(subtasks, list):
        return False, ["budget unavailable because subtasks invalid"]
    if budget < 2:
        notes.append("spawn attempted with budget < 2")
    k = len(subtasks)
    child_budgets = []
    for subtask in subtasks:
        if isinstance(subtask, dict) and isinstance(subtask.get("budget"), int):
            child_budgets.append(subtask["budget"])
        else:
            notes.append("subtask budget missing or not int")
    if any(b < 0 for b in child_budgets):
        notes.append("negative child budget")
    if sum(child_budgets) > budget - k:
        notes.append(f"child budget sum {sum(child_budgets)} exceeds {budget - k}")
    return not notes, notes


def score_namespace(doc: dict[str, Any]) -> tuple[int, list[str]]:
    notes: list[str] = []
    action = doc.get("action")
    if action == "EXECUTE":
        for output in doc.get("result_outputs", []):
            path = output.get("path") if isinstance(output, dict) else None
            if not isinstance(path, str) or not PATH_RE.match(path) or not path.startswith("root/"):
                notes.append(f"bad EXECUTE output namespace: {path}")
    elif action == "SPAWN":
        for subtask in doc.get("subtasks", []):
            if not isinstance(subtask, dict):
                continue
            sid = subtask.get("id")
            for output in subtask.get("outputs", []):
                path = output.get("path") if isinstance(output, dict) else None
                if not isinstance(sid, str) or not isinstance(path, str):
                    notes.append(f"bad output namespace: {path}")
                elif not PATH_RE.match(path) or not path.startswith(f"{sid}/"):
                    notes.append(f"output {path} must be under {sid}/")
            condition = subtask.get("condition")
            if isinstance(condition, str):
                for ref in condition_refs(condition):
                    if not PATH_RE.match(ref):
                        notes.append(f"condition path is not namespace/key: {ref}")
    elif action == "DEFER":
        wake = doc.get("wake_condition")
        if isinstance(wake, str):
            for ref in condition_refs(wake):
                if not PATH_RE.match(ref):
                    notes.append(f"wake path is not namespace/key: {ref}")
    return int(not notes), notes


def score_decomposition(doc: dict[str, Any]) -> tuple[int, list[str]]:
    notes: list[str] = []
    subtasks = doc.get("subtasks", [])
    if not isinstance(subtasks, list) or not subtasks:
        return 0, ["no subtasks to score"]
    k = len(subtasks)
    if k >= 8:
        notes.append("8+ subtasks is likely over-sharded")
        return 0, notes
    if k == 1:
        notes.append("single spawned subtask is usually unnecessary")
        return 1, notes
    has_outputs = all(valid_output_list(s.get("outputs")) for s in subtasks if isinstance(s, dict))
    has_conditioned = any(isinstance(s, dict) and s.get("condition") for s in subtasks)
    has_parallel = any(isinstance(s, dict) and s.get("condition") is None for s in subtasks)
    sequential_ids = [f"root.{i}" for i in range(1, k + 1)]
    ids = [s.get("id") for s in subtasks if isinstance(s, dict)]
    if ids != sequential_ids:
        notes.append("subtask ids are not contiguous root.1..root.n")
    if has_outputs and ids == sequential_ids and (has_parallel or has_conditioned):
        return 2, notes
    return 1, notes


def score_conditions(doc: dict[str, Any]) -> tuple[int, list[str]]:
    notes: list[str] = []
    outputs_to_owner: dict[str, str] = {}
    subtasks = doc.get("subtasks", [])
    if not isinstance(subtasks, list):
        return 0, ["subtasks invalid"]
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        sid = subtask.get("id", "")
        for output in subtask.get("outputs", []):
            if isinstance(output, dict) and isinstance(output.get("path"), str):
                outputs_to_owner[output["path"]] = str(sid)
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        sid = str(subtask.get("id", ""))
        condition = subtask.get("condition")
        if condition is None:
            continue
        if not isinstance(condition, str):
            notes.append(f"{sid} condition is not a string")
            continue
        refs = condition_refs(condition)
        if not refs:
            notes.append(f"{sid} condition has no done(path) terms")
        for ref in refs:
            owner = outputs_to_owner.get(ref)
            if owner is None:
                notes.append(f"{sid} condition references undeclared output {ref}")
            elif owner == sid:
                notes.append(f"{sid} condition references its own output {ref}")
        if not allowed_condition_syntax(condition):
            notes.append(f"{sid} condition uses unsupported syntax")
    return int(not notes), notes


def score_capsules(doc: dict[str, Any]) -> tuple[int, list[str]]:
    notes: list[str] = []
    subtasks = doc.get("subtasks", [])
    if not isinstance(subtasks, list):
        return 0, ["subtasks invalid for capsule scoring"]
    total = 0
    count = 0
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        count += 1
        capsule = str(subtask.get("capsule", ""))
        sentences = [s for s in re.split(r"[.!?]+", capsule) if s.strip()]
        score = 0
        if 2 <= len(sentences) <= 4:
            score += 1
        lower = capsule.lower()
        if any(token in lower for token in ["root goal", "parent", "overall", "final", "needed"]):
            score += 1
        if len(capsule.split()) > 100:
            score = max(0, score - 1)
            notes.append(f"{subtask.get('id')} capsule may be too long")
        total += score
    if count == 0:
        return 0, ["no capsules to score"]
    mean = total / count
    if mean >= 1.5:
        return 2, notes
    if mean >= 0.75:
        return 1, notes
    return 0, notes


def condition_refs(condition: str) -> list[str]:
    return DONE_TERM_RE.findall(condition)


def allowed_condition_syntax(condition: str) -> bool:
    stripped = DONE_TERM_RE.sub("TERM", condition)
    stripped = stripped.replace("AND", "").replace("OR", "")
    stripped = stripped.replace("and", "").replace("or", "")
    stripped = stripped.replace("(", "").replace(")", "")
    stripped = stripped.replace("TERM", "")
    return not stripped.strip()


def print_summary(rows: list[dict[str, Any]]) -> None:
    total = len(rows)
    valid = sum(int(row["valid_json"]) for row in rows)
    action_match = sum(int(row["action_match"]) for row in rows)
    spawn_rows = [row for row in rows if row["action"] == "SPAWN"]
    decomp_values = [int(row["decomposition_sanity"]) for row in spawn_rows if row["decomposition_sanity"] != ""]
    cond_values = [int(row["condition_correctness"]) for row in spawn_rows if row["condition_correctness"] != ""]
    mean_decomp = sum(decomp_values) / len(decomp_values) if decomp_values else 0.0
    cond_rate = sum(cond_values) / len(cond_values) if cond_values else 0.0
    passed = valid >= 19 and action_match >= 16 and mean_decomp >= 1.3 and cond_rate >= 0.8
    print("Phase 1 aggregate:")
    print(f"  valid_json: {valid}/{total}")
    print(f"  action_match: {action_match}/{total}")
    print(f"  mean_decomposition_sanity: {mean_decomp:.2f}")
    print(f"  condition_correctness_rate: {cond_rate:.2%}")
    print(f"  pass_bar: {'PASS' if passed else 'FAIL'}")


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RATD Phase 1 probe runner and scorer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="call the configured LLM for each Phase 1 task")
    run.add_argument("--harness", default="prompts/harness_v1.md")
    run.add_argument("--tasks", default="tasks/phase1_tasks.json")
    run.add_argument("--out-dir", default="results/phase1")
    run.add_argument("--provider", default=os.environ.get("RATD_PROVIDER", DEFAULT_PROVIDER))
    run.add_argument("--model", default=os.environ.get("RATD_MODEL", DEFAULT_MODEL))
    run.add_argument(
        "--local-endpoint",
        default=os.environ.get("RATD_LOCAL_ENDPOINT", DEFAULT_LOCAL_ENDPOINT),
    )
    run.add_argument("--temperature", type=float, default=0.0)
    run.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    run.add_argument("--sleep", type=float, default=0.0)
    run.add_argument("--limit", type=int, default=0)
    run.add_argument("--retries", type=int, default=2)
    run.add_argument("--skip-existing", action="store_true")
    run.set_defaults(func=run_phase1)

    score = sub.add_parser("score", help="score saved Phase 1 responses")
    score.add_argument("--tasks", default="tasks/phase1_tasks.json")
    score.add_argument("--results-dir", default="results/phase1")
    score.set_defaults(func=score_phase1)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
