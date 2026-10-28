"""API auth dependencies (review P0)."""

from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.governance import User
from app.services.auth_service import has_permission, seed_demo_admin


async def get_current_user(
    x_user_id: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Identity comes from the header in local demo; authorization is DB-backed."""
    if not x_user_id:
        if settings.execution_demo_permissions:
            return await seed_demo_admin(db)
        return None
    user = (await db.execute(select(User).where(User.id == x_user_id))).scalar_one_or_none()
    if user is None:
        user = (await db.execute(select(User).where(User.email == x_user_id))).scalar_one_or_none()
    if user is None and settings.execution_demo_permissions:
        return await seed_demo_admin(db)
    return user


def require_permission(permission: str):
    async def dependency(
        x_workspace_id: Optional[str] = Header(default="ws_main"),
        user: Optional[User] = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        if user is None:
            raise HTTPException(status_code=401, detail="authentication required")
        allowed = await has_permission(db, user=user, workspace_id=x_workspace_id, permission=permission)
        if not allowed:
            raise HTTPException(status_code=403, detail=f"missing permission: {permission}")

    return dependency
