"""Event trace — logging is the product (handoff rule 4).

One JSONL file per run. Every LLM call, every tool call, every state
event, every circuit edit (before/after), every lifecycle transition,
and the final health verdict flow through here. The ET metrics and the
emergence inventory must be computable from this file alone.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class Trace:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f = path.open("a", encoding="utf-8")
        self._seq = 0

    def log(self, event: str, **data: Any) -> None:
        self._seq += 1
        rec = {"seq": self._seq, "ts": round(time.time(), 3), "event": event, **data}
        self._f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()
