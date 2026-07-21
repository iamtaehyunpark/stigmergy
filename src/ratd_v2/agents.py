"""Agent records — Playground Spec v2 §1.

The runtime tracks identity, lifecycle, the bounded rolling window,
and per-agent cost tallies. Everything semantic is the agent's job.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# lifecycle: spawned -> running -> waiting | done | failed | terminated
RUNNABLE_STATES = {"spawned", "running"}
TERMINAL_STATES = {"done", "failed", "terminated"}


@dataclass
class WindowEntry:
    round: int
    assistant: str            # the model's full round output
    observation: str          # the tool results / observations delivered back


@dataclass
class Agent:
    id: str
    role: str                 # planner | worker | ratd | stig
    task: str
    capsule: str
    root_goal: str
    parent: Optional[str] = None
    initial_refs: list[str] = field(default_factory=list)
    spawned_by_rule: Optional[str] = None
    state: str = "spawned"
    rounds: int = 0           # rounds used (= activations for Arm S)
    window: list[WindowEntry] = field(default_factory=list)
    pending_obs: list[str] = field(default_factory=list)  # delivered next round
    done_summary: str = ""
    fail_reason: str = ""
    wait_rule: Optional[str] = None
    readonly_chain: int = 0   # consecutive read-only implicit chains (Arm S)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    prompt_chars: list[int] = field(default_factory=list)  # per-round prompt size

    def runnable(self) -> bool:
        return self.state in RUNNABLE_STATES

    def public_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "state": self.state,
            "parent": self.parent,
            "rounds": self.rounds,
            "task": self.task[:160],
        }
