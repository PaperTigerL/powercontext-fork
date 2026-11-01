"""Configuration for the MiniMax SDD context module.

Everything is environment driven so that the reviewer can run the module
from a clean environment without editing source files. Placeholder
values are the defaults; real credentials are only ever read from the
environment and are never written to disk or to logs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Settings", "load_settings"]


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else default


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the context module."""

    # --- MiniMax -----------------------------------------------------
    minimax_api_key: str | None = None
    minimax_base_url: str = "https://api.minimaxi.com/v1"
    minimax_model: str = "MiniMax-M2"
    # "minimax" calls the real API; "replay" replays the recorded session.
    llm_provider: str = "replay"

    # --- PowerContext -------------------------------------------------
    powercontext_url: str = "http://127.0.0.1:8000"
    powercontext_token: str | None = None
    powercontext_scope_title: str = "MiniMax SDD context"

    # --- seekdb -------------------------------------------------------
    seekdb_dir: Path = field(default_factory=lambda: Path("./.ctxmodule-data/seekdb"))

    # --- workspace ----------------------------------------------------
    workspace: Path = field(default_factory=lambda: Path("./.ctxmodule-data"))
    transcript_dir: Path = field(default_factory=lambda: Path("./transcript"))

    def scope_idempotency_key(self, task_id: str) -> str:
        return f"minimax-sdd-{task_id}"


def load_settings(**overrides: object) -> Settings:
    """Build settings from the environment, applying explicit overrides."""

    settings = Settings(
        minimax_api_key=os.environ.get("MINIMAX_API_KEY"),
        minimax_base_url=os.environ.get(
            "MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"
        ),
        minimax_model=os.environ.get("MINIMAX_MODEL", "MiniMax-M2"),
        llm_provider=os.environ.get("CTXMODULE_LLM_PROVIDER", "replay"),
        powercontext_url=os.environ.get(
            "POWERCONTEXT_URL", "http://127.0.0.1:8000"
        ).rstrip("/"),
        powercontext_token=os.environ.get("POWERCONTEXT_TOKEN"),
        powercontext_scope_title=os.environ.get(
            "POWERCONTEXT_SCOPE_TITLE", "MiniMax SDD context"
        ),
        seekdb_dir=_env_path(
            "CTXMODULE_SEEKDB_DIR", Path("./.ctxmodule-data/seekdb")
        ),
        workspace=_env_path("CTXMODULE_WORKSPACE", Path("./.ctxmodule-data")),
        transcript_dir=_env_path(
            "CTXMODULE_TRANSCRIPT_DIR", Path("./transcript")
        ),
    )
    if overrides:
        settings = Settings(**{**settings.__dict__, **overrides})  # type: ignore[arg-type]
    return settings
