"""Unified scope resolution + aggregation policy (E23-E27, E203)."""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social import Brand, ConnectedAccount
from app.services.social.metric_catalog import aggregate_values, metric_semantics


async def resolve_workspace_brand(db: AsyncSession, workspace_id: str, brand_id: Optional[str] = None) -> Optional[Brand]:
    if not workspace_id:
        return None
    query = select(Brand).where(Brand.workspace_id == workspace_id)
    if brand_id:
        query = query.where(Brand.id == brand_id)
    return (await db.execute(query.limit(1))).scalar_one_or_none()


async def resolve_accounts(
    db: AsyncSession,
    *,
    workspace_id: str,
    platforms: Optional[List[str]] = None,
    account_ids: Optional[List[str]] = None,
    brand_id: Optional[str] = None,
    account_group_id: Optional[str] = None,
) -> List[ConnectedAccount]:
    """Resolve connected accounts strictly inside the workspace (E143 isolation)."""
    query = select(ConnectedAccount).where(
        ConnectedAccount.workspace_id == workspace_id,
        ConnectedAccount.status == "LINKED",
    )
    if platforms:
        query = query.where(ConnectedAccount.platform.in_([p.upper() for p in platforms]))
    if account_ids:
        query = query.where(ConnectedAccount.id.in_(account_ids))
    if brand_id:
        query = query.where(ConnectedAccount.brand_id == brand_id)
    if account_group_id:
        query = query.where(ConnectedAccount.account_group_id == account_group_id)
    return list((await db.execute(query)).scalars().all())


async def aggregate_metric(
    db: AsyncSession,
    *,
    workspace_id: str,
    metric_key: str,
    values: List[float],
    rates_denominator: Optional[List[float]] = None,
) -> Dict[str, Any]:
    semantics = await metric_semantics(db, metric_key)
    return aggregate_values(values, semantics, rates_denominator=rates_denominator)


def scope_cache_key(scope: Dict[str, Any]) -> str:
    """Cache key must include the full scope (E142)."""
    import json

    return json.dumps(scope, sort_keys=True, ensure_ascii=False)
