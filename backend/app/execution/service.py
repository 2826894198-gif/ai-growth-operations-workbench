"""Execution service helpers: recommendation -> approval -> intent."""

from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.approvals import approve_approval, create_approval
from app.execution.intents import create_intent
from app.execution.providers.factory import get_execution_provider
from app.execution.risk import classify_blast_radius, classify_risk
from app.models.execution import ExecutionApproval, ExecutionIntent
from app.models.rules import Recommendation

ACTION_MAP = {
    "META_ADS": {
        "REVIEW_PAUSE": "META_PAUSE_ENTITY",
        "REVIEW_ENABLE": "META_ENABLE_ENTITY",
        "REVIEW_REDUCE_BUDGET": "META_CHANGE_BUDGET",
        "REVIEW_SCALE": "META_CHANGE_BUDGET",
        "REVIEW_EMERGENCY_BUDGET_CONTROL": "META_CHANGE_BUDGET",
    },
    "GOOGLE_ADS": {
        "REVIEW_PAUSE": "GOOGLE_PAUSE_CAMPAIGN",
        "REVIEW_ENABLE": "GOOGLE_ENABLE_CAMPAIGN",
        "REVIEW_REDUCE_BUDGET": "GOOGLE_CHANGE_BUDGET",
        "REVIEW_SCALE": "GOOGLE_CHANGE_BUDGET",
        "REVIEW_EMERGENCY_BUDGET_CONTROL": "GOOGLE_CHANGE_BUDGET",
    },
}


def map_recommendation_action(rec: Recommendation) -> Optional[str]:
    platform_map = ACTION_MAP.get((rec.platform or "").upper())
    if not platform_map:
        return None
    return platform_map.get((rec.primary_action or "").upper())


def _mock_intent(rec: Recommendation, action_type: str) -> SimpleNamespace:
    provider = "META" if (rec.platform or "").upper() == "META_ADS" else "GOOGLE_ADS"
    return SimpleNamespace(
        id=f"preview-{rec.id}",
        provider=provider,
        action_type=action_type,
        entity_type=rec.entity_type.upper() if rec.entity_type and rec.entity_type.upper() != "ACCOUNT" else ("CAMPAIGN" if provider == "GOOGLE_ADS" else "CAMPAIGN"),
        entity_id=rec.entity_id or "camp_1001",
        external_entity_id=rec.entity_id,
        requested_change={},
        expected_before_state=None,
        workspace_id=None,
    )


async def current_state_for_recommendation(db: AsyncSession, rec: Recommendation, action_type: str, force_mock: bool = True) -> Dict[str, Any]:
    provider = get_execution_provider(("META" if (rec.platform or "").upper() == "META_ADS" else "GOOGLE_ADS"), force_mock=force_mock)
    return await provider.get_current_state(_mock_intent(rec, action_type))


