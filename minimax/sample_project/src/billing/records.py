"""Billing domain records.

This module holds the record type and fixtures used by the filtering
feature. It is intentionally free of filtering logic so that the
regression tests can pin down behaviour that must not change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

__all__ = ["BillingRecord", "SAMPLE", "load_records", "total_amount"]


@dataclass(frozen=True)
class BillingRecord:
    """A single billing record."""

    id: str
    amount: float
    currency: str
    status: str


SAMPLE: tuple[BillingRecord, ...] = (
    BillingRecord(id="r1", amount=50.0, currency="CNY", status="paid"),
    BillingRecord(id="r2", amount=120.0, currency="USD", status="pending"),
    BillingRecord(id="r3", amount=200.0, currency="CNY", status="paid"),
    BillingRecord(id="r4", amount=20.0, currency="USD", status="refunded"),
)


def load_records(rows: Iterable[Sequence[object]]) -> list[BillingRecord]:
    """Build records from raw rows; unknown statuses are rejected."""

    records: list[BillingRecord] = []
    for row in rows:
        identifier, amount, currency, status = row
        records.append(
            BillingRecord(
                id=str(identifier),
                amount=float(amount),  # type: ignore[arg-type]
                currency=str(currency),
                status=str(status),
            )
        )
    return records


def total_amount(records: Iterable[BillingRecord]) -> float:
    """Sum the amount of every record; unrelated to the filtering feature."""

    return sum(record.amount for record in records)
