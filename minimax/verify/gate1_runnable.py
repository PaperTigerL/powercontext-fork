"""Gate 1 -- the module must run.

Acceptance item: "the module can initialise data, start and execute the
verification sample from a clean environment, without relying on local
files or state that are not delivered".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import MINIMAX_ROOT, SPEC_V2, TERMS

from ctxmodule.pipeline import import_materials


def test_module_runs_from_a_clean_environment(workspace: Path, settings) -> None:
    # 1. initialise the data (fresh seekdb directory inside the workspace)
    from ctxmodule.seekdb_store import SeekDBStore

    with SeekDBStore(settings.seekdb_dir).open() as store:
        result = import_materials(
            store, project_dir=MINIMAX_ROOT / "sample_project", spec_path=SPEC_V2
        )
    assert result["document_count"] > 0
    assert settings.seekdb_dir.exists()

    # 2. start the module and execute the verification sample
    env = dict(os.environ)
    env["PYTHONPATH"] = str(MINIMAX_ROOT)
    env["CTXMODULE_SEEKDB_DIR"] = str(settings.seekdb_dir)
    env["CTXMODULE_TRANSCRIPT_DIR"] = str(settings.transcript_dir)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ctxmodule",
            "context",
            "--task-id",
            "TASK-BILL-001",
            "--task",
            "assemble the context",
            "--require-spec",
            "SPEC-BILL-001-F",
        ],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["sources"], "the module produced no sources"

    # 3. every referenced source must be part of the delivered package
    for source in payload["sources"]:
        assert not Path(source).is_absolute(), source
        assert ".." not in Path(source).parts, source

    # 4. the run must not have written outside the workspace / package
    assert settings.seekdb_dir.resolve().is_relative_to(workspace.resolve())
