"""MiniMax SDD context module.

A spec-driven development context module: it imports the specifications,
code and tests of a task into seekdb, selects the material with real SQL
queries, hands the resulting context to MiniMax and keeps the task state
in PowerContext so that it survives a restart.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
