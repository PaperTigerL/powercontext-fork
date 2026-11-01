"""MiniMax integration.

Two providers are supported:

``minimax``
    Calls the MiniMax chat-completions endpoint over HTTP using the
    key from ``MINIMAX_API_KEY``. The key is never written to disk.

``replay`` (default)
    Replays the recorded development session in
    ``transcript/minimax_session.jsonl``. This keeps the self-test
    deterministic and offline while still proving that the recorded
    session matches the context the module actually assembles.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["MiniMaxClient", "ReplayClient", "LLMError", "build_client", "context_digest"]


class LLMError(RuntimeError):
    """Raised when the model provider cannot serve a request."""


def context_digest(context: dict[str, Any]) -> str:
    """Stable digest of the assembled development context."""

    canonical = json.dumps(context, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class MiniMaxClient:
    """Call the MiniMax chat-completions API."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.minimaxi.com/v1",
        model: str = "MiniMax-M2",
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise LLMError("MINIMAX_API_KEY is not set")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]], *, task_id: str = "") -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"MiniMax HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"MiniMax unreachable: {exc.reason}") from exc
        try:
            return str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected MiniMax response shape: {body}") from exc


class ReplayClient:
    """Replay a recorded MiniMax session."""

    def __init__(self, transcript_path: Path | str) -> None:
        self.transcript_path = Path(transcript_path)
        if not self.transcript_path.exists():
            raise LLMError(
                f"transcript not found: {self.transcript_path}; "
                "run the recorded session first or set CTXMODULE_LLM_PROVIDER=minimax"
            )
        self.records = [
            json.loads(line)
            for line in self.transcript_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def chat(self, messages: list[dict[str, str]], *, task_id: str = "") -> str:
        """Return the recorded assistant reply for this task.

        The recorded reply carries the digest of the context that was
        given to MiniMax. When a digest is supplied through the system
        message it must match, which proves the recorded session was
        produced with exactly this context.
        """

        expected = _digest_from_messages(messages)
        candidates = [
            record
            for record in self.records
            if record.get("role") == "assistant"
            and (not task_id or record.get("task_id") in (None, "", task_id))
        ]
        if not candidates:
            raise LLMError(f"no recorded assistant reply for task {task_id!r}")
        if expected:
            for record in candidates:
                if record.get("context_digest") == expected:
                    return str(record.get("content", ""))
            raise LLMError(
                "recorded session does not match the assembled context: "
                f"expected digest {expected}, recorded "
                f"{[record.get('context_digest') for record in candidates]}"
            )
        return str(candidates[-1].get("content", ""))


def _digest_from_messages(messages: list[dict[str, str]]) -> str | None:
    for message in messages:
        text = message.get("content", "")
        marker = "CONTEXT_DIGEST:"
        if marker in text:
            return text.split(marker, 1)[1].strip().splitlines()[0].strip()
    return None


def build_client(settings: Any) -> MiniMaxClient | ReplayClient:
    """Build the configured provider."""

    provider = (settings.llm_provider or "replay").lower()
    if provider == "minimax":
        return MiniMaxClient(
            api_key=settings.minimax_api_key or "",
            base_url=settings.minimax_base_url,
            model=settings.minimax_model,
        )
    if provider == "replay":
        return ReplayClient(settings.transcript_dir / "minimax_session.jsonl")
    raise LLMError(f"unknown CTXMODULE_LLM_PROVIDER={provider!r}")
