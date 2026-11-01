"""End-to-end flow of the SDD context module.

The flow mirrors the task required by the competition statement:

1. import the specifications, code and tests of a task,
2. select the material for the task with real seekdb queries,
3. hand the resulting context to MiniMax,
4. apply the produced change and verify it with the tests,
5. save the task state in PowerContext so that it can be reused after a
   restart.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .config import Settings
from .llm import LLMError, build_client, context_digest
from .pc import PowerContextClient, TaskState
from .seekdb_store import Document, SeekDBStore

__all__ = [
    "SpecItem",
    "parse_spec",
    "import_materials",
    "build_context",
    "run_tests",
    "apply_patch",
    "TaskResult",
    "execute_task",
]

_SPEC_ROW = re.compile(r"^\|\s*(SPEC-[A-Z0-9-]+)\s*\|(.+?)\s*\|")
_CODE_SUFFIXES = (".py", ".ts", ".js", ".go", ".java", ".rs", ".c", ".h", ".cc", ".cpp")


@dataclass(frozen=True)
class SpecItem:
    """One constraint entry of a specification."""

    item_id: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.item_id, "text": self.text}


def parse_spec(spec_path: Path | str) -> list[SpecItem]:
    """Extract the constraint entries of a specification markdown file."""

    text = Path(spec_path).read_text(encoding="utf-8")
    items: list[SpecItem] = []
    for line in text.splitlines():
        match = _SPEC_ROW.match(line.strip())
        if match:
            body = match.group(2).split("|", 1)[0].strip()
            items.append(SpecItem(item_id=match.group(1), text=body))
    return items


def _collect_files(project_dir: Path) -> tuple[list[Path], list[Path]]:
    """Return (code files, test files) of the sample project."""

    code_files: list[Path] = []
    test_files: list[Path] = []
    for path in sorted(project_dir.rglob("*")):
        if not path.is_file() or path.suffix not in _CODE_SUFFIXES:
            continue
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(project_dir).as_posix()
        if relative.startswith("tests/") or path.name.startswith("test_"):
            test_files.append(path)
        else:
            code_files.append(path)
    return code_files, test_files


def import_materials(
    store: SeekDBStore,
    *,
    project_dir: Path,
    spec_path: Path,
) -> dict[str, Any]:
    """Import specification, code and tests into seekdb.

    The active specification is stored under the stable document id
    ``spec:active`` so that re-importing an updated specification
    replaces its content instead of adding an unrelated document.
    """

    project_dir = Path(project_dir)
    spec_path = Path(spec_path)
    items = parse_spec(spec_path)
    spec_text = spec_path.read_text(encoding="utf-8")
    spec_doc_id = "spec:active"
    spec_hash = store.upsert(
        doc_id=spec_doc_id,
        kind="spec",
        path=spec_path.name,
        title=spec_path.stem,
        content=spec_text,
        spec_ids=tuple(item.item_id for item in items),
    )

    code_files, test_files = _collect_files(project_dir)
    code_ids: list[str] = []
    test_ids: list[str] = []
    for path in code_files:
        relative = path.relative_to(project_dir).as_posix()
        doc_id = f"code:{relative}"
        store.upsert(
            doc_id=doc_id,
            kind="code",
            path=relative,
            title=path.name,
            content=path.read_text(encoding="utf-8", errors="replace"),
            spec_ids=tuple(item.item_id for item in items),
        )
        code_ids.append(doc_id)
    for path in test_files:
        relative = path.relative_to(project_dir).as_posix()
        doc_id = f"test:{relative}"
        store.upsert(
            doc_id=doc_id,
            kind="test",
            path=relative,
            title=path.name,
            content=path.read_text(encoding="utf-8", errors="replace"),
            spec_ids=tuple(item.item_id for item in items),
        )
        test_ids.append(doc_id)

    return {
        "spec_doc_id": spec_doc_id,
        "spec_hash": spec_hash,
        "spec_items": [item.to_dict() for item in items],
        "code_ids": code_ids,
        "test_ids": test_ids,
        "document_count": store.count(),
    }


def build_context(
    store: SeekDBStore,
    *,
    task_id: str,
    task: str,
    terms: Sequence[str],
    required_spec_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Select the material for a task using real seekdb queries.

    The specification is read back from the database, not from the file
    system, so a re-imported specification is always reflected.
    """

    spec_doc = store.get("spec:active")
    if spec_doc is None:
        raise RuntimeError("no specification has been imported")

    selected = store.search(terms, limit=50)
    code_docs = [doc for doc in selected if doc.kind == "code"]
    test_docs = [doc for doc in selected if doc.kind == "test"]

    if not code_docs:
        code_docs = [doc for doc in store.all_documents() if doc.kind == "code"]
    if not test_docs:
        test_docs = [doc for doc in store.all_documents() if doc.kind == "test"]

    spec_items = []
    for item_id in required_spec_ids:
        entry = _find_spec_item(spec_doc.content, item_id)
        if entry:
            spec_items.append(entry)

    sources = [f"spec:{spec_doc.path}"] + [f"code:{doc.path}" for doc in code_docs]
    sources += [f"test:{doc.path}" for doc in test_docs]

    return {
        "task_id": task_id,
        "task": task,
        "spec": {
            "doc_id": spec_doc.doc_id,
            "path": spec_doc.path,
            "title": spec_doc.title,
            "source_hash": spec_doc.source_hash,
            "items": spec_items,
        },
        "code": [
            {"doc_id": doc.doc_id, "path": doc.path, "title": doc.title}
            for doc in code_docs
        ],
        "tests": [
            {"doc_id": doc.doc_id, "path": doc.path, "title": doc.title}
            for doc in test_docs
        ],
        "sources": sources,
    }


