"""Command line entry point of the context module.

    python -m ctxmodule import   --project ../sample_project --spec ../sample_project/specs/billing_filter_v2.md
    python -m ctxmodule context  --task-id TASK-BILL-001 --task "..."
    python -m ctxmodule state    --task-id TASK-BILL-001
    python -m ctxmodule pipeline --task-id TASK-BILL-001 --task "..."

Every command prints a JSON document on stdout so that the output can be
diffed or checked by the acceptance tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_settings
from .pc import PowerContextClient
from .pipeline import (
    build_context,
    execute_task,
    import_materials,
)
from .seekdb_store import SeekDBStore

__all__ = ["main"]

DEFAULT_TERMS = ("filter", "status", "records", "billing")


def _client(settings) -> PowerContextClient:
    return PowerContextClient(settings.powercontext_url, settings.powercontext_token)


def _store(settings) -> SeekDBStore:
    return SeekDBStore(settings.seekdb_dir).open()


def _emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def cmd_import(args: argparse.Namespace, settings) -> int:
    with _store(settings) as store:
        result = import_materials(
            store,
            project_dir=Path(args.project),
            spec_path=Path(args.spec),
        )
    _emit(result)
    return 0


def cmd_context(args: argparse.Namespace, settings) -> int:
    with _store(settings) as store:
        context = build_context(
            store,
            task_id=args.task_id,
            task=args.task,
            terms=tuple(args.term or DEFAULT_TERMS),
            required_spec_ids=tuple(args.require_spec or ()),
        )
    _emit(context)
    return 0


def cmd_state(args: argparse.Namespace, settings) -> int:
    client = _client(settings)
    scope_id = args.scope_id or client.ensure_scope(
        settings.powercontext_scope_title, settings.scope_idempotency_key(args.task_id)
    )
    state = client.load_task_state(scope_id=scope_id, task_id=args.task_id)
    _emit(state.to_dict() if state else {"found": False})
    return 0


def cmd_pipeline(args: argparse.Namespace, settings) -> int:
    with _store(settings) as store:
        client = _client(settings)
        result = execute_task(
            settings,
            store=store,
            client=client,
            task_id=args.task_id,
            task=args.task,
            terms=tuple(args.term or DEFAULT_TERMS),
            required_spec_ids=tuple(args.require_spec or ()),
        )
    _emit(result.to_dict())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ctxmodule", description=__doc__)
    parser.add_argument("--seekdb-dir", default=None)
    parser.add_argument("--transcript-dir", default=None)
    parser.add_argument("--powercontext-url", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="import specs, code and tests")
    p_import.add_argument("--project", required=True)
    p_import.add_argument("--spec", required=True)
    p_import.set_defaults(func=cmd_import)

    p_context = sub.add_parser("context", help="assemble the task context")
    p_context.add_argument("--task-id", required=True)
    p_context.add_argument("--task", required=True)
    p_context.add_argument("--term", action="append")
    p_context.add_argument("--require-spec", action="append")
    p_context.set_defaults(func=cmd_context)

    p_state = sub.add_parser("state", help="read the persisted task state")
    p_state.add_argument("--task-id", required=True)
    p_state.add_argument("--scope-id", default=None)
    p_state.set_defaults(func=cmd_state)

    p_pipeline = sub.add_parser("pipeline", help="run the full flow")
    p_pipeline.add_argument("--task-id", required=True)
    p_pipeline.add_argument("--task", required=True)
    p_pipeline.add_argument("--term", action="append")
    p_pipeline.add_argument("--require-spec", action="append")
    p_pipeline.set_defaults(func=cmd_pipeline)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    overrides: dict[str, object] = {}
    if args.seekdb_dir:
        overrides["seekdb_dir"] = Path(args.seekdb_dir).expanduser().resolve()
    if args.transcript_dir:
        overrides["transcript_dir"] = Path(args.transcript_dir).expanduser().resolve()
    if args.powercontext_url:
        overrides["powercontext_url"] = args.powercontext_url
    settings = load_settings(**overrides)
    return int(args.func(args, settings))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
