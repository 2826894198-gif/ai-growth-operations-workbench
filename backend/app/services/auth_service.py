"""Tenant RBAC: users, workspace membership, brand/account grants (review P0)."""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import AccountGrant, BrandGrant, User, WorkspaceMembership

ROLE_PERMISSIONS = {
    "VIEWER": {"READ", "ANALYZE"},
    "ANALYST": {"READ", "ANALYZE"},
    "OPERATOR": {"READ", "ANALYZE", "APPROVE", "EXECUTE"},
    "ADMIN": {"READ", "ANALYZE", "APPROVE", "EXECUTE", "POLICY_ADMIN", "KILL_SWITCH", "CONNECTION_ADMIN"},
}


async def get_or_create_user(db: AsyncSession, *, email: str, display_name: Optional[str] = None, roles: Optional[List[str]] = None) -> User:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is not None:
        return user
    user = User(email=email, display_name=display_name or email, status="ACTIVE", roles=roles or ["ANALYST"])
    db.add(user)
    await db.flush()
    return user


async def ensure_membership(db: AsyncSession, *, user_id: str, workspace_id: str, role: str = "VIEWER") -> WorkspaceMembership:
    membership = (
        await db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if membership is not None:
        return membership
    membership = WorkspaceMembership(user_id=user_id, workspace_id=workspace_id, role=role, status="ACTIVE")
    db.add(membership)
    await db.flush()
    return membership


async def get_membership(db: AsyncSession, *, user_id: str, workspace_id: str) -> Optional[WorkspaceMembership]:
    return (
        await db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user_id,
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()


async def has_permission(
    db: AsyncSession,
    *,
    user: User,
    workspace_id: str,
    permission: str,
    brand_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> bool:
    """Permission check: global role > workspace role > brand/account grants."""
    if "ADMIN" in (user.roles or []):
        return True
    membership = await get_membership(db, user_id=str(user.id), workspace_id=workspace_id)
    if membership is None:
        return False
    if permission in ROLE_PERMISSIONS.get(membership.role, set()):
        return True
    if brand_id:
        grant = (
            await db.execute(
                select(BrandGrant).where(
                    BrandGrant.membership_id == str(membership.id),
                    BrandGrant.brand_id == brand_id,
                    BrandGrant.permission == permission,
                )
            )
        ).scalar_one_or_none()
        if grant is not None:
            return True
    if account_id:
        grant = (
            await db.execute(
                select(AccountGrant).where(
                    AccountGrant.membership_id == str(membership.id),
                    AccountGrant.account_id == account_id,
                    AccountGrant.permission == permission,
                )
            )
        ).scalar_one_or_none()
        if grant is not None:
            return True
    return False


async def grant_brand(db: AsyncSession, *, membership_id: str, workspace_id: str, brand_id: str, permission: str) -> BrandGrant:
    grant = BrandGrant(membership_id=membership_id, workspace_id=workspace_id, brand_id=brand_id, permission=permission)
    db.add(grant)
    await db.flush()
    return grant


async def grant_account(db: AsyncSession, *, membership_id: str, workspace_id: str, account_id: str, permission: str) -> AccountGrant:
    grant = AccountGrant(membership_id=membership_id, workspace_id=workspace_id, account_id=account_id, permission=permission)
    db.add(grant)
    await db.flush()
    return grant


async def seed_demo_admin(db: AsyncSession) -> User:
    """Local demo admin user; production replaces header identity with SSO."""
    user = await get_or_create_user(db, email="admin@recollect.test", display_name="Demo Admin", roles=["ADMIN"])
    await ensure_membership(db, user_id=str(user.id), workspace_id="ws_main", role="ADMIN")
    await db.flush()
    return user


def user_dict(user: User) -> Dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "roles": user.roles,
        "status": user.status,
    }
