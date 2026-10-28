"""Browser node identity, allowlist and heartbeat (PART 07 §19-§21)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import BrowserNode


async def register_node(
    db: AsyncSession,
    *,
    name: str,
    allowed_workspace_ids: Optional[List[str]],
    credential_reference: str,
    version: Optional[str] = None,
) -> BrowserNode:
    node = BrowserNode(
        name=name,
        status="OFFLINE",
        allowed_workspace_ids=allowed_workspace_ids or [],
        credential_reference=credential_reference,
        version=version,
    )
    db.add(node)
    await db.flush()
    return node


async def heartbeat(
    db: AsyncSession,
    *,
    node_id: str,
    version: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> BrowserNode:
    node = (await db.execute(select(BrowserNode).where(BrowserNode.id == node_id))).scalar_one_or_none()
    if node is None:
        raise ValueError("browser node not found")
    if node.status == "REVOKED":
        raise ValueError("browser node revoked")
    if workspace_id and node.allowed_workspace_ids and workspace_id not in node.allowed_workspace_ids:
        raise ValueError("workspace not allowed for this browser node")
    node.last_heartbeat_at = datetime.now(timezone.utc)
    node.status = "ONLINE"
    if version:
        node.version = version
    await db.flush()
    return node


async def revoke_node(db: AsyncSession, node_id: str, actor: str) -> BrowserNode:
    node = (await db.execute(select(BrowserNode).where(BrowserNode.id == node_id))).scalar_one_or_none()
    if node is None:
        raise ValueError("browser node not found")
    node.status = "REVOKED"
    await db.flush()
    return node


async def list_nodes(db: AsyncSession, status: Optional[str] = None) -> List[Dict[str, Any]]:
    query = select(BrowserNode).order_by(BrowserNode.created_at.desc())
    if status:
        query = query.where(BrowserNode.status == status)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "status": r.status,
            "allowed_workspace_ids": r.allowed_workspace_ids,
            "last_heartbeat_at": r.last_heartbeat_at.isoformat() if r.last_heartbeat_at else None,
            "version": r.version,
            "credential_configured": bool(r.credential_reference),
        }
        for r in rows
    ]
