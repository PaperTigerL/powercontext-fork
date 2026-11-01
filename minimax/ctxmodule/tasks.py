"""The canonical verification task of the sample project.

Both the recording script and the acceptance gates use these constants so
that the context assembled by the gates is byte-identical to the context
that was given to MiniMax during the recorded session.
"""

from __future__ import annotations

__all__ = ["TASK_ID", "TASK", "TERMS", "REQUIRED_SPEC_IDS", "SPEC_V1_ITEMS", "SPEC_V2_ITEMS"]

TASK_ID = "TASK-BILL-001"

TASK = (
    "Implement the status filter required by SPEC-BILL-001-F in "
    "src/billing/filter.py. status must be keyword-only, multiple "
    "conditions intersect, and the original order must be preserved."
)

# Terms used to select the material with the seekdb queries.
TERMS = ("filter", "status", "records", "billing")

# Specification items that must be part of the assembled context.
REQUIRED_SPEC_IDS = ("SPEC-BILL-001-F", "SPEC-BILL-001-G", "SPEC-BILL-001-H")

# Items that exist in specification v1 but not in v2.
SPEC_V1_ITEMS = ("SPEC-BILL-001-A",)
SPEC_V2_ITEMS = ("SPEC-BILL-001-A", "SPEC-BILL-001-F", "SPEC-BILL-001-G", "SPEC-BILL-001-H")
