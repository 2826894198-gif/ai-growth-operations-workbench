from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.rules.engine import run_evaluation


async def replay_rule(
    db: AsyncSession,
    rule_key: str,
    start_date: str,
    end_date: str,
    scope: str = "ALL",
) -> dict:
    """Replay a rule day-by-day using only data available at each as-of time.

    Part 02 intraday snapshots are not used yet, so the result is marked
    APPROXIMATE (no look-ahead is introduced for daily facts).
    """
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    days = []
    total_triggers = 0
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        as_of = datetime.combine(day, time(23, 59), tzinfo=timezone.utc)
        run = await run_evaluation(db, trigger_type="REPLAY", rule_keys=[rule_key], as_of=as_of, shadow=True)
        if run is None:
            continue
        days.append({"date": day.isoformat(), "triggered": run.triggered, "run_id": str(run.id)})
        total_triggers += run.triggered
    return {
        "rule_key": rule_key,
        "start_date": start_date,
        "end_date": end_date,
        "approximate": True,
        "total_triggers": total_triggers,
        "days": days,
    }
