from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.rules import RuleDefinition, RuleParameter
from app.rules.audit import audit
from app.rules.engine import run_evaluation
from app.rules.registry import load_rule_packs

router = APIRouter()


class ManualEvaluationRequest(BaseModel):
    rule_keys: Optional[List[str]] = None
    as_of: Optional[str] = None


class ParameterUpdate(BaseModel):
    parameters: Dict[str, Any]


async def _get_rule(db: AsyncSession, rule_key: str) -> RuleDefinition:
    rule = (
        await db.execute(
            select(RuleDefinition)
            .where(RuleDefinition.rule_key == rule_key)
            .order_by(RuleDefinition.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return rule


@router.get("")
async def list_rules(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(RuleDefinition))).scalars().all()
    if not rows:
        # Fall back to YAML packs before rules are loaded into the DB.
        return load_rule_packs()
    result = []
    latest: Dict[str, RuleDefinition] = {}
    for row in rows:
        if row.rule_key not in latest or row.version > latest[row.rule_key].version:
            latest[row.rule_key] = row
    for row in latest.values():
        if category and row.category != category:
            continue
        if status and row.status != status:
            continue
        result.append(
            {
                "rule_key": row.rule_key,
                "name": row.name,
                "category": row.category,
                "platform": row.platform,
                "version": row.version,
                "status": row.status,
                "enabled": row.enabled,
                "severity": row.severity,
                "evaluation_level": row.evaluation_level,
                "schedule_group": row.schedule_group,
            }
        )
    return result


@router.get("/{rule_key}")
async def get_rule(rule_key: str, db: AsyncSession = Depends(get_db)):
    rule = await _get_rule(db, rule_key)
    params = (
        await db.execute(
            select(RuleParameter).where(
                RuleParameter.rule_key == rule_key,
                RuleParameter.valid_to.is_(None),
            )
        )
    ).scalars().all()
    return {
        "rule_key": rule.rule_key,
        "name": rule.name,
        "category": rule.category,
        "platform": rule.platform,
        "version": rule.version,
        "status": rule.status,
        "enabled": rule.enabled,
        "severity": rule.severity,
        "evaluation_level": rule.evaluation_level,
        "schedule_group": rule.schedule_group,
        "conditions": rule.conditions,
        "guards": rule.guards,
        "action_template": rule.action_template,
        "cooldown_minutes": rule.cooldown_minutes,
        "minimum_confidence": rule.minimum_confidence,
        "parameters": [{"key": p.parameter_key, "value": p.value, "source": p.source, "scope_type": p.scope_type} for p in params],
    }


async def _set_status(db: AsyncSession, rule_key: str, status: str, action: str) -> dict:
    rule = await _get_rule(db, rule_key)
    before = {"status": rule.status, "enabled": rule.enabled}
    rule.status = status
    if status in ("ACTIVE", "SHADOW"):
        rule.enabled = True
    if status == "PAUSED":
        rule.enabled = False
    await audit(db, actor="api", action=action, target=rule_key, before=before, after={"status": status})
    await db.commit()
    return {"rule_key": rule_key, "status": status}


@router.post("/{rule_key}/enable")
async def enable_rule(rule_key: str, db: AsyncSession = Depends(get_db)):
    return await _set_status(db, rule_key, "ACTIVE", "rule_enabled")


@router.post("/{rule_key}/disable")
async def disable_rule(rule_key: str, db: AsyncSession = Depends(get_db)):
    return await _set_status(db, rule_key, "PAUSED", "rule_disabled")


@router.post("/{rule_key}/shadow")
async def shadow_rule(rule_key: str, db: AsyncSession = Depends(get_db)):
    return await _set_status(db, rule_key, "SHADOW", "rule_shadowed")


@router.post("/{rule_key}/activate")
async def activate_rule(rule_key: str, db: AsyncSession = Depends(get_db)):
    return await _set_status(db, rule_key, "ACTIVE", "rule_activated")


@router.get("/{rule_key}/parameters")
async def get_parameters(rule_key: str, db: AsyncSession = Depends(get_db)):
    await _get_rule(db, rule_key)
    params = (
        await db.execute(
            select(RuleParameter).where(
                RuleParameter.rule_key == rule_key,
                RuleParameter.valid_to.is_(None),
            )
        )
    ).scalars().all()
    return {p.parameter_key: p.value for p in params}


@router.put("/{rule_key}/parameters")
async def put_parameters(rule_key: str, data: ParameterUpdate, db: AsyncSession = Depends(get_db)):
    await _get_rule(db, rule_key)
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    existing = (
        await db.execute(
            select(RuleParameter).where(
                RuleParameter.rule_key == rule_key,
                RuleParameter.scope_type == "GLOBAL",
                RuleParameter.valid_to.is_(None),
            )
        )
    ).scalars().all()
    for row in existing:
        row.valid_to = now
    for key, value in data.parameters.items():
        db.add(
            RuleParameter(
                rule_key=rule_key,
                parameter_key=key,
                scope_type="GLOBAL",
                value=value,
                value_type="number" if isinstance(value, (int, float)) else "string",
                source="MANUAL",
                valid_from=now,
            )
        )
    await audit(db, actor="api", action="parameter_changed", target=rule_key, after=data.parameters)
    await db.commit()
    return {"rule_key": rule_key, "parameters": data.parameters}


@router.post("/evaluate")
async def manual_evaluate(data: ManualEvaluationRequest, db: AsyncSession = Depends(get_db)):
    run = await run_evaluation(db, trigger_type="MANUAL", rule_keys=data.rule_keys, as_of=__import__("datetime").datetime.fromisoformat(data.as_of.replace("Z", "+00:00")) if data.as_of else None)
    if run is None:
        raise HTTPException(status_code=422, detail="no rules evaluated")
    return {"run_id": str(run.id), "triggered": run.triggered, "suppressed": run.suppressed, "entities": run.entities_evaluated}
