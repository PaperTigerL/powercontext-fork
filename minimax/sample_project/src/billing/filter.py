"""Record filtering for the billing domain.

Implements the constraints recorded in the active specification
(``specs/billing_filter_v*.md``).

History
-------
* v1 (SPEC-BILL-001-A .. E): amount / currency filtering only.
* v2 (SPEC-BILL-001-F .. H): adds ``status`` filtering and makes the
  multi-condition semantics an explicit intersection.

The file checked into the repository is the **pre-change** state: it
implements v1 only. The ``status`` keyword required by v2 is therefore
not implemented yet, and the target feature tests fail against this
snapshot for exactly that reason.
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
) -> list[BillingRecord]:
    """Filter billing records.

    Implements SPEC-BILL-001-A, -B, -C, -D and -E.

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
    """

    result = list(records)

    if min_amount is not None:
        result = [record for record in result if record.amount >= min_amount]

    if currency is not None:
        result = [record for record in result if record.currency == currency]

    return result
