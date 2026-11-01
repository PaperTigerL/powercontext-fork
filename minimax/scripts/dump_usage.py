"""Collect the technical usage records (material 5).

    python scripts/dump_usage.py

Writes into ``artifacts/usage/``:

* ``seekdb-queries.txt``      -- the SQL that was executed and its results
* ``minimax-usage.json``      -- a summary of the recorded MiniMax session
* ``powercontext-state.txt``  -- the PowerContext state write / read-back cycle

The PowerContext part starts a real PowerContext Server, runs the real
pipeline so that the task state is written, restarts the server and reads the
state back. That write -> restart -> read cycle is exactly the evidence the
acceptance item "state can be reused" asks for.

Both the seekdb directory and the PowerContext home must live on a **local
Linux file system**. On a ``/mnt/<drive>`` mount (a Windows drive mounted into
WSL) seekdb fails with ``seekdb_open failed: code=-1`` and the SQLite file
cannot be locked. The script therefore defaults to a temporary directory and
honours ``CTXMODULE_SEEKDB_DIR`` / ``POWERCONTEXT_HOME`` when they are set to
a local path.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MINIMAX_ROOT = HERE.parent
sys.path.insert(0, str(MINIMAX_ROOT))

from ctxmodule.config import load_settings  # noqa: E402
from ctxmodule.pc import PowerContextClient  # noqa: E402
from ctxmodule.pc_server import start_server, stop_server  # noqa: E402
from ctxmodule.pipeline import (  # noqa: E402
    build_context,
    execute_task,
    import_materials,
)
from ctxmodule.seekdb_store import SeekDBStore  # noqa: E402
from ctxmodule.tasks import REQUIRED_SPEC_IDS, TASK, TASK_ID, TERMS  # noqa: E402

PROJECT = MINIMAX_ROOT / "sample_project"
SPEC = PROJECT / "specs" / "billing_filter_v2.md"


def _local_dir(env_name: str, prefix: str) -> Path:
    """Return a writable directory on a local (non ``/mnt``) file system."""

    raw = os.environ.get(env_name)
    if raw:
        path = Path(raw).expanduser().resolve()
    else:
        path = Path(tempfile.mkdtemp(prefix=prefix))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _record_seekdb(settings, usage_dir: Path) -> None:
    """Store the project material in seekdb and record the queries."""

    with SeekDBStore(settings.seekdb_dir).open() as store:
        import_materials(store, project_dir=PROJECT, spec_path=SPEC)
        context = build_context(
            store,
            task_id=TASK_ID,
            task=TASK,
            terms=TERMS,
            required_spec_ids=REQUIRED_SPEC_IDS,
        )
        rows = store.search(TERMS, limit=50)
        lines = [
            "# seekdb usage record",
            "",
            "database directory : " + str(settings.seekdb_dir),
            f"table              : {store.TABLE}",
            f"document count     : {store.count()}",
            "",
            "-- documents returned by the selection query --",
        ]
        for document in rows:
            lines.append(
                f"{document.doc_id}\t{document.kind}\t{document.path}\t"
                f"{document.source_hash[:16]}"
            )
        lines += ["", "-- context sources --"] + [
            f"  {source}" for source in context["sources"]
        ]
        (usage_dir / "seekdb-queries.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )


def _record_minimax(usage_dir: Path) -> None:
    """Summarise the recorded MiniMax development session."""

    transcript = MINIMAX_ROOT / "transcript" / "minimax_session.jsonl"
    if not transcript.exists():
        return
    records = [
        json.loads(line)
        for line in transcript.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = [
        {
            "role": record.get("role"),
            "provider": record.get("provider"),
            "mode": record.get("mode"),
            "model": record.get("model"),
            "task_id": record.get("task_id"),
            "context_digest": record.get("context_digest"),
            "context_sources": record.get("context_sources"),
            "applied_files": record.get("applied_files"),
            "diff_sha256": record.get("diff_sha256"),
        }
        for record in records
    ]
    (usage_dir / "minimax-usage.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _record_powercontext(settings, usage_dir: Path) -> None:
    """Write the task state into PowerContext, restart, read it back."""

    home = _local_dir("POWERCONTEXT_HOME", "ctxmodule-powercontext-")
    note = usage_dir / "powercontext-state.txt"

    lines = [
        "# PowerContext usage record",
        "",
        "server command : powercontext server run --host 127.0.0.1 --port <free>",
        f"POWERCONTEXT_HOME : {home}",
        f"scope title       : {settings.powercontext_scope_title}",
        f"idempotency key   : {settings.scope_idempotency_key(TASK_ID)}",
        "",
        "-- step 1: the real pipeline writes the task state --",
    ]

    def _write(url: str) -> dict[str, object]:
        client = PowerContextClient(url)
        with SeekDBStore(settings.seekdb_dir).open() as store:
            import_materials(store, project_dir=PROJECT, spec_path=SPEC)
            result = execute_task(
                settings,
                store=store,
                client=client,
                task_id=TASK_ID,
                task=TASK,
                terms=TERMS,
                required_spec_ids=REQUIRED_SPEC_IDS,
            )
        return {
            "scope_id": result.state.scope_id,
            "state": result.state.to_dict(),
            "context_digest": result.digest,
            "context_sources": result.usage_record.get("context_sources"),
        }

    def _read(url: str) -> dict[str, object]:
        client = PowerContextClient(url)
        scope_id = client.ensure_scope(
            settings.powercontext_scope_title, settings.scope_idempotency_key(TASK_ID)
        )
        state = client.load_task_state(scope_id=scope_id, task_id=TASK_ID)
        prepared = client.prepare_context(
            scope_id=scope_id, query=f"{TASK_ID} status", max_bytes=8192
        )
        return {
            "scope_id": scope_id,
            "state": state.to_dict() if state else None,
            "prepared_context": (prepared.get("content") or "")[:4000],
        }

    written: dict[str, object] = {}
    process, port = start_server(home)
    try:
        written = _write(f"http://127.0.0.1:{port}")
    finally:
        stop_server(process)
    lines += [
        "  state written    : " + json.dumps(written.get("state"), ensure_ascii=False),
        "  scope id         : " + str(written.get("scope_id")),
        "  context digest   : " + str(written.get("context_digest")),
        "",
        "-- step 2: the server is restarted and the state is read back --",
    ]

    read_back: dict[str, object] = {}
    process, port = start_server(home)
    try:
        read_back = _read(f"http://127.0.0.1:{port}")
    finally:
        stop_server(process)
    lines += [
        "  state read back  : "
        + json.dumps(read_back.get("state"), ensure_ascii=False),
        "",
        "-- context prepared from the recovered state --",
        str(read_back.get("prepared_context") or ""),
    ]
    note.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    usage_dir = MINIMAX_ROOT / "artifacts" / "usage"
    usage_dir.mkdir(parents=True, exist_ok=True)

    settings = load_settings(
        transcript_dir=MINIMAX_ROOT / "transcript",
        seekdb_dir=_local_dir("CTXMODULE_SEEKDB_DIR", "ctxmodule-seekdb-"),
        workspace=MINIMAX_ROOT / ".ctxmodule-data",
    )

    _record_seekdb(settings, usage_dir)
    _record_minimax(usage_dir)
    _record_powercontext(settings, usage_dir)

    print(json.dumps({"usage_dir": str(usage_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
