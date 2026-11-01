"""Gate 4 -- the database really takes part.

Acceptance item: "the engineering material or an index is stored in
seekdb / OceanBase and the actual query result is used to build the task
context".
"""

from __future__ import annotations

from conftest import MINIMAX_ROOT, SPEC_V2, TASK_ID, TERMS

from ctxmodule.pipeline import build_context, import_materials


def test_material_is_stored_in_seekdb(store) -> None:
    import_materials(
        store, project_dir=MINIMAX_ROOT / "sample_project", spec_path=SPEC_V2
    )
    assert store.count() >= 4, "the material was not stored in seekdb"

    kinds = {document.kind for document in store.all_documents()}
    assert {"spec", "code", "test"} <= kinds

    # The stored specification really contains the constraint entries.
    spec = store.get("spec:active")
    assert spec is not None
    assert "SPEC-BILL-001-F" in spec.content


def test_context_is_built_from_query_results(store) -> None:
    import_materials(
        store, project_dir=MINIMAX_ROOT / "sample_project", spec_path=SPEC_V2
    )
    context = build_context(
        store,
        task_id=TASK_ID,
        task="assemble the context",
        terms=TERMS,
        required_spec_ids=("SPEC-BILL-001-F",),
    )

    project = MINIMAX_ROOT / "sample_project"

    # Every code / test source of the context must be backed by a seekdb row
    # whose content equals the file on disk. That can only hold when the
    # context was assembled from the database.
    for entry in context["code"] + context["tests"]:
        document = store.get(entry["doc_id"])
        assert document is not None, entry["doc_id"]
        assert document.path == entry["path"]
        on_disk = (project / entry["path"]).read_text(encoding="utf-8")
        assert document.content == on_disk, (
            f"the context source {entry['path']} does not match the stored row"
        )

    # A raw query must find the material that the context selected.
    found = store.search(["filter_records"], kinds=["code"])
    assert found, "a seekdb query found no code material"
    assert any(document.path == "src/billing/filter.py" for document in found)

    # The selection must be query driven: an unrelated term finds nothing.
    assert store.search(["zzz-no-such-token-zzz"]) == []
