"""PowerContext HTTP client and task-state storage.

The module talks to a local PowerContext Server over its documented HTTP
API:

* ``POST /v1/scopes``            -- create (or reuse) a scope
* ``POST /v1/sources/content``    -- capture a Source
* ``POST /v1/memory/remember``    -- write an explicit Memory entry
* ``POST /v1/context/prepare``    -- read bounded context back

Only the standard library is used so that the module starts in a clean
environment without extra packages. The bearer token is read from the
environment and is never placed in a URL, a log line or a Memory entry.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

__all__ = ["PowerContextClient", "PowerContextUnavailable", "TaskState"]


class PowerContextUnavailable(RuntimeError):
    """Raised when the PowerContext Server cannot be reached."""


@dataclass(frozen=True)
class TaskState:
    """The persisted state of one development task."""

    task_id: str
    scope_id: str
    status: str
    spec_ids: tuple[str, ...]
    changed_files: tuple[str, ...]
    tests: dict[str, str]
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "scope_id": self.scope_id,
            "status": self.status,
            "spec_ids": list(self.spec_ids),
            "changed_files": list(self.changed_files),
            "tests": dict(self.tests),
            "notes": self.notes,
        }


class PowerContextClient:
    """Minimal client for the PowerContext Server HTTP API."""

    def __init__(self, base_url: str, token: str | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    # -- plumbing ------------------------------------------------------
    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                status = response.status
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self._log_call(path, payload, status=exc.code, error=detail)
            raise PowerContextUnavailable(
                f"PowerContext {path} failed with HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            self._log_call(path, payload, status=0, error=str(exc.reason))
            raise PowerContextUnavailable(
                f"PowerContext {path} is unreachable at {self.base_url}: {exc.reason}"
            ) from exc
        self._log_call(path, payload, status=status)
        if not body.strip():
            return {}
        return json.loads(body)

    def _log_call(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        status: int,
        error: str | None = None,
    ) -> None:
        """Append the call to the usage log when one is configured.

        The log is the PowerContext half of the technical usage record.
        Credentials are never written: only the request path, the payload
        keys and the response status.
        """

        target = os.environ.get("CTXMODULE_HTTP_LOG")
        if not target:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "method": "POST",
            "path": path,
            "payload_keys": sorted(payload.keys()),
            "status": status,
        }
        if error:
            record["error"] = error
        try:
            with open(target, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:  # pragma: no cover - logging must never break the flow
            pass

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.base_url}/health/live", timeout=self.timeout
            ) as response:
                return 200 <= response.status < 300
        except Exception:
            return False

    # -- API -----------------------------------------------------------
    def ensure_scope(self, title: str, idempotency_key: str) -> str:
        """Create a scope and return its id (idempotent per key)."""

        result = self.post(
            "/v1/scopes",
            {
                "title": title,
                "summary": title,
                "idempotency_key": idempotency_key,
            },
        )
        scope_id = result.get("scope_id")
        if not scope_id:
            raise PowerContextUnavailable(f"scope creation returned no scope_id: {result}")
        return str(scope_id)

    def capture_source(
        self,
        *,
        scope_id: str,
        source_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.post(
            "/v1/sources/content",
            {
                "scope_id": scope_id,
                "source_id": source_id,
                "content": content,
                "metadata": metadata or {},
            },
        )

    def remember(
        self, *, scope_id: str, kind: str, text: str, reason: str
    ) -> dict[str, Any]:
        return self.post(
            "/v1/memory/remember",
            {
                "scope_id": scope_id,
                "kind": kind,
                "text": text,
                "reason": reason,
            },
        )

    def prepare_context(
        self, *, scope_id: str, query: str, max_bytes: int = 8000
    ) -> dict[str, Any]:
        return self.post(
            "/v1/context/prepare",
            {"scope_id": scope_id, "query": query, "max_bytes": max_bytes},
        )

    # -- task state ----------------------------------------------------
    STATE_MARKER = "CTXMODULE_STATE_JSON:"

    def save_task_state(self, state: TaskState) -> None:
        """Persist the task state so that it survives a module restart.

        The state is written twice on purpose:

        * as a Source, so that the raw record keeps its provenance, and
        * as a Memory entry, so that a later ``/v1/context/prepare`` call
          returns it inside the prepared context and the module can read
          it back after a restart.
        """

        payload = json.dumps(state.to_dict(), ensure_ascii=False, sort_keys=True)
        self.capture_source(
            scope_id=state.scope_id,
            source_id=f"task-state:{state.task_id}",
            content=payload,
            metadata={
                "origin": "minimax-sdd-context-module",
                "task_id": state.task_id,
                "status": state.status,
                "kind": "task-state",
            },
        )
        self.remember(
            scope_id=state.scope_id,
            kind="decision",
            text=(
                f"Task {state.task_id} status={state.status}; "
                f"changed files: {', '.join(state.changed_files) or 'none'}; "
                f"tests: {json.dumps(state.tests, ensure_ascii=False, sort_keys=True)}"
                f"\n{self.STATE_MARKER}{payload}"
            ),
            reason=f"Task state saved by the MiniMax SDD context module ({state.task_id})",
        )

    def load_task_state(self, *, scope_id: str, task_id: str) -> TaskState | None:
        """Read the task state back, e.g. after the module was restarted."""

        prepared = self.prepare_context(
            scope_id=scope_id, query=f"task state {task_id}", max_bytes=32768
        )
        content = prepared.get("content") or ""
        for payload in _extract_json_objects(content, self.STATE_MARKER):
            data = _parse_state_payload(payload)
            if data is None:
                continue
            if str(data.get("task_id", "")) != task_id:
                continue
            return TaskState(
                task_id=str(data.get("task_id", task_id)),
                scope_id=str(data.get("scope_id", scope_id)),
                status=str(data.get("status", "unknown")),
                spec_ids=tuple(data.get("spec_ids", ())),
                changed_files=tuple(data.get("changed_files", ())),
                tests=dict(data.get("tests", {})),
                notes=str(data.get("notes", "")),
            )
        return None


def _parse_state_payload(payload: str) -> dict[str, Any] | None:
    """Parse a state payload.

    The prepared context embeds the payload inside a JSON envelope, so the
    inner quotes are backslash escaped. Try the raw text first and fall
    back to the unescaped form.
    """

    for candidate in (payload, payload.replace('\\"', '"')):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _extract_json_objects(text: str, marker: str) -> list[str]:
    """Extract every JSON object that follows ``marker`` in ``text``."""

    objects: list[str] = []
    start = 0
    while True:
        index = text.find(marker, start)
        if index < 0:
            return objects
        cursor = index + len(marker)
        while cursor < len(text) and text[cursor] in " \t\r\n":
            cursor += 1
        if cursor >= len(text) or text[cursor] != "{":
            start = index + len(marker)
            continue
        depth = 0
        for position in range(cursor, len(text)):
            char = text[position]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    objects.append(text[cursor : position + 1])
                    start = position + 1
                    break
        else:
            return objects
