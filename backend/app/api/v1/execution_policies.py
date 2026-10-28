"""Execution policies API (PART 06 §139, admin only)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.execution_permissions import require_permission
from app.core.database import get_db
from app.execution.policies import seed_default_policies
from app.models.execution import ExecutionPolicy

router = APIRouter()


class PolicyCreate(BaseModel):
    name: str
    provider: str
    action_type: str
    mode: str = "manual"
    max_risk_level: str = "HIGH"
    min_confidence: float = 0.60
    max_change_pct: Optional[float] = None
    max_actions_per_hour: int = 10
    max_actions_per_day: int = 30
    max_total_budget_change_pct_per_day: float = 30.0
    allowed_scope: Optional[dict] = None
    require_fresh_data_minutes: int = 60
    cooldown_minutes: int = 1440
    max_affected_campaigns: int = 1
    auto_execution_eligible: bool = False
    standing_approval: bool = False
    canary_scope: Optional[dict] = None
    enabled: bool = True


def _policy_dict(policy: ExecutionPolicy) -> dict:
    return {
        "id": str(policy.id),
        "name": policy.name,
        "provider": policy.provider,
        "action_type": policy.action_type,
        "mode": policy.mode,
        "max_risk_level": policy.max_risk_level,
        "min_confidence": policy.min_confidence,
        "max_change_pct": policy.max_change_pct,
        "max_actions_per_hour": policy.max_actions_per_hour,
        "max_actions_per_day": policy.max_actions_per_day,
        "max_total_budget_change_pct_per_day": policy.max_total_budget_change_pct_per_day,
        "allowed_scope": policy.allowed_scope,
        "require_fresh_data_minutes": policy.require_fresh_data_minutes,
        "cooldown_minutes": policy.cooldown_minutes,
        "max_affected_campaigns": policy.max_affected_campaigns,
        "auto_execution_eligible": policy.auto_execution_eligible,
        "standing_approval": policy.standing_approval,
        "canary_scope": policy.canary_scope,
        "enabled": policy.enabled,
        "version": policy.version,
        "created_by": policy.created_by,
    }


@router.get("/policies")
async def list_policies(provider: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(ExecutionPolicy).order_by(ExecutionPolicy.created_at.desc())
    if provider:
        query = query.where(ExecutionPolicy.provider == provider.upper())
    rows = (await db.execute(query)).scalars().all()
    return [_policy_dict(r) for r in rows]


@router.get("/policies/{policy_id}")
async def get_policy(policy_id: str, db: AsyncSession = Depends(get_db)):
    policy = (await db.execute(select(ExecutionPolicy).where(ExecutionPolicy.id == policy_id))).scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="policy not found")
    return _policy_dict(policy)


@router.post("/policies", dependencies=[Depends(require_permission("EXECUTION_POLICY_ADMIN"))])
async def create_policy(data: PolicyCreate, db: AsyncSession = Depends(get_db)):
    policy = ExecutionPolicy(
        workspace_id=None,
        name=data.name,
        provider=data.provider.upper(),
        action_type=data.action_type.upper(),
        mode=data.mode,
        max_risk_level=data.max_risk_level,
        min_confidence=data.min_confidence,
        max_change_pct=data.max_change_pct,
        max_actions_per_hour=data.max_actions_per_hour,
        max_actions_per_day=data.max_actions_per_day,
        max_total_budget_change_pct_per_day=data.max_total_budget_change_pct_per_day,
        allowed_scope=data.allowed_scope or {"all": False},
        require_fresh_data_minutes=data.require_fresh_data_minutes,
        cooldown_minutes=data.cooldown_minutes,
        max_affected_campaigns=data.max_affected_campaigns,
        auto_execution_eligible=data.auto_execution_eligible,
        standing_approval=data.standing_approval,
        canary_scope=data.canary_scope,
        enabled=data.enabled,
        version=1,
        created_by="admin",
    )
    db.add(policy)
    await db.commit()
    return _policy_dict(policy)


@router.put("/policies/{policy_id}", dependencies=[Depends(require_permission("EXECUTION_POLICY_ADMIN"))])
async def update_policy(policy_id: str, data: PolicyCreate, db: AsyncSession = Depends(get_db)):
    policy = (await db.execute(select(ExecutionPolicy).where(ExecutionPolicy.id == policy_id))).scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="policy not found")
    old_version = policy.version
    policy.version = old_version + 1
    policy.name = data.name
    policy.mode = data.mode
    policy.max_risk_level = data.max_risk_level
    policy.min_confidence = data.min_confidence
    policy.max_change_pct = data.max_change_pct
    policy.max_actions_per_hour = data.max_actions_per_hour
    policy.max_actions_per_day = data.max_actions_per_day
    policy.max_total_budget_change_pct_per_day = data.max_total_budget_change_pct_per_day
    policy.allowed_scope = data.allowed_scope or {"all": False}
    policy.require_fresh_data_minutes = data.require_fresh_data_minutes
    policy.cooldown_minutes = data.cooldown_minutes
    policy.max_affected_campaigns = data.max_affected_campaigns
    policy.auto_execution_eligible = data.auto_execution_eligible
    policy.standing_approval = data.standing_approval
    policy.canary_scope = data.canary_scope
    policy.enabled = data.enabled
    await db.commit()
    return _policy_dict(policy)


@router.post("/policies/seed", dependencies=[Depends(require_permission("EXECUTION_POLICY_ADMIN"))])
async def seed_policies(db: AsyncSession = Depends(get_db)):
    created = await seed_default_policies(db)
    await db.commit()
    return {"created": created}
