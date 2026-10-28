"""Kill switch checks + auto-kill triggers (PART 06 §51-§54, §160-§161)."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.execution.timeutil import ensure_utc
from app.models.execution import ExecutionJob, ExecutionKillSwitch

SCOPE_TYPES = ("GLOBAL", "WORKSPACE", "PROVIDER", "ACCOUNT", "ACTION", "ENTITY", "CONNECTED_ACCOUNT")


async def list_active_kill_switches(db: AsyncSession) -> List[ExecutionKillSwitch]:
    rows = (await db.execute(select(ExecutionKillSwitch).where(ExecutionKillSwitch.enabled.is_(True)))).scalars().all()
    return list(rows)


async def kill_switch_blocked(
    db: AsyncSession,
    *,
    provider: str,
    action_type: str,
    account_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> Dict[str, bool]:
    """Return which scopes are blocking. GLOBAL wins immediately."""
    blocked = {
        "GLOBAL": False,
        "WORKSPACE": False,
        "PROVIDER": False,
        "ACCOUNT": False,
        "ACTION": False,
        "ENTITY": False,
        "CONNECTED_ACCOUNT": False,
        "CONFIG": settings.execution_global_kill_switch,
    }
    switches = await list_active_kill_switches(db)
    for switch in switches:
        scope = switch.scope_type.upper()
        if scope == "GLOBAL":
            blocked["GLOBAL"] = True
            continue
        if scope == "WORKSPACE" and workspace_id and switch.scope_id == workspace_id:
            blocked["WORKSPACE"] = True
        if scope == "PROVIDER" and (switch.scope_id or "").upper() == provider.upper():
            blocked["PROVIDER"] = True
        elif scope == "ACCOUNT" and account_id and switch.scope_id == account_id:
            blocked["ACCOUNT"] = True
        elif scope == "ACTION" and (switch.scope_id or "").upper() == action_type.upper():
            blocked["ACTION"] = True
        elif scope == "ENTITY" and entity_id and switch.scope_id == entity_id:
            blocked["ENTITY"] = True
        elif scope == "CONNECTED_ACCOUNT" and entity_id and switch.scope_id == entity_id:
            blocked["CONNECTED_ACCOUNT"] = True
    blocked["ACTIVE"] = any(v for k, v in blocked.items() if k != "ACTIVE")
    return blocked


async def set_kill_switch(
    db: AsyncSession,
    *,
    scope_type: str,
    scope_id: Optional[str],
    enabled: bool,
    actor: str,
    reason: Optional[str] = None,
) -> ExecutionKillSwitch:
    scope_type = scope_type.upper()
    if scope_type not in SCOPE_TYPES:
        raise ValueError(f"invalid kill switch scope: {scope_type}")
    row = (
        await db.execute(
            select(ExecutionKillSwitch).where(
                ExecutionKillSwitch.scope_type == scope_type,
                ExecutionKillSwitch.scope_id == scope_id,
            )
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None:
        row = ExecutionKillSwitch(scope_type=scope_type, scope_id=scope_id)
        db.add(row)
    row.enabled = enabled
    row.reason = reason
    if enabled:
        row.activated_by = actor
        row.activated_at = now
        row.deactivated_by = None
        row.deactivated_at = None
    else:
        row.deactivated_by = actor
        row.deactivated_at = now
    await db.flush()
    return row


async def check_auto_kill_triggers(db: AsyncSession) -> Optional[str]:
    """Activate scoped kill switches on failure/unknown-outcome spikes."""
    window_minutes = settings.execution_auto_kill_window_minutes
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    jobs = (
        await db.execute(
            select(ExecutionJob).where(
                ExecutionJob.status.in_(("FAILED", "UNKNOWN", "COMPENSATION_FAILED")),
            )
        )
    ).scalars().all()
    jobs = [j for j in jobs if ensure_utc(j.finished_at) is not None and ensure_utc(j.finished_at) >= since]
    if not jobs:
        return None
    unknown = [j for j in jobs if j.error_code in ("PROVIDER_TIMEOUT", "PROVIDER_OUTCOME_UNKNOWN")]
    verification_failed = [j for j in jobs if j.verification_result == "MISMATCHED" or j.error_code == "VERIFICATION_FAILED"]
    if len(unknown) >= settings.execution_unknown_outcome_auto_kill_threshold:
        await set_kill_switch(
            db,
            scope_type="PROVIDER",
            scope_id=None,
            enabled=True,
            actor="system",
            reason=f"auto kill: {len(unknown)} unknown provider outcomes in {window_minutes}m",
        )
        return "PROVIDER"
    if len(verification_failed) >= settings.execution_verification_failure_auto_kill_threshold:
        await set_kill_switch(
            db,
            scope_type="PROVIDER",
            scope_id=None,
            enabled=True,
            actor="system",
            reason=f"auto kill: {len(verification_failed)} verification failures in {window_minutes}m",
        )
        return "PROVIDER"
    return None
