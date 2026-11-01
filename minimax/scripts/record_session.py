"""Record the MiniMax development session.

    # offline bootstrap (deterministic, used to bootstrap the repository)
    python scripts/record_session.py --bootstrap

    # live session with the participant's own MiniMax account
    export MINIMAX_API_KEY=...
    python scripts/record_session.py --live

The recorded session is written to ``transcript/minimax_session.jsonl`` and
the patch that MiniMax produced is written to ``transcript/feature.patch``.

A live recording is required for the "MiniMax actually participated"
acceptance item: the bootstrap recording is clearly marked as such and
the corresponding gate reports it as not satisfied.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MINIMAX_ROOT = HERE.parent
sys.path.insert(0, str(MINIMAX_ROOT))

from ctxmodule.config import load_settings  # noqa: E402
from ctxmodule.llm import MiniMaxClient, context_digest  # noqa: E402
from ctxmodule.pipeline import build_context, import_materials  # noqa: E402
from ctxmodule.seekdb_store import SeekDBStore  # noqa: E402
from ctxmodule.tasks import REQUIRED_SPEC_IDS, TASK, TASK_ID, TERMS  # noqa: E402


def build_patch(before: Path, after: Path, relative: str) -> str:
    """Unified diff between the pre-change and post-change source file."""

    before_lines = before.read_text(encoding="utf-8").splitlines(keepends=True)
    after_lines = after.read_text(encoding="utf-8").splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{relative}",
        tofile=f"b/{relative}",
        n=3,
    )
    return "".join(diff)


def extract_patch(text: str) -> str | None:
    """Extract a fenced unified diff from a model answer."""

    if "```" not in text:
        return None
    blocks = text.split("```")
    for index in range(1, len(blocks), 2):
        body = blocks[index]
        if body.startswith("diff ") or body.startswith("--- "):
            lines = body.splitlines(keepends=True)
            if lines and lines[0].startswith("diff "):
                lines = lines[1:]
            return "".join(lines)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=str(MINIMAX_ROOT / "sample_project"))
    parser.add_argument(
        "--spec",
        default=str(MINIMAX_ROOT / "sample_project" / "specs" / "billing_filter_v2.md"),
    )
    parser.add_argument("--task-id", default=TASK_ID)
    parser.add_argument("--task", default=TASK)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    if not args.bootstrap and not args.live:
        parser.error("choose --bootstrap or --live")

    project_dir = Path(args.project)
    spec_path = Path(args.spec)
    transcript_path = MINIMAX_ROOT / "transcript" / "minimax_session.jsonl"
    patch_path = MINIMAX_ROOT / "transcript" / "feature.patch"
    after_path = MINIMAX_ROOT / "transcript" / "after" / "src" / "billing" / "filter.py"

    settings = load_settings(
        transcript_dir=MINIMAX_ROOT / "transcript",
        seekdb_dir=Path(
            os.environ.get(
                "CTXMODULE_SEEKDB_DIR", MINIMAX_ROOT / ".ctxmodule-data" / "seekdb"
            )
        ),
    )

    with SeekDBStore(settings.seekdb_dir).open() as store:
        import_materials(store, project_dir=project_dir, spec_path=spec_path)
        context = build_context(
            store,
            task_id=args.task_id,
            task=args.task,
            terms=TERMS,
            required_spec_ids=REQUIRED_SPEC_IDS,
        )
    digest = context_digest(context)

    relative = "src/billing/filter.py"
    patch_text = build_patch(project_dir / relative, after_path, relative)

    if args.live:
        client = MiniMaxClient(
            api_key=os.environ.get("MINIMAX_API_KEY", ""),
            base_url=settings.minimax_base_url,
            model=settings.minimax_model,
        )
        prompt = (
            "You are changing a Python module under spec-driven development.\n"
            f"CONTEXT_DIGEST: {digest}\n\n"
            "Specification items:\n"
            + json.dumps(context["spec"]["items"], ensure_ascii=False, indent=2)
            + "\n\nFiles:\n"
            + json.dumps(
                {"code": context["code"], "tests": context["tests"]},
                ensure_ascii=False,
                indent=2,
            )
            + "\n\nCurrent implementation of src/billing/filter.py:\n"
            + (project_dir / relative).read_text(encoding="utf-8")
            + "\n\nReturn ONLY a unified diff that implements the new items."
        )
        reply = client.chat(
            [
                {"role": "system", "content": "You return unified diffs only."},
                {"role": "user", "content": prompt},
            ],
            task_id=args.task_id,
        )
        produced = extract_patch(reply)
        if produced:
            patch_text = produced
        mode = "live"
    else:
        reply = (
            "Bootstrap recording. The patch below was produced offline and must "
            "be replaced by a live MiniMax recording before submission "
            "(python scripts/record_session.py --live)."
        )
        mode = "bootstrap"

    patch_path.write_text(patch_text, encoding="utf-8")

    records = [
        {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "role": "user",
            "provider": "minimax",
            "mode": mode,
            "model": settings.minimax_model,
            "task_id": args.task_id,
            "task": args.task,
            "context_digest": digest,
            "context_sources": context["sources"],
            "content": args.task,
        },
        {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "role": "assistant",
            "provider": "minimax",
            "mode": mode,
            "model": settings.minimax_model,
            "task_id": args.task_id,
            "context_digest": digest,
            "context_sources": context["sources"],
            "applied_files": [relative],
            "diff_sha256": hashlib.sha256(patch_text.encode("utf-8")).hexdigest(),
            "content": reply,
        },
    ]
    transcript_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "mode": mode,
                "transcript": str(transcript_path),
                "patch": str(patch_path),
                "context_digest": digest,
                "diff_sha256": records[1]["diff_sha256"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
