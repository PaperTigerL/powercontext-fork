"""Record filtering for the billing domain.

Implements the constraints recorded in the active specification
(``specs/billing_filter_v*.md``).

History
-------
* v1 (SPEC-BILL-001-A .. E): amount / currency filtering only.
* v2 (SPEC-BILL-001-F .. H): adds ``status`` filtering and makes the
  multi-condition semantics an explicit intersection.

This snapshot is the **post-change** state produced during the recorded
MiniMax session: ``status`` filtering is implemented and multiple
conditions intersect.
"""

from __future__ import annotations

from typing import Iterable

from .records import BillingRecord

__all__ = ["filter_records"]


def filter_records(
    records: Iterable[BillingRecord],
    *,
    min_amount: float | None = None,
    currency: str | None = None,
    status: str | None = None,
) -> list[BillingRecord]:
    """Filter billing records.

    Implements SPEC-BILL-001-A .. -H.

    Parameters
    ----------
    records:
        The records to filter. The original order is preserved.
    min_amount:
        Keep records whose ``amount`` is greater than or equal to this
        value. ``None`` disables the check.
    currency:
        Keep records whose ``currency`` equals this value exactly.
        ``None`` disables the check.
    status:
        Keep records whose ``status`` equals this value exactly.
        ``None`` disables the check.
    """

    result = list(records)

    if min_amount is not None:
        result = [record for record in result if record.amount >= min_amount]

    if currency is not None:
        result = [record for record in result if record.currency == currency]

    if status is not None:
        result = [record for record in result if record.status == status]

    return result
