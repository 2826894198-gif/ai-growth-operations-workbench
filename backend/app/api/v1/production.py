"""PART 07 production APIs: browser nodes, releases, retention, metrics."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_permission
from app.core.database import get_db
from app.observability.metrics import snapshot
from app.services import browser_node_service, release_service, retention_service

router = APIRouter()


class BrowserNodeRegister(BaseModel):
    name: str
    credential_reference: str
    allowed_workspace_ids: Optional[List[str]] = None
    version: Optional[str] = None


class BrowserNodeHeartbeat(BaseModel):
    version: Optional[str] = None
    workspace_id: Optional[str] = None


class ReleaseCreate(BaseModel):
    version: str
    git_sha: str
    environment: str
    db_revision: Optional[str] = None
    image_digests: Optional[dict] = None
    deployed_by: Optional[str] = None
    notes: Optional[str] = None


@router.get("/metrics")
async def metrics_endpoint():
    return snapshot()


@router.get("/browser-nodes", dependencies=[Depends(require_permission("READ"))])
async def list_browser_nodes(status: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    return await browser_node_service.list_nodes(db, status=status)


@router.post("/browser-nodes", dependencies=[Depends(require_permission("CONNECTION_ADMIN"))])
async def register_browser_node(data: BrowserNodeRegister, db: AsyncSession = Depends(get_db)):
    node = await browser_node_service.register_node(
        db,
        name=data.name,
        allowed_workspace_ids=data.allowed_workspace_ids,
        credential_reference=data.credential_reference,
        version=data.version,
    )
    await db.commit()
    return {"id": str(node.id), "name": node.name, "status": node.status}


@router.post("/browser-nodes/{node_id}/heartbeat")
async def browser_node_heartbeat(node_id: str, data: BrowserNodeHeartbeat = None, db: AsyncSession = Depends(get_db)):
    try:
        node = await browser_node_service.heartbeat(
            db,
            node_id=node_id,
            version=data.version if data else None,
            workspace_id=data.workspace_id if data else None,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": str(node.id), "status": node.status, "last_heartbeat_at": node.last_heartbeat_at.isoformat() if node.last_heartbeat_at else None}


@router.post("/browser-nodes/{node_id}/revoke", dependencies=[Depends(require_permission("CONNECTION_ADMIN"))])
async def revoke_browser_node(node_id: str, db: AsyncSession = Depends(get_db)):
    try:
        node = await browser_node_service.revoke_node(db, node_id, "admin")
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": str(node.id), "status": node.status}


@router.get("/releases", dependencies=[Depends(require_permission("READ"))])
async def list_releases(environment: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    return await release_service.list_releases(db, environment=environment, limit=limit)


@router.post("/releases", dependencies=[Depends(require_permission("POLICY_ADMIN"))])
async def record_release(data: ReleaseCreate, db: AsyncSession = Depends(get_db)):
    release = await release_service.record_release(
        db,
        version=data.version,
        git_sha=data.git_sha,
        environment=data.environment,
        db_revision=data.db_revision,
        image_digests=data.image_digests,
        deployed_by=data.deployed_by,
        notes=data.notes,
    )
    await db.commit()
    return {"id": str(release.id), "version": release.version, "environment": release.environment, "status": release.status}


@router.get("/retention-policies", dependencies=[Depends(require_permission("READ"))])
async def retention_policies(db: AsyncSession = Depends(get_db)):
    return await retention_service.list_policies(db)


@router.post("/retention-policies/seed", dependencies=[Depends(require_permission("POLICY_ADMIN"))])
async def seed_retention_policies(db: AsyncSession = Depends(get_db)):
    created = await retention_service.seed_retention_policies(db)
    await db.commit()
    return {"created": created}
