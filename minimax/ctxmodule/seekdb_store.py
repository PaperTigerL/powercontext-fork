"""seekdb-backed storage for engineering material.

The module stores imported specifications, source files and test files in
an embedded seekdb instance and selects the material for a task with real
SQL queries. The query results are what feeds the development context, so
seekdb genuinely participates in the task flow instead of being a
side-effect installation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

__all__ = ["Document", "SeekDBStore", "SeekDBUnavailable"]


class SeekDBUnavailable(RuntimeError):
    """Raised when the embedded seekdb runtime cannot be used."""


@dataclass(frozen=True)
class Document:
    """One stored piece of engineering material."""

    doc_id: str
    kind: str  # spec | code | test
    path: str
    title: str
    content: str
    spec_ids: tuple[str, ...] = ()
    source_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "kind": self.kind,
            "path": self.path,
            "title": self.title,
            "content": self.content,
            "spec_ids": list(self.spec_ids),
            "source_hash": self.source_hash,
        }


def _quote(value: str) -> str:
    """Escape a value for inline SQL literal use."""

    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SeekDBStore:
    """Thin wrapper around an embedded seekdb database."""

    TABLE = "ctx_documents"

    def __init__(self, db_dir: Path | str) -> None:
        self.db_dir = Path(db_dir)
        self._instance = None
        self._conn = None
        self._cursor = None

    # -- lifecycle -----------------------------------------------------
    def open(self) -> "SeekDBStore":
        try:
            import pylibseekdb
        except ImportError as exc:  # pragma: no cover - environment issue
            raise SeekDBUnavailable(
                "pylibseekdb is not installed; install powercontext[seekdb] "
                "on Linux x86_64 with Python 3.12"
            ) from exc

        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._instance = pylibseekdb.open(str(self.db_dir))
        self._conn = self._instance.connect()
        self._cursor = self._conn.cursor()
        self._cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {self.TABLE} ("
            "doc_id VARCHAR(255) PRIMARY KEY, "
            "kind VARCHAR(32), "
            "path VARCHAR(1024), "
            "title VARCHAR(1024), "
            "content TEXT, "
            "spec_ids VARCHAR(1024), "
            "source_hash VARCHAR(64), "
            "updated_at VARCHAR(64))"
        )
        self._conn.commit()
        return self

    def close(self) -> None:
        for handle in (self._cursor, self._conn):
            try:
                if handle is not None:
                    handle.close()
            except Exception:  # pragma: no cover - best effort
                pass
        try:
            if self._instance is not None:
                self._instance.close()
        except Exception:  # pragma: no cover - best effort
            pass
        self._cursor = self._conn = self._instance = None

    def __enter__(self) -> "SeekDBStore":
        return self.open()

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- writes --------------------------------------------------------
    def upsert(
        self,
        *,
        doc_id: str,
        kind: str,
        path: str,
        title: str,
        content: str,
        spec_ids: Sequence[str] = (),
    ) -> str:
        """Insert or replace one document; returns its content hash."""

        digest = _sha256(content)
        self._cursor.execute(
            f"DELETE FROM {self.TABLE} WHERE doc_id = {_quote(doc_id)}"
        )
        self._cursor.execute(
            f"INSERT INTO {self.TABLE} "
            "(doc_id, kind, path, title, content, spec_ids, source_hash, updated_at) "
            f"VALUES ({_quote(doc_id)}, {_quote(kind)}, {_quote(path)}, "
            f"{_quote(title)}, {_quote(content)}, {_quote(json.dumps(list(spec_ids)))}, "
            f"{_quote(digest)}, {_quote(digest)})"
        )
        self._conn.commit()
        return digest

    # -- reads ---------------------------------------------------------
    def get(self, doc_id: str) -> Document | None:
        self._cursor.execute(
            f"SELECT doc_id, kind, path, title, content, spec_ids, source_hash "
            f"FROM {self.TABLE} WHERE doc_id = {_quote(doc_id)}"
        )
        rows = self._cursor.fetchall()
        if not rows:
            return None
        return self._row_to_document(rows[0])

    def all_documents(self) -> list[Document]:
        self._cursor.execute(
            f"SELECT doc_id, kind, path, title, content, spec_ids, source_hash "
            f"FROM {self.TABLE}"
        )
        return [self._row_to_document(row) for row in self._cursor.fetchall()]

    def count(self) -> int:
        self._cursor.execute(f"SELECT COUNT(*) FROM {self.TABLE}")
        rows = self._cursor.fetchall()
        return int(rows[0][0]) if rows else 0

    def search(
        self,
        terms: Iterable[str],
        *,
        kinds: Sequence[str] | None = None,
        limit: int = 50,
    ) -> list[Document]:
        """Select material with a real SQL query.

        Every term must appear in the stored content (``LIKE``), and the
        result is ordered by document id so that selection is stable.
        """

        clauses: list[str] = []
        for term in terms:
            cleaned = term.strip()
            if not cleaned:
                continue
            clauses.append(f"content LIKE {_quote('%' + cleaned + '%')}")
        if kinds:
            kind_list = ", ".join(_quote(kind) for kind in kinds)
            clauses.append(f"kind IN ({kind_list})")
        where = " AND ".join(clauses) if clauses else "1 = 1"
        self._cursor.execute(
            f"SELECT doc_id, kind, path, title, content, spec_ids, source_hash "
            f"FROM {self.TABLE} WHERE {where} ORDER BY doc_id LIMIT {int(limit)}"
        )
        return [self._row_to_document(row) for row in self._cursor.fetchall()]

    @staticmethod
    def _row_to_document(row: Sequence[object]) -> Document:
        doc_id, kind, path, title, content, spec_ids, source_hash = row
        try:
            ids = tuple(json.loads(spec_ids)) if spec_ids else ()
        except (TypeError, ValueError):
            ids = ()
        return Document(
            doc_id=str(doc_id),
            kind=str(kind),
            path=str(path),
            title=str(title),
            content=str(content),
            spec_ids=ids,
            source_hash=str(source_hash),
        )
