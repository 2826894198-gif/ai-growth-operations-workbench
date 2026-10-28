"""Decision Assistant — single-agent review convergence (review 4.7).

One assistant with controlled read/simulate/draft tools. It cannot read write
keys and cannot call provider mutation; drafting an intent still requires human
approval and the PART 06 execution chain.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rules import Recommendation
from app.services.metric_service import query_metric


async def run_decision_assistant(
    db: AsyncSession,
    *,
    workspace_id: str,
    user_request: str,
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Single Decision Assistant turn (Mock; live mode reuses same tool contract)."""
    scope = scope or {}
    account_ids = scope.get("account_ids") or []
    tools_used: List[str] = []
    metric_rows: List[Dict[str, Any]] = []
    recommendation_rows: List[Dict[str, Any]] = []

    # Tool 1: query_metrics — pull canonical metrics through the metric service
    end = date.today()
    start = end - timedelta(days=int(scope.get("window_days", 14)))
    for metric_key in ("social_views", "paid_spend", "paid_roas", "orders"):
        try:
            result = await query_metric(
                db,
                workspace_id=workspace_id,
                metric_key=metric_key,
                account_ids=account_ids or None,
                start=start,
                end=end,
            )
            tools_used.append(f"query_metrics({metric_key})")
            metric_rows.append(result)
        except Exception:  # noqa: BLE001
            continue

    # Tool 2: retrieve_rule_evidence — list open recommendations in scope
    recs = (
        await db.execute(
            select(Recommendation)
            .where(Recommendation.status.in_(("OPEN", "ACKNOWLEDGED", "APPROVED")))
            .order_by(Recommendation.created_at.desc())
            .limit(8)
        )
    ).scalars().all()
    for rec in recs:
        tools_used.append(f"retrieve_rule_evidence({rec.id})")
        recommendation_rows.append(
            {
                "recommendation_id": str(rec.id),
                "primary_action": rec.primary_action,
                "reason_group": rec.reason_group,
                "severity": rec.severity,
                "confidence": rec.confidence,
                "case_status": rec.case_status,
                "entity": f"{rec.entity_type}:{rec.entity_id}",
            }
        )

    # Tool 3: explain_change — describe the most recent window movement
    tools_used.append("explain_change(last_14d)")
    explanation = _explain(metric_rows)

    answer = (
        f"基于当前 Scope（{workspace_id}）近 {scope.get('window_days', 14)} 天数据：{explanation}。"
        f"共发现 {len(recommendation_rows)} 条待处理规则信号。"
        + (
            "优先级建议：先查看最高严重度推荐并进入模拟/审批。"
            if recommendation_rows
            else "当前没有开放的高优先级规则信号；建议保持观察。"
        )
    )
    return {
        "mode": "mock",
        "answer": answer,
        "tools_used": tools_used,
        "metrics": metric_rows,
        "recommendations": recommendation_rows,
        "suggested_actions": [
            {"action": "open_recommendation_case", "target": r["recommendation_id"]} for r in recommendation_rows[:3]
        ],
        "limitations": [
            "Decision Assistant 只读、只模拟、只起草；不能直接修改广告",
            "平台自报指标与第一方归因分开呈现，不合并为唯一 ROAS",
        ],
    }


def _explain(metric_rows: List[Dict[str, Any]]) -> str:
    parts = []
    for row in metric_rows:
        if not row.get("ok"):
            continue
        value = row.get("value")
        parts.append(f"{row.get('display_name', row.get('metric_key'))}={value if value is not None else '无数据'}")
    return "；".join(parts) if parts else "无可用指标"


async def draft_execution_intent(db: AsyncSession, *, recommendation_id: str, actor: str = "assistant") -> Dict[str, Any]:
    """Draft only — create a PENDING approval and return the case draft (no mutation)."""
    from app.execution.service import create_approval_from_recommendation

    try:
        approval, detail = await create_approval_from_recommendation(
            db,
            recommendation_id=recommendation_id,
            approved_by=actor,
            force_mock=True,
            commit=False,
        )
        await db.rollback()
        return {
            "ok": True,
            "draft": {
                "action_type": approval.action_type,
                "provider": approval.provider,
                "entity_id": approval.entity_id,
                "requested_change": approval.approved_change,
                "risk_level": approval.risk_level,
                "expires_at": approval.expires_at.isoformat(),
            },
            "detail": detail,
            "caveat": "draft only; human approval required before any execution",
        }
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
