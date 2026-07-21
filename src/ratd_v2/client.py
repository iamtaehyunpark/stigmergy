"""LLM client for the v2 runtime.

Ported from v1 src/phase1.py with two changes:
- no forced ``response_format: json_object`` (multi-round ReAct rounds
  are free text with embedded tool-call blocks); Arm S / judge callers
  may request it per call.
- token usage (prompt/completion) is captured and returned — the ET
  cost axis is measured in tokens, not only chars.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "qwen3.6"
DEFAULT_PROVIDER = "local"
# Port 8001 = OUR vLLM instance (GPU 0). Port 8000 on galaxy-05 belongs to
# another user (samuelyeh) — never point anything at it.
DEFAULT_LOCAL_ENDPOINT = "http://127.0.0.1:8001/v1/chat/completions"
DEFAULT_MAX_TOKENS = 16000   # E1 + v2 smoke: 8k cut whole-chapter emissions
                             # mid-JSON; the cap is an architecture-independent
                             # confounder, so it is set clear of the task shapes


@dataclass(frozen=True)
class Config:
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    max_tokens: int = DEFAULT_MAX_TOKENS
    local_endpoint: str = DEFAULT_LOCAL_ENDPOINT


@dataclass(frozen=True)
class ModelReply:
    text: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str = "stop"    # "length" = output cap hit mid-emission


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=False)
        f.write("\n")


def ensure_credentials(config: Config) -> None:
    if config.provider == "local":
        if not config.local_endpoint:
            raise RuntimeError("local endpoint is not set")
        return
    if config.provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    if config.provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    if config.provider not in {"local", "anthropic", "openai"}:
        raise RuntimeError(f"Unsupported provider: {config.provider}")


def _http_json(req: urllib.request.Request, provider: str,
               timeout: int = 900, retries: int = 4) -> dict[str, Any]:
    # A transient endpoint blip or slow generation must not crash a
    # multi-hour unattended run; only 4xx fails fast.
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if 500 <= exc.code < 600 and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"{provider} API error {exc.code}: {body}") from exc
        except (urllib.error.URLError, http.client.HTTPException,
                TimeoutError, ConnectionError, OSError) as exc:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"{provider} API connection failed after {retries + 1} attempts: {exc}"
            ) from exc
    raise RuntimeError("unreachable")


def call_model(messages: list[dict[str, str]], config: Config,
               json_mode: bool = False) -> ModelReply:
    """messages = full chat list incl. system message."""
    if config.provider == "local":
        def _local_request(max_tokens: int) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "model": config.model,
                "temperature": config.temperature,
                "max_tokens": max_tokens,
                "chat_template_kwargs": {"enable_thinking": False},
                "messages": messages,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            req = urllib.request.Request(
                config.local_endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST",
            )
            return _http_json(req, "local")

        try:
            data = _local_request(config.max_tokens)
        except RuntimeError as exc:
            # context-length 400: the server reports our input token count
            # and its limit — clamp the output budget once and retry rather
            # than crashing a multi-hour run. Below a 1024-token floor the
            # prompt itself is the problem; re-raise for the runtime's roof.
            m = re.search(r"passed (\d+) input tokens.*?context length is "
                          r"only (\d+)", str(exc))
            if not m:
                raise
            room = int(m.group(2)) - int(m.group(1)) - 64
            if room < 1024:
                raise
            data = _local_request(room)
    elif config.provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        payload = {
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "messages": messages,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json",
                     "authorization": f"Bearer {api_key}"},
            method="POST",
        )
        data = _http_json(req, "openai")
    elif config.provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        system = ""
        rest = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                rest.append(m)
        payload = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": system,
            "messages": rest,
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json", "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"},
            method="POST",
        )
        data = _http_json(req, "anthropic")
        usage = data.get("usage", {})
        text = "".join(i.get("text", "") for i in data.get("content", [])
                       if i.get("type") == "text").strip()
        fin = ("length" if data.get("stop_reason") == "max_tokens" else "stop")
        return ModelReply(text, int(usage.get("input_tokens", 0)),
                          int(usage.get("output_tokens", 0)), fin)
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")

    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content")
    if not isinstance(content, str):
        reasoning = message.get("reasoning")
        content = reasoning if isinstance(reasoning, str) else ""
    usage = data.get("usage", {}) or {}
    return ModelReply(content.strip(),
                      int(usage.get("prompt_tokens", 0) or 0),
                      int(usage.get("completion_tokens", 0) or 0),
                      str(choice.get("finish_reason") or "stop"))
