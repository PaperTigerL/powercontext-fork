"""Start and stop a real PowerContext Server.

``powercontext.cli.app`` has no ``__main__`` guard, so the module has to be
started through the installed console script. This helper is shared by the
acceptance gates (``verify/conftest.py``) and by
``scripts/dump_usage.py``, which records the PowerContext state write/read
cycle as technical usage evidence.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

__all__ = ["free_port", "powercontext_command", "start_server", "stop_server"]


def free_port() -> int:
    """Return a free TCP port on the loopback interface."""

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def powercontext_command() -> list[str]:
    """Locate the installed PowerContext console script."""

    sibling = Path(sys.executable).parent / "powercontext"
    if sibling.exists():
        return [str(sibling)]
    found = shutil.which("powercontext")
    if found:
        return [found]
    return [sys.executable, "-m", "powercontext.cli.app"]


def start_server(home: Path, timeout: float = 90.0) -> tuple[subprocess.Popen, int]:
    """Start PowerContext on a free port and wait until it answers."""

    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    port = free_port()
    env = dict(os.environ)
    env["POWERCONTEXT_HOME"] = str(home)
    process = subprocess.Popen(
        [
            *powercontext_command(),
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

    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"PowerContext server exited early:\n{output}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return process, port
        except OSError:
            time.sleep(0.5)
    stop_server(process)
    raise RuntimeError("PowerContext server did not become ready in time")


def stop_server(process: subprocess.Popen) -> None:
    """Terminate a server started by :func:`start_server`."""

    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:  # pragma: no cover - best effort
            process.kill()
            process.wait(timeout=10)
