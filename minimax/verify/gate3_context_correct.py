"""Gate 3 -- the assembled context is correct.

Acceptance item: "the output contains the specification, code and test
sources required by the sample; after the specification is updated and
re-imported, the output uses the updated content".
"""

from __future__ import annotations

from conftest import MINIMAX_ROOT, SPEC_V1, SPEC_V2, TASK_ID, TERMS

from ctxmodule.pipeline import build_context, import_materials


def _items(context: dict) -> dict[str, str]:
    return {item["id"]: item["text"] for item in context["spec"]["items"]}


def test_context_follows_the_active_specification(store) -> None:
    # --- version 1 -------------------------------------------------
    import_materials(
        store, project_dir=MINIMAX_ROOT / "sample_project", spec_path=SPEC_V1
    )
    first = build_context(
        store,
        task_id=TASK_ID,
        task="assemble the context",
        terms=TERMS,
        required_spec_ids=("SPEC-BILL-001-A", "SPEC-BILL-001-F"),
    )
    first_items = _items(first)
    assert "SPEC-BILL-001-A" in first_items
    assert "SPEC-BILL-001-F" not in first_items, (
        "the module returned an item that the active specification does not contain"
    )

    # --- version 2, re-imported over the same source ---------------
    import_materials(
        store, project_dir=MINIMAX_ROOT / "sample_project", spec_path=SPEC_V2
    )
    second = build_context(
        store,
        task_id=TASK_ID,
        task="assemble the context",
        terms=TERMS,
        required_spec_ids=("SPEC-BILL-001-A", "SPEC-BILL-001-F"),
    )
    second_items = _items(second)

    assert "SPEC-BILL-001-F" in second_items, (
        "after re-importing the updated specification the module still answers "
        "with the old content"
    )
    assert "SPEC-BILL-001-F" not in first_items
    assert second_items["SPEC-BILL-001-F"] != first_items.get("SPEC-BILL-001-F")
    assert second["spec"]["source_hash"] != first["spec"]["source_hash"]


def test_context_names_real_code_and_test_sources(store) -> None:
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
    assert context["code"], "no code source was selected"
    assert context["tests"], "no test source was selected"

    project = MINIMAX_ROOT / "sample_project"
    for entry in context["code"] + context["tests"]:
        assert (project / entry["path"]).exists(), entry["path"]

    assert any(
        entry["path"] == "src/billing/filter.py" for entry in context["code"]
    ), "the module under change was not selected"
    assert any(
        entry["path"] == "tests/test_target.py" for entry in context["tests"]
    ), "the target feature test was not selected"
