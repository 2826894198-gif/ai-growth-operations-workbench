"""Post-execution observation and outcome labels (PART 06 §109-§110)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import ExecutionOutcome

OBSERVATION_WINDOW_HOURS = {
    "BUDGET": 24,
    "STATUS": 12,
}


def label_outcome(before_metrics: Optional[Dict[str, Any]], after_metrics: Optional[Dict[str, Any]], expected_signal: Optional[Dict[str, Any]]) -> str:
    if not before_metrics or not after_metrics:
        return "INSUFFICIENT_DATA"
    signal = (expected_signal or {}).get("metric")
    direction = (expected_signal or {}).get("direction")
    if not signal or not direction:
        return "NO_CLEAR_SIGNAL"
    before = before_metrics.get(signal)
    after = after_metrics.get(signal)
    if before is None or after is None:
        return "INSUFFICIENT_DATA"
    try:
        delta = float(after) - float(before)
    except (TypeError, ValueError):
        return "INSUFFICIENT_DATA"
    improved = delta > 0 if direction == "UP" else delta < 0
    degraded = delta < 0 if direction == "UP" else delta > 0
    if abs(delta) < 1e-9:
        return "NO_CLEAR_SIGNAL"
    if improved:
        return "IMPROVED"
    if degraded:
        return "DEGRADED"
    return "MIXED"


async def create_outcome(
    db: AsyncSession,
    *,
    job_id: str,
    intent_id: Optional[str],
    before_metrics: Optional[Dict[str, Any]],
    after_metrics: Optional[Dict[str, Any]],
    expected_signal: Optional[Dict[str, Any]],
    observed_signal: Optional[Dict[str, Any]] = None,
    observation_end: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> ExecutionOutcome:
    action = (observed_signal or {}).get("action") or ""
    window_hours = OBSERVATION_WINDOW_HOURS.get("BUDGET" if "BUDGET" in action else "STATUS", 24)
    outcome = ExecutionOutcome(
        execution_job_id=job_id,
        intent_id=intent_id,
        observation_start=datetime.now(timezone.utc),
        observation_end=observation_end or datetime.now(timezone.utc) + timedelta(hours=window_hours),
        before_metrics=before_metrics,
        after_metrics=after_metrics,
        expected_signal=expected_signal,
        observed_signal=observed_signal,
        outcome_label=label_outcome(before_metrics, after_metrics, expected_signal),
        notes=notes,
    )
    db.add(outcome)
    await db.flush()
    return outcome
