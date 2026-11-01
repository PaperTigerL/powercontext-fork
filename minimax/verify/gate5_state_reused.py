"""Gate 5 -- the task state can be reused after a restart.

Acceptance item: "starting from an empty state, save the task record,
restart the module, read it back and use it for the follow-up context or
task processing".
"""

from __future__ import annotations

from pathlib import Path

from conftest import _start_server, _stop_server

from ctxmodule.pc import PowerContextClient, TaskState


def test_task_state_survives_a_restart(powercontext_home: Path) -> None:
    # --- empty state -------------------------------------------------
    process, port = _start_server(powercontext_home)
    try:
        client = PowerContextClient(f"http://127.0.0.1:{port}")
        assert client.health(), "the PowerContext server is not healthy"
        scope_id = client.ensure_scope("MiniMax SDD context", "gate5-scope")
        assert client.load_task_state(scope_id=scope_id, task_id="TASK-BILL-001") is None
        client.save_task_state(
            TaskState(
                task_id="TASK-BILL-001",
                scope_id=scope_id,
                status="change-applied",
                spec_ids=("SPEC-BILL-001-F",),
                changed_files=("src/billing/filter.py",),
                tests={"target": "passed", "regression": "passed"},
                notes="status filter implemented",
            )
        )
    finally:
        _stop_server(process)

    # --- restart the module (and the server it talks to) -------------
    process, port = _start_server(powercontext_home)
    try:
        client = PowerContextClient(f"http://127.0.0.1:{port}")
        scope_id = client.ensure_scope("MiniMax SDD context", "gate5-scope")
        state = client.load_task_state(scope_id=scope_id, task_id="TASK-BILL-001")
        assert state is not None, (
            "the task state did not survive the restart"
        )
        assert state.status == "change-applied"
        assert state.spec_ids == ("SPEC-BILL-001-F",)
        assert state.changed_files == ("src/billing/filter.py",)
        assert state.tests["target"] == "passed"

        # The recovered state must be usable for the follow-up work.
        prepared = client.prepare_context(
            scope_id=scope_id, query="TASK-BILL-001 status", max_bytes=8192
        )
        content = prepared.get("content") or ""
        assert "TASK-BILL-001" in content
    finally:
        _stop_server(process)
