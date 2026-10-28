from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import FeatureFlag, UserDashboardPreference
from app.models.review import AccountDetectionSetting
from app.models.rules import BusinessTargetProfile, RuleDefinition

router = APIRouter()


class TargetsUpdate(BaseModel):
    target_cpa: Optional[float] = None
    target_roas: Optional[float] = None
    break_even_roas: Optional[float] = None
    target_aov: Optional[float] = None
    gross_margin_rate: Optional[float] = None
    max_daily_spend: Optional[float] = None
    max_campaign_daily_spend: Optional[float] = None
    refund_rate_warning: Optional[float] = None
    refund_rate_critical: Optional[float] = None


class DetectionRulesUpdate(BaseModel):
    sync_delay_minutes: int = Field(20, ge=5, le=1440)
    sync_stale_minutes: int = Field(60, ge=10, le=10080)
    content_inactive_days: int = Field(7, ge=1, le=90)


def _target_scope(workspace_id: str):
    if workspace_id == "ws_main":
        return or_(
            BusinessTargetProfile.workspace_id == workspace_id,
            BusinessTargetProfile.workspace_id.is_(None),
        )
    return BusinessTargetProfile.workspace_id == workspace_id


@router.get("/business-targets")
async def get_business_targets(
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(select(BusinessTargetProfile).where(_target_scope(workspace_id)))
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "workspace_id": r.workspace_id or "ws_main",
            "name": r.name,
            "scope_type": r.scope_type,
            "scope_id": r.scope_id,
            "target_cpa": r.target_cpa,
            "target_roas": r.target_roas,
            "break_even_roas": r.break_even_roas,
            "target_aov": r.target_aov,
            "gross_margin_rate": r.gross_margin_rate,
            "max_daily_spend": r.max_daily_spend,
            "max_campaign_daily_spend": r.max_campaign_daily_spend,
            "refund_rate_warning": r.refund_rate_warning,
            "refund_rate_critical": r.refund_rate_critical,
        }
        for r in rows
    ]


@router.put("/business-targets")
async def update_business_targets(
    data: TargetsUpdate,
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            select(BusinessTargetProfile).where(_target_scope(workspace_id)).limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        row = BusinessTargetProfile(
            workspace_id=workspace_id,
            name="Workspace targets",
            scope_type="WORKSPACE",
            scope_id=workspace_id,
        )
        db.add(row)
    elif row.workspace_id is None:
        row.workspace_id = workspace_id
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, key, value)
    await db.commit()
    return {"status": "updated", "workspace_id": workspace_id}


@router.get("/detection-rules")
async def get_detection_rules(
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(
            select(AccountDetectionSetting).where(
                AccountDetectionSetting.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    return {
        "workspace_id": workspace_id,
        "sync_delay_minutes": row.sync_delay_minutes if row else 20,
        "sync_stale_minutes": row.sync_stale_minutes if row else 60,
        "content_inactive_days": row.content_inactive_days if row else 7,
        "source": "WORKSPACE" if row else "DEFAULT",
    }


@router.put("/detection-rules")
async def update_detection_rules(
    data: DetectionRulesUpdate,
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    if data.sync_stale_minutes <= data.sync_delay_minutes:
        raise HTTPException(status_code=422, detail="过期阈值必须大于延迟阈值")
    row = (
        await db.execute(
            select(AccountDetectionSetting).where(
                AccountDetectionSetting.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = AccountDetectionSetting(workspace_id=workspace_id)
        db.add(row)
    row.sync_delay_minutes = data.sync_delay_minutes
    row.sync_stale_minutes = data.sync_stale_minutes
    row.content_inactive_days = data.content_inactive_days
    await db.commit()
    return {
        "status": "updated",
        "workspace_id": workspace_id,
        **data.model_dump(),
    }


@router.get("/notifications")
async def get_notification_settings(db: AsyncSession = Depends(get_db)):
    return {"critical_only": False, "high_critical": True, "daily_digest": False, "weekly_digest": True}


@router.put("/notifications")
async def update_notification_settings(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return {"status": "updated", "settings": data}


@router.get("/permissions")
async def get_permissions():
    return {"roles": ["VIEWER", "ANALYST", "OPERATOR", "ADMIN"], "current_role": "ADMIN"}


@router.get("/feature-flags")
async def get_feature_flags(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(FeatureFlag))).scalars().all()
    return {r.flag_key: {"enabled": r.enabled, "rollout_pct": r.rollout_pct} for r in rows}


@router.get("/rules")
async def get_rule_settings(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(RuleDefinition))).scalars().all()
    latest = {}
    for r in rows:
        if r.rule_key not in latest or r.version > latest[r.rule_key].version:
            latest[r.rule_key] = r
    return [
        {"rule_key": r.rule_key, "status": r.status, "version": r.version, "severity": r.severity, "cooldown_minutes": r.cooldown_minutes}
        for r in latest.values()
    ]


@router.get("/preferences")
async def get_preferences(user_id: str = "demo-user", db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(UserDashboardPreference).where(UserDashboardPreference.user_id == user_id))).scalar_one_or_none()
    if row is None:
        return {"user_id": user_id, "default_date_range": "LAST_7_DAYS", "density": "COMPACT", "theme": "DARK"}
    return {"user_id": user_id, "default_date_range": row.default_date_range, "density": row.density, "theme": row.theme, "table_columns": row.table_columns}
