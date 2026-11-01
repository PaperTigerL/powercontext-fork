"""Collect the technical usage records (material 5).

    python scripts/dump_usage.py

Writes into ``artifacts/usage/``:

* ``seekdb-queries.txt``   -- the SQL that was executed and its results
* ``minimax-usage.json``   -- a summary of the recorded MiniMax session
* ``powercontext-state.txt`` -- the task state read back from PowerContext
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MINIMAX_ROOT = HERE.parent
sys.path.insert(0, str(MINIMAX_ROOT))

from ctxmodule.config import load_settings  # noqa: E402
from ctxmodule.pipeline import build_context, import_materials  # noqa: E402
from ctxmodule.seekdb_store import SeekDBStore  # noqa: E402
from ctxmodule.tasks import REQUIRED_SPEC_IDS, TASK, TASK_ID, TERMS  # noqa: E402

PROJECT = MINIMAX_ROOT / "sample_project"
SPEC = PROJECT / "specs" / "billing_filter_v2.md"


def main() -> int:
    usage_dir = MINIMAX_ROOT / "artifacts" / "usage"
    usage_dir.mkdir(parents=True, exist_ok=True)

    settings = load_settings(
        transcript_dir=MINIMAX_ROOT / "transcript",
        seekdb_dir=Path(
            os.environ.get(
                "CTXMODULE_SEEKDB_DIR", MINIMAX_ROOT / ".ctxmodule-data" / "seekdb"
            )
        ),
    )

    # --- seekdb -------------------------------------------------------
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
            f"database directory : {settings.seekdb_dir}",
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

    # --- MiniMax -----------------------------------------------------
    transcript = MINIMAX_ROOT / "transcript" / "minimax_session.jsonl"
    if transcript.exists():
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

    # --- PowerContext -------------------------------------------------
    powercontext_note = MINIMAX_ROOT / "artifacts" / "powercontext-state.txt"
    if os.environ.get("POWERCONTEXT_URL"):
        from ctxmodule.pc import PowerContextClient  # noqa: E402

        client = PowerContextClient(
            os.environ["POWERCONTEXT_URL"], os.environ.get("POWERCONTEXT_TOKEN")
        )
        scope_id = client.ensure_scope(
            settings.powercontext_scope_title, settings.scope_idempotency_key(TASK_ID)
        )
        state = client.load_task_state(scope_id=scope_id, task_id=TASK_ID)
        powercontext_note.write_text(
            json.dumps(
                state.to_dict() if state else {"found": False},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        powercontext_note.write_text(
            "POWERCONTEXT_URL is not set; start the server and run:\n"
            "  POWERCONTEXT_URL=http://127.0.0.1:8000 python scripts/dump_usage.py\n",
            encoding="utf-8",
        )

    print(json.dumps({"usage_dir": str(usage_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
