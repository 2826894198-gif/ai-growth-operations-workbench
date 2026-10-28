"""Kill switch API (PART 06 §138)."""


from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.execution_permissions import require_permission
from app.core.database import get_db
from app.execution.kill_switch import list_active_kill_switches, set_kill_switch
from app.models.execution import ExecutionKillSwitch

router = APIRouter()


class KillSwitchAction(BaseModel):
    actor: str = "admin"
    reason: str = "operator action"


def _switch_dict(switch) -> dict:
    return {
        "id": str(switch.id),
        "scope_type": switch.scope_type,
        "scope_id": switch.scope_id,
        "enabled": switch.enabled,
        "reason": switch.reason,
        "activated_by": switch.activated_by,
        "activated_at": switch.activated_at.isoformat() if switch.activated_at else None,
        "deactivated_by": switch.deactivated_by,
        "deactivated_at": switch.deactivated_at.isoformat() if switch.deactivated_at else None,
    }


@router.get("/kill-switches")
async def list_kill_switches(db: AsyncSession = Depends(get_db)):
    switches = await list_active_kill_switches(db)
    all_switches = (
        await db.execute(select(ExecutionKillSwitch).order_by(ExecutionKillSwitch.created_at.desc()))
    ).scalars().all()
    return {"active": [_switch_dict(s) for s in switches], "all": [_switch_dict(s) for s in all_switches]}


@router.post("/kill-switches/global/enable", dependencies=[Depends(require_permission("EXECUTION_KILL_SWITCH"))])
async def enable_global(data: KillSwitchAction = None, db: AsyncSession = Depends(get_db)):
    switch = await set_kill_switch(
        db,
        scope_type="GLOBAL",
        scope_id=None,
        enabled=True,
        actor=data.actor if data else "admin",
        reason=data.reason if data else "emergency stop",
    )
    await db.commit()
    return _switch_dict(switch)


@router.post("/kill-switches/global/disable", dependencies=[Depends(require_permission("EXECUTION_KILL_SWITCH"))])
async def disable_global(data: KillSwitchAction = None, db: AsyncSession = Depends(get_db)):
    switch = await set_kill_switch(
        db,
        scope_type="GLOBAL",
        scope_id=None,
        enabled=False,
        actor=data.actor if data else "admin",
        reason=data.reason if data else "resume operations",
    )
    await db.commit()
    return _switch_dict(switch)


@router.post("/kill-switches/provider/{provider}/enable", dependencies=[Depends(require_permission("EXECUTION_KILL_SWITCH"))])
async def enable_provider(provider: str, data: KillSwitchAction = None, db: AsyncSession = Depends(get_db)):
    switch = await set_kill_switch(
        db,
        scope_type="PROVIDER",
        scope_id=provider.upper(),
        enabled=True,
        actor=data.actor if data else "admin",
        reason=data.reason if data else f"provider {provider} stopped",
    )
    await db.commit()
    return _switch_dict(switch)


@router.post("/kill-switches/provider/{provider}/disable", dependencies=[Depends(require_permission("EXECUTION_KILL_SWITCH"))])
async def disable_provider(provider: str, data: KillSwitchAction = None, db: AsyncSession = Depends(get_db)):
    switch = await set_kill_switch(
        db,
        scope_type="PROVIDER",
        scope_id=provider.upper(),
        enabled=False,
        actor=data.actor if data else "admin",
        reason=data.reason if data else f"provider {provider} resumed",
    )
    await db.commit()
    return _switch_dict(switch)


@router.post("/kill-switches/action/{action_type}/enable", dependencies=[Depends(require_permission("EXECUTION_KILL_SWITCH"))])
async def enable_action(action_type: str, data: KillSwitchAction = None, db: AsyncSession = Depends(get_db)):
    switch = await set_kill_switch(
        db,
        scope_type="ACTION",
        scope_id=action_type.upper(),
        enabled=True,
        actor=data.actor if data else "admin",
        reason=data.reason if data else f"action {action_type} stopped",
    )
    await db.commit()
    return _switch_dict(switch)


@router.post("/kill-switches/action/{action_type}/disable", dependencies=[Depends(require_permission("EXECUTION_KILL_SWITCH"))])
async def disable_action(action_type: str, data: KillSwitchAction = None, db: AsyncSession = Depends(get_db)):
    switch = await set_kill_switch(
        db,
        scope_type="ACTION",
        scope_id=action_type.upper(),
        enabled=False,
        actor=data.actor if data else "admin",
        reason=data.reason if data else f"action {action_type} resumed",
    )
    await db.commit()
    return _switch_dict(switch)
