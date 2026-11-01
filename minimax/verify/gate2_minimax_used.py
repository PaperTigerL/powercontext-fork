"""Gate 2 -- MiniMax actually participated.

Acceptance item: "the development record contains this task, the context
that was provided and the code modification process, and corresponds to
the submitted code diff".
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from conftest import (
    MINIMAX_ROOT,
    SPEC_V2,
    TASK_ID,
    TERMS,
    TRANSCRIPT_DIR,
)

from ctxmodule.llm import context_digest
from ctxmodule.pipeline import build_context, import_materials
from ctxmodule.tasks import REQUIRED_SPEC_IDS, TASK


def _records() -> list[dict]:
    path = TRANSCRIPT_DIR / "minimax_session.jsonl"
    assert path.exists(), f"missing MiniMax development record: {path}"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_minimax_session_matches_context_and_diff(store) -> None:
    import_materials(
        store, project_dir=MINIMAX_ROOT / "sample_project", spec_path=SPEC_V2
    )
    context = build_context(
        store,
        task_id=TASK_ID,
        task=TASK,
        terms=TERMS,
        required_spec_ids=REQUIRED_SPEC_IDS,
    )
    digest = context_digest(context)

    records = _records()
    assistant = [
        record
        for record in records
        if record.get("role") == "assistant" and record.get("task_id") == TASK_ID
    ]
    assert assistant, "the development record contains no assistant turn for the task"

    record = assistant[-1]
    assert record.get("provider") == "minimax"

    # The recorded session must have used exactly this context.
    assert record.get("context_digest") == digest, (
        "the recorded MiniMax session was produced with a different context; "
        "re-record it with scripts/record_session.py"
    )

    # The recorded session must reference the material the module selects.
    assert set(record.get("context_sources", [])) == set(context["sources"])

    # The recorded diff must be the diff that is shipped.
    patch_path = TRANSCRIPT_DIR / "feature.patch"
    assert patch_path.exists(), f"missing recorded patch: {patch_path}"
    patch_text = patch_path.read_text(encoding="utf-8")
    assert hashlib.sha256(patch_text.encode("utf-8")).hexdigest() == record.get(
        "diff_sha256"
    ), "the shipped patch does not match the recorded session"

    # The recorded session must name the files it changed.
    applied = set(record.get("applied_files", []))
    assert applied, "the development record does not name any changed file"
    for relative in applied:
        assert f"a/{relative}" in patch_text, relative

    # The session must be a real MiniMax recording, not the offline bootstrap.
    if os.environ.get("CTXMODULE_ALLOW_BOOTSTRAP_RECORDING") == "1":
        pytest.skip(
            "CTXMODULE_ALLOW_BOOTSTRAP_RECORDING=1: the live-recording check is "
            "skipped (development only)"
        )
    assert record.get("mode") == "live", (
        "the shipped development record is an offline bootstrap recording; "
        "run 'python scripts/record_session.py --live' with your own "
        "MINIMAX_API_KEY before submitting"
    )
