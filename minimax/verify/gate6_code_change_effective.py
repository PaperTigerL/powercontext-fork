"""Gate 6 -- the code change is effective.

Acceptance item: "the same target feature tests fail before the change
because the target behaviour is not implemented, pass after the change,
and the related regression tests pass as well".

The failure before the change must be caused by the missing behaviour --
never by a missing dependency, a broken import or an unreachable service.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from conftest import MINIMAX_ROOT, TRANSCRIPT_DIR

from ctxmodule.pipeline import apply_patch, run_tests


def _is_collection_error(output: str) -> bool:
    markers = (
        "error collecting",
        "ModuleNotFoundError",
        "ImportError while importing test module",
        "ERROR collecting",
    )
    return any(marker in output for marker in markers)


def _artifacts_dir() -> Path:
    return Path(
        os.environ.get("CTXMODULE_ARTIFACTS_DIR", MINIMAX_ROOT / "artifacts")
    )


def _code_version() -> str:
    """The commit the logs belong to."""

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=MINIMAX_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:  # pragma: no cover - git may be unavailable
        return "unknown"


def test_target_tests_fail_before_and_pass_after(scratch_project: Path, tmp_path: Path) -> None:
    artifacts = _artifacts_dir()
    artifacts.mkdir(parents=True, exist_ok=True)
    version = _code_version()
    patch_text = (TRANSCRIPT_DIR / "feature.patch").read_text(encoding="utf-8")

    # --- before the change -------------------------------------------
    before = run_tests(scratch_project, "tests/test_target.py")
    before["code_version"] = version
    (artifacts / "target-tests-before.log").write_text(
        json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert before["exit_code"] != 0, (
        "the target feature tests already pass before the change; "
        "the sample project does not demonstrate the missing behaviour"
    )
    assert not _is_collection_error(before["stdout"] + before["stderr"]), (
        "the target tests failed for an environment reason instead of the "
        "missing behaviour"
    )
    assert "unexpected keyword argument 'status'" in before["stdout"], (
        "the target tests did not fail because the target behaviour is missing"
    )

    # --- apply the recorded change -----------------------------------
    applied, message = apply_patch(scratch_project, patch_text)
    assert applied, f"the recorded patch did not apply: {message}"

    # --- after the change --------------------------------------------
    after = run_tests(scratch_project, "tests/test_target.py")
    after["code_version"] = version
    (artifacts / "target-tests-after.log").write_text(
        json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert after["passed"], (
        "the target feature tests still fail after the change:\n" + after["stdout"]
    )

    # --- regression ---------------------------------------------------
    regression = run_tests(scratch_project, "tests/test_regression.py")
    regression["code_version"] = version
    (artifacts / "regression-tests-after.log").write_text(
        json.dumps(regression, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    assert regression["passed"], (
        "the regression tests fail after the change:\n" + regression["stdout"]
    )

    # --- the logs must record command and exit code ------------------
    for record in (before, after, regression):
        assert record["command"]
        assert isinstance(record["exit_code"], int)
