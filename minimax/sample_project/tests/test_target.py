"""Target feature tests for the billing filtering feature.

These tests pin down the behaviour required by the *active* version of
the specification (``specs/billing_filter_v2.md``).

Against the pre-change snapshot they fail because the ``status``
filtering is not implemented yet -- the failure is raised by the
production code (``TypeError: filter_records() got an unexpected
keyword argument 'status'``), never by a missing dependency, a broken
import or an unreachable service.
"""

from __future__ import annotations

from billing import SAMPLE, filter_records

# SPEC-BILL-001-F
def test_filter_by_status_keeps_only_matching_records() -> None:
    result = filter_records(SAMPLE, status="paid")
    assert [record.id for record in result] == ["r1", "r3"]


# SPEC-BILL-001-F
def test_filter_by_status_absent_does_not_filter_status() -> None:
    result = filter_records(SAMPLE)
    assert [record.id for record in result] == [record.id for record in SAMPLE]


# SPEC-BILL-001-G
def test_status_and_amount_intersect() -> None:
    result = filter_records(SAMPLE, status="paid", min_amount=100)
    assert [record.id for record in result] == ["r3"]


# SPEC-BILL-001-G
def test_status_and_currency_intersect() -> None:
    result = filter_records(SAMPLE, status="paid", currency="CNY")
    assert [record.id for record in result] == ["r1", "r3"]


# SPEC-BILL-001-H
def test_status_is_keyword_only() -> None:
    # Passing status positionally must not be accepted.
    try:
        filter_records(SAMPLE, "paid")  # type: ignore[misc]
    except TypeError:
        return
    raise AssertionError("status must be keyword-only")


# SPEC-BILL-001-C
def test_status_filter_preserves_order() -> None:
    result = filter_records(SAMPLE, status="refunded")
    assert [record.id for record in result] == ["r4"]