def _find_spec_item(spec_text: str, item_id: str) -> dict[str, str] | None:
    for line in spec_text.splitlines():
        match = _SPEC_ROW.match(line.strip())
        if match and match.group(1) == item_id:
            return {"id": match.group(1), "text": match.group(2).split("|", 1)[0].strip()}
    return None


def apply_patch(project_dir: Path, patch_text: str) -> tuple[bool, str]:
    """Apply a unified diff to the sample project."""

    project_dir = Path(project_dir)
    patch_path = project_dir / ".ctxmodule-apply.patch"
    patch_path.write_text(patch_text, encoding="utf-8")
    try:
        completed = subprocess.run(
            ["git", "apply", "-p1", "--whitespace=nowarn", str(patch_path.name)],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
    finally:
        patch_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        return False, (completed.stderr or completed.stdout).strip()
    return True, "applied"


def run_tests(project_dir: Path, *targets: str) -> dict[str, Any]:
    """Run pytest inside the sample project and capture the outcome."""

    project_dir = Path(project_dir)
    env = {
        "PYTHONPATH": str(project_dir / "src"),
        "PATH": _current_path(),
    }
    command = [sys.executable, "-m", "pytest", "-q", *targets]
    completed = subprocess.run(
        command,
        cwd=project_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    return {
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-4000:],
        "passed": completed.returncode == 0,
    }


def _current_path() -> str:
    import os

    return os.environ.get("PATH", "")


@dataclass
class TaskResult:
    """Outcome of one end-to-end task execution."""

    task_id: str
    context: dict[str, Any]
    digest: str
    assistant_reply: str
    tests: dict[str, Any]
    state: TaskState | None
    usage_record: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "context": self.context,
            "context_digest": self.digest,
            "assistant_reply": self.assistant_reply,
            "tests": self.tests,
            "state": self.state.to_dict() if self.state else None,
            "usage": self.usage_record,
        }


def execute_task(
    settings: Settings,
    *,
    store: SeekDBStore,
    client: PowerContextClient,
    task_id: str,
    task: str,
    terms: Sequence[str],
    required_spec_ids: Sequence[str] = (),
    scope_id: str | None = None,
) -> TaskResult:
    """Run the full flow for one task."""

    context = build_context(
        store,
        task_id=task_id,
        task=task,
        terms=terms,
        required_spec_ids=required_spec_ids,
    )
    digest = context_digest(context)

    llm = build_client(settings)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a development assistant working on a spec-driven "
                "change.\n"
                "CONTEXT_DIGEST: " + digest + "\n"
                "Follow the specification items listed in the context and "
                "produce a minimal patch."
            ),
        },
        {"role": "user", "content": task},
    ]
    reply = llm.chat(messages, task_id=task_id)

    usage_record = {
        "task_id": task_id,
        "provider": "minimax",
        "mode": settings.llm_provider,
        "model": settings.minimax_model,
        "context_digest": digest,
        "context_sources": context["sources"],
        "task": task,
        "reply_excerpt": reply[:400],
    }

    resolved_scope = scope_id or client.ensure_scope(
        settings.powercontext_scope_title, settings.scope_idempotency_key(task_id)
    )
    state = TaskState(
        task_id=task_id,
        scope_id=resolved_scope,
        status="context-assembled",
        spec_ids=tuple(
            item["id"] for item in context["spec"]["items"]
        ),
        changed_files=(),
        tests={},
        notes=task,
    )
    client.save_task_state(state)

    return TaskResult(
        task_id=task_id,
        context=context,
        digest=digest,
        assistant_reply=reply,
        tests={},
        state=state,
        usage_record=usage_record,
    )


def copy_project(source: Path, target: Path) -> Path:
    """Copy the sample project into a scratch directory."""

    source = Path(source)
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target
