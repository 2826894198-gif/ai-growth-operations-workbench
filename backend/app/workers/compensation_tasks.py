"""Compensation worker (queue: compensation) — thin alias for clarity."""

from app.workers.execution_tasks import execution_run_compensation

__all__ = ["execution_run_compensation"]