async def build_requested_change(rec: Recommendation, action_type: str, current_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if "BUDGET" in action_type:
        current_budget = current_state.get("budget") or current_state.get("daily_budget")
        if action_type.startswith("GOOGLE_"):
            # Google CampaignBudget amount_micros is authoritative; the
            # convenience "budget" field on campaigns can lag behind.
            if current_state.get("amount_micros") is not None:
                current_budget = None
        if current_budget is None and current_state.get("amount_micros") is not None:
            from app.execution.providers.google_ads.budget import micros_to_decimal

            current_budget = micros_to_decimal(current_state["amount_micros"])
        if current_budget is None:
            return None
        pct = rec.suggested_change_pct if rec.suggested_change_pct is not None else 0.0
        proposed = Decimal(str(current_budget)) * (Decimal("1") + Decimal(str(pct)) / Decimal("100"))
        change = {
            "current_budget": str(current_budget),
            "proposed_budget": str(proposed),
            "currency": "USD",
            "confidence": rec.confidence or 0.0,
        }
        if action_type.startswith("META_"):
            change["budget_owner"] = current_state.get("budget_owner") or "CAMPAIGN"
            change["budget_owner_entity_id"] = current_state.get("budget_owner_entity_id") or rec.entity_id
        else:
            change["budget_resource"] = current_state.get("budget_resource")
            change["affected_campaigns"] = [str(c.get("id")) for c in current_state.get("campaigns", [])]
            change["shared_budget_explicitly_approved"] = False
        return change
    if "PAUSE" in action_type or "ENABLE" in action_type:
        return {
            "entity_type": rec.entity_type.upper() if rec.entity_type and rec.entity_type.upper() != "ACCOUNT" else "CAMPAIGN",
            "current_status": current_state.get("status", "ACTIVE"),
            "proposed_status": "PAUSED" if "PAUSE" in action_type else ("ACTIVE" if action_type.startswith("META_") else "ENABLED"),
            "confidence": rec.confidence or 0.0,
        }
    return None


async def create_approval_from_recommendation(
    db: AsyncSession,
    *,
    recommendation_id: str,
    approved_by: str,
    force_mock: bool = True,
    commit: bool = True,
    provider_override=None,
) -> Tuple[ExecutionApproval, Dict[str, Any]]:
    rec = (await db.execute(select(Recommendation).where(Recommendation.id == recommendation_id))).scalar_one_or_none()
    if rec is None:
        raise ValueError("recommendation not found")
    if rec.status not in ("OPEN", "ACKNOWLEDGED", "APPROVED"):
        raise ValueError(f"recommendation status {rec.status} is not actionable")
    action_type = map_recommendation_action(rec)
    if action_type is None:
        raise ValueError(f"recommendation action {rec.primary_action} has no executable mapping")
    provider = "META" if (rec.platform or "").upper() == "META_ADS" else "GOOGLE_ADS"
    if provider_override is not None:
        current_state = await provider_override.get_current_state(_mock_intent(rec, action_type))
    else:
        current_state = await current_state_for_recommendation(db, rec, action_type, force_mock=force_mock)
    requested_change = await build_requested_change(rec, action_type, current_state)
    if not requested_change:
        raise ValueError("cannot build requested change from recommendation (missing current budget state)")
    entity_type = rec.entity_type.upper() if rec.entity_type and rec.entity_type.upper() != "ACCOUNT" else "CAMPAIGN"
    delta_pct = None
    if "BUDGET" in action_type:
        try:
            delta_pct = (Decimal(requested_change["proposed_budget"]) - Decimal(requested_change["current_budget"])) / Decimal(
                requested_change["current_budget"]
            ) * Decimal("100")
        except (ValueError, ZeroDivisionError):
            delta_pct = None
    blast = classify_blast_radius(
        affected_campaigns=len(current_state.get("campaigns") or []) if action_type.startswith("GOOGLE_") else 1,
        shared_budget=bool(current_state.get("explicitly_shared")),
    )
    risk = classify_risk(action_type, blast_radius=blast, delta_pct=delta_pct, shared_budget=bool(current_state.get("explicitly_shared")))
    approval = await create_approval(
        db,
        workspace_id=None,
        recommendation_id=recommendation_id,
        provider=provider,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=rec.entity_id or "camp_1001",
        external_entity_id=rec.entity_id,
        approved_change=requested_change,
        expected_before_state=current_state,
        approved_by=approved_by,
        risk_level=risk,
        status="PENDING",
    )
    if commit:
        await db.commit()
    else:
        await db.flush()
    return approval, {"current_state": current_state, "requested_change": requested_change, "risk": risk, "blast_radius": blast}


async def approve_and_create_intent(db: AsyncSession, approval_id: str, actor: str) -> ExecutionIntent:
    approval = await approve_approval(db, approval_id, actor)
    blast = classify_blast_radius(
        affected_campaigns=len(approval.approved_change.get("affected_campaigns") or []) if approval.provider == "GOOGLE_ADS" else 1,
        shared_budget=bool(approval.approved_change.get("shared_budget_explicitly_approved")),
    )
    intent = await create_intent(
        db,
        workspace_id=approval.workspace_id,
        recommendation_id=approval.recommendation_id,
        approval=approval,
        provider=approval.provider,
        action_type=approval.action_type,
        entity_type=approval.entity_type,
        entity_id=approval.entity_id,
        external_entity_id=approval.external_entity_id,
        requested_change=approval.approved_change,
        expected_before_state=approval.expected_before_state,
        account_id=None,
        policy_version=1,
        blast_radius=blast,
        shadow_only=False,
        status="APPROVED",
    )
    await db.commit()
    return intent
