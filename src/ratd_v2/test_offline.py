"""Offline machinery test — scripted model, no LLM endpoint.

Drives all three arms through scripted rounds and asserts the runtime
invariants the smoke tests will later check with the real model:
multi-round continuity, agent-authored rule firing (exactly-once),
Arm S revive + implicit done + op-result delivery, workspace
persistence + cross-workspace write logging, bounded returns with
truncation markers, worker surface exclusion, health verdicts.

    python3 -m src.ratd_v2.test_offline
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from .client import Config, ModelReply
from .runtime import Rails, Runtime


def block(tool: str, **args: object) -> str:
    return "```json\n" + json.dumps({"tool": tool, "args": args}) + "\n```\n"


class MockModel:
    def __init__(self, script: dict[tuple[str, int], str]):
        self.script = script
        self.prompts: dict[tuple[str, int], str] = {}

    def __call__(self, messages: list[dict[str, str]], json_mode: bool = False) -> ModelReply:
        joined = "\n".join(m["content"] for m in messages)
        aid = re.search(r"AGENT ID: (\S+)", joined).group(1)
        rnd = int(re.search(r"\[round (\d+) for you", joined).group(1))
        self.prompts[(aid, rnd)] = joined
        text = self.script.get((aid, rnd), block("done", summary="(default)"))
        return ModelReply(text, prompt_tokens=len(joined) // 4,
                          completion_tokens=len(text) // 4)


def read_trace(out: Path) -> list[dict]:
    return [json.loads(l) for l in
            (out / "trace.jsonl").read_text(encoding="utf-8").splitlines()]


def load_harnesses() -> dict[str, str]:
    base = Path("prompts/et")
    return {"ratd": (base / "harness_ratd.md").read_text(),
            "planner": (base / "harness_planner.md").read_text(),
            "worker": (base / "harness_worker.md").read_text(),
            "stig": (base / "harness_stig.md").read_text()}


TASK = {"id": "T", "task": "Produce a final note at global/final.md."}


def test_arm_r(tmp: Path, harnesses: dict[str, str]) -> None:
    from .tools import READ_CAP
    long_plan = "plan line\n" * (READ_CAP // 10 + 300)  # > READ_CAP → marker
    script = {
        ("root", 1): "Survey first.\n"
                     + block("catalog.search", query="", k=10)
                     + block("workspace.write", path="plan.md", content=long_plan),
        ("root", 2): block("workspace.read", path="plan.md")
                     + block("spawn",
                             task="Write section A and commit it to global/section_a.md",
                             capsule="Root needs section A text.",
                             initial_refs=["agents/root/plan.md"])
                     + block("circuit.add_rule",
                             condition='exists("global/section_a.md")',
                             target={"type": "spawn", "task": "Review section A",
                                     "capsule": "Quality check.",
                                     "initial_refs": ["global/section_a.md"]})
                     + block("wait", condition='state("a1")=="done"'),
        ("a1", 1): block("workspace.read", path="agents/root/plan.md")
                   + block("global.commit", path="section_a.md",
                           content="Section A content.", summary="section A draft"),
        ("a1", 2): block("done", summary="section A committed (used round-1 read)"),
        ("a2", 1): block("global.read", path="global/section_a.md")
                   + block("workspace.write", path="agents/root/review_note.md",
                           content="review: ok")
                   + block("done", summary="reviewed"),
        ("root", 3): block("global.commit", path="final.md",
                           from_workspace="plan.md", summary="final note")
                     + block("done", summary="delivered"),
    }
    mock = MockModel(script)
    out = tmp / "r"
    m = Runtime("offline_r", "r", TASK, harnesses, Config(), out,
                Rails(max_llm_calls=50), model_fn=mock).run()
    trace = read_trace(out)
    h = m["health"]
    assert not h["systemic_failure"], h
    assert h["root_state"] == "done" and m["n_agents"] == 3
    assert h["quiescent"], "run must end at quiescence, not a rail"
    assert m["rules_fired"] == 2, m["rules_fired"]  # exists-rule + root's wait rule
    state = json.loads((out / "state.json").read_text())
    exists_rules = [r for r in state["rules"].values()
                    if "exists" in r["condition"]]
    assert len(exists_rules) == 1 and exists_rules[0]["fired_count"] == 1  # CAS once
    assert state["agents"]["a2"]["spawned_by_rule"] is not None
    assert any(e.get("truncated_return")
               for e in trace if e["event"] == "tool_call"), "no truncation marker"
    # ... and the marker actually reached the agent (root r2 obs -> r3 prompt)
    assert "[TRUNCATED" in mock.prompts[("root", 3)]
    assert any(e["event"] == "cross_workspace_write" and e["agent"] == "a2"
               for e in trace)
    # multi-round continuity: a1's round-2 prompt contains round-1's read result
    assert "plan line" in mock.prompts[("a1", 2)]
    # commit-by-reference delivered the full workspace file, uncapped
    final = state["global"]["global/final.md"]
    assert len(final["versions"][-1]["content"]) == len(long_plan)
    assert any(e["event"] == "health_verdict" for e in trace)
    print("arm R offline: OK")


def test_arm_p(tmp: Path, harnesses: dict[str, str]) -> None:
    script = {
        ("root", 1): block("spawn",
                           task="Write the part and commit it to global/part.md",
                           capsule="Planner needs the part.")
                     + block("wait", condition='state("a1")=="done"'),
        ("a1", 1): block("spawn", task="should be rejected", capsule="")
                   + block("global.commit", path="part.md", content="Part text.",
                           summary="the part"),
        ("a1", 2): block("done", summary="part committed"),
        ("root", 2): block("global.read", path="global/part.md")
                     + block("global.commit", path="final.md",
                             content="Final from planner.", summary="final")
                     + block("done", summary="planned and delivered"),
    }
    mock = MockModel(script)
    out = tmp / "p"
    m = Runtime("offline_p", "p", TASK, harnesses, Config(), out,
                Rails(max_llm_calls=50), model_fn=mock).run()
    trace = read_trace(out)
    h = m["health"]
    assert not h["systemic_failure"], h
    worker_spawn = [e for e in trace if e["event"] == "tool_call"
                    and e["agent"] == "a1" and e["tool"] == "spawn"]
    assert worker_spawn and worker_spawn[0]["error"], "worker spawn must be rejected"
    assert "unknown tool" in worker_spawn[0]["result"]
    state = json.loads((out / "state.json").read_text())
    assert state["agents"]["a1"]["role"] == "worker"
    assert state["agents"]["root"]["role"] == "planner"
    print("arm P offline: OK")


def test_arm_s(tmp: Path, harnesses: dict[str, str]) -> None:
    script = {
        ("root", 1): block("workspace.write", path="notes.md",
                           content="activation-1 notes")
                     + block("continue"),
        ("root", 2): block("spawn",
                           task="Commit the output to global/out.md",
                           capsule="One-shot producer.")
                     + block("wait", condition='state("a1")=="done"'),
        ("a1", 1): block("global.commit", path="out.md", content="Output.",
                         summary="the output"),  # no terminal, state changed
                                                 # -> implicit continue
        ("a1", 2): block("global.read", path="out.md"),
        # read-only + no terminal -> ONE grace chain...
        ("a1", 3): block("global.read", path="out.md"),
        # ...second consecutive read-only -> implicit done (fixed-point rule)
        ("root", 3): block("global.commit", path="final.md",
                           content="Final via substrate.", summary="final")
                     + block("done", summary="chained to completion"),
    }
    mock = MockModel(script)
    out = tmp / "s"
    m = Runtime("offline_s", "s", TASK, harnesses, Config(), out,
                Rails(max_llm_calls=50), model_fn=mock).run()
    trace = read_trace(out)
    h = m["health"]
    assert not h["systemic_failure"], h
    assert any(e["event"] == "implicit_continue" and e["agent"] == "a1"
               for e in trace)
    # the auto-chained agent got its nudge in the next activation
    assert "re-activated automatically" in mock.prompts[("a1", 2)]
    # ...its read-only act 2 got the one grace chain with the persist nudge...
    assert "Persist what you learned" in mock.prompts[("a1", 3)]
    # ...and the second consecutive read-only act ended it (fixed-point rule)
    assert any(e["event"] == "implicit_done_readonly" and e["agent"] == "a1"
               for e in trace)
    assert ("a1", 4) not in mock.prompts
    # delivery channel: activation 2 sees activation 1's op results, and
    # carries no transcript beyond them
    p2 = mock.prompts[("root", 2)]
    assert "RESULTS OF YOUR PREVIOUS ACTIVATION'S OPERATIONS" in p2
    assert "wrote agents/root/notes.md" in p2
    assert "activation-1 notes" not in p2  # emission text does not carry over
    p3 = mock.prompts[("root", 3)]
    assert "resumed by rule" in p3
    print("arm S offline: OK")


def test_parser() -> None:
    from .tools import parse_tool_calls
    # unclosed final fence (observed: R smoke rounds 2-3)
    calls, errs = parse_tool_calls(
        '```json\n{"tool": "done", "args": {"summary": "x"}}')
    assert calls == [{"tool": "done", "args": {"summary": "x"}}], (calls, errs)
    # invalid escape + literal newline inside string (observed: S smoke)
    calls, errs = parse_tool_calls(
        '```json\n{"tool": "done", "args": {"summary": "don\\\'t\nstop"}}\n```')
    assert calls and calls[0]["args"]["summary"] == "don't\nstop", (calls, errs)
    # Arm S action document (whole-response JSON, ops list)
    calls, errs = parse_tool_calls(
        '{"reasoning": "r", "ops": [{"tool": "continue", "args": {}}]}')
    assert calls == [{"tool": "continue", "args": {}}], (calls, errs)
    # ``` inside a single-line JSON string must not split the block
    calls, errs = parse_tool_calls(
        '```json\n{"tool": "done", "args": {"summary": "code ``` fence"}}\n```')
    assert calls and "```" in calls[0]["args"]["summary"], (calls, errs)
    print("parser edge cases: OK")


def main() -> int:
    test_parser()
    harnesses = load_harnesses()
    tmp = Path(tempfile.mkdtemp(prefix="ratd_v2_offline_"))
    test_arm_r(tmp, harnesses)
    test_arm_p(tmp, harnesses)
    test_arm_s(tmp, harnesses)
    print(f"all offline tests passed (artifacts in {tmp})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
