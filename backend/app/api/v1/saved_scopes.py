"""Saved scopes API (E27, E193-E194)."""


from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.social import SavedScope

router = APIRouter()


class SavedScopeCreate(BaseModel):
    workspace_id: str
    name: str
    scope: dict
    is_favorite: bool = False
    actor: str = "operator"


def _scope_dict(scope: SavedScope) -> dict:
    return {
        "id": str(scope.id),
        "workspace_id": scope.workspace_id,
        "name": scope.name,
        "scope": scope.scope,
        "is_favorite": scope.is_favorite,
        "created_by": scope.created_by,
        "created_at": scope.created_at.isoformat() if scope.created_at else None,
    }


@router.get("")
async def list_saved_scopes(workspace_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SavedScope).where(SavedScope.workspace_id == workspace_id).order_by(SavedScope.created_at.desc()))).scalars().all()
    return [_scope_dict(r) for r in rows]


@router.post("")
async def create_saved_scope(data: SavedScopeCreate, db: AsyncSession = Depends(get_db)):
    scope = SavedScope(
        workspace_id=data.workspace_id,
        name=data.name,
        scope=data.scope,
        is_favorite=data.is_favorite,
        created_by=data.actor,
    )
    db.add(scope)
    await db.commit()
    return _scope_dict(scope)
