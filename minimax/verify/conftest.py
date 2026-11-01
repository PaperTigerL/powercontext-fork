"""Shared fixtures for the six acceptance gates.

Every gate runs against a clean workspace: a fresh seekdb directory, a
fresh PowerContext home and a fresh copy of the sample project. Nothing
outside the delivered package is required.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

MINIMAX_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MINIMAX_ROOT))

from ctxmodule.config import load_settings  # noqa: E402
from ctxmodule.pc import PowerContextClient  # noqa: E402
from ctxmodule.seekdb_store import SeekDBStore  # noqa: E402
from ctxmodule.tasks import TASK, TASK_ID, TERMS  # noqa: E402

SPEC_V1 = MINIMAX_ROOT / "sample_project" / "specs" / "billing_filter_v1.md"
SPEC_V2 = MINIMAX_ROOT / "sample_project" / "specs" / "billing_filter_v2.md"
PROJECT = MINIMAX_ROOT / "sample_project"
TRANSCRIPT_DIR = MINIMAX_ROOT / "transcript"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    path = tmp_path / "workspace"
    path.mkdir()
    return path


@pytest.fixture()
def settings(workspace: Path):
    return load_settings(
        seekdb_dir=workspace / "seekdb",
        transcript_dir=TRANSCRIPT_DIR,
        workspace=workspace,
        llm_provider="replay",
    )


@pytest.fixture()
def store(settings) -> SeekDBStore:
    with SeekDBStore(settings.seekdb_dir).open() as opened:
        yield opened


@pytest.fixture()
def powercontext_home(tmp_path: Path) -> Path:
    path = tmp_path / "powercontext-home"
    path.mkdir()
    return path


@pytest.fixture()
def server(powercontext_home: Path):
    """Start a real PowerContext Server and stop it again."""

    process, port = _start_server(powercontext_home)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        _stop_server(process)


def _powercontext_command() -> list[str]:
    """Locate the installed PowerContext console script.

    ``powercontext.cli.app`` has no ``__main__`` guard, so the module has
    to be started through the installed console script.
    """

    sibling = Path(sys.executable).parent / "powercontext"
    if sibling.exists():
        return [str(sibling)]
    found = shutil.which("powercontext")
    if found:
        return [found]
    return [sys.executable, "-m", "powercontext.cli.app"]


def _start_server(home: Path) -> tuple[subprocess.Popen, int]:
    port = free_port()
    env = dict(os.environ)
    env["POWERCONTEXT_HOME"] = str(home)
    process = subprocess.Popen(
        [
            *_powercontext_command(),
            "server",
            "run",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.time() + 90
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"PowerContext server exited early:\n{output}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return process, port
        except OSError:
            time.sleep(0.5)
    _stop_server(process)
    raise RuntimeError("PowerContext server did not become ready in time")


def _stop_server(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()
            process.wait(timeout=10)


@pytest.fixture()
def client(server: str) -> PowerContextClient:
    return PowerContextClient(server)


@pytest.fixture()
def scratch_project(tmp_path: Path) -> Path:
    """A private copy of the sample project (pre-change state)."""

    target = tmp_path / "sample_project"
    shutil.copytree(PROJECT, target)
    return target
