"""PART 06 — Automation Execution, Approval, Revalidation & Rollback System.

This package is the ONLY system layer allowed to mutate advertising platforms.
No agent, rule or dashboard code may call provider mutation APIs directly.
"""

from app.execution.errors import ExecutionError, ExecutionErrorCode

__all__ = ["ExecutionError", "ExecutionErrorCode"]
