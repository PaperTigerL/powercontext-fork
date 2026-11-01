"""Regression tests for the billing filtering feature.

These cover the behaviour that existed before the change (v1
constraints SPEC-BILL-001-A .. -E). They must pass both before and
after the modification.
"""

from __future__ import annotations

from billing import SAMPLE, filter_records, load_records, total_amount

# SPEC-BILL-001-A
def test_filter_by_min_amount() -> None:
    result = filter_records(SAMPLE, min_amount=100)
    assert [record.id for record in result] == ["r2", "r3"]


# SPEC-BILL-001-B
def test_filter_by_currency() -> None:
    result = filter_records(SAMPLE, currency="USD")
    assert [record.id for record in result] == ["r2", "r4"]


# SPEC-BILL-001-C
def test_filter_preserves_input_order() -> None:
    result = filter_records(SAMPLE, min_amount=0)
    assert [record.id for record in result] == ["r1", "r2", "r3", "r4"]


# SPEC-BILL-001-D
def test_empty_input_returns_empty_list() -> None:
    assert filter_records([], min_amount=10) == []
    assert filter_records([]) == []


# SPEC-BILL-001-E
def test_absent_conditions_do_not_change_results() -> None:
    assert len(filter_records(SAMPLE)) == len(SAMPLE)


# Unrelated behaviour that must stay intact.
def test_total_amount_is_unchanged() -> None:
    assert total_amount(SAMPLE) == 390.0


def test_load_records_rejects_nothing_for_known_rows() -> None:
    records = load_records([("x", 1.0, "CNY", "paid")])
    assert records[0].id == "x"
    assert records[0].status == "paid"
