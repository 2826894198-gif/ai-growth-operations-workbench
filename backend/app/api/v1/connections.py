"""Connection Center API (E169-E171)."""

from html import escape
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.social import ConnectedAccount, ProviderConnection
from app.services.instagram.business_login import (
    InstagramBusinessLoginError,
    complete_business_login,
    start_business_login,
)
from app.services.social.connection_service import (
    complete_oauth_callback,
    connection_health,
    discover_accounts,
    link_accounts,
    reauthorize,
    serialize_connection,
    start_oauth,
    validate_connection,
)

router = APIRouter()
capabilities_router = APIRouter()


class OAuthStart(BaseModel):
    workspace_id: str
    redirect_uri: Optional[str] = None
    actor: str = "operator"


class OAuthCallback(BaseModel):
    workspace_id: str
    state: str
    code: str
    actor: str = "operator"


class LinkAccounts(BaseModel):
    external_account_ids: List[str]
    workspace_id: str
    brand_id: Optional[str] = None
    account_group_id: Optional[str] = None
    actor: str = "operator"


class ConnectionAction(BaseModel):
    actor: str = "operator"


@router.get("")
async def list_connections(workspace_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    rows = (
        (
            await db.execute(
                select(ProviderConnection)
                .where(ProviderConnection.workspace_id == workspace_id)
                .order_by(ProviderConnection.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [serialize_connection(r) for r in rows]


@router.post("/{provider}/start-oauth")
async def start_oauth_endpoint(provider: str, data: OAuthStart, db: AsyncSession = Depends(get_db)):
    try:
        if provider.upper() == "INSTAGRAM":
            result = await start_business_login(
                db, workspace_id=data.workspace_id, actor=data.actor
            )
        else:
            result = await start_oauth(
                db,
                workspace_id=data.workspace_id,
                provider=provider,
                actor=data.actor,
                redirect_uri=data.redirect_uri,
            )
        await db.commit()
        return result
    except (InstagramBusinessLoginError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _oauth_callback_page(*, success: bool, message: str) -> str:
    title = (
        "Instagram connection completed" if success else "Instagram connection was not completed"
    )
    tone = "#0f766e" if success else "#b91c1c"
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title><body style="font-family:system-ui;margin:48px;max-width:640px">'
        f'<h1 style="color:{tone}">{escape(title)}</h1>'
        f"<p>{escape(message)}</p><p>You can return to the Growth dashboard.</p></body></html>"
    )


@router.get("/instagram/oauth/callback", response_class=HTMLResponse)
async def instagram_oauth_callback_endpoint(
    state: str = Query(..., min_length=16),
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    result = await complete_business_login(
        db,
        state=state,
        code=code,
        error=error,
        error_reason=error_reason,
    )
    await db.commit()
    return HTMLResponse(
        _oauth_callback_page(success=result.success, message=result.message),
        status_code=200 if result.success else 400,
    )


@router.post("/oauth/callback")
async def oauth_callback_endpoint(data: OAuthCallback, db: AsyncSession = Depends(get_db)):
    try:
        connection = await complete_oauth_callback(
            db,
            workspace_id=data.workspace_id,
            provider="META",
            state=data.state,
            code=data.code,
            actor=data.actor,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_connection(connection)


@router.get("/{connection_id}")
async def get_connection(connection_id: str, db: AsyncSession = Depends(get_db)):
    connection = (
        await db.execute(select(ProviderConnection).where(ProviderConnection.id == connection_id))
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=404, detail="connection not found")
    return serialize_connection(connection)


@router.post("/{connection_id}/validate")
async def validate_connection_endpoint(
    connection_id: str, data: ConnectionAction = None, db: AsyncSession = Depends(get_db)
):
    try:
        result = await validate_connection(db, connection_id, data.actor if data else "operator")
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.post("/{connection_id}/reauthorize")
async def reauthorize_endpoint(
    connection_id: str, data: ConnectionAction = None, db: AsyncSession = Depends(get_db)
):
    try:
        result = await reauthorize(db, connection_id, data.actor if data else "operator")
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.post("/{connection_id}/discover")
async def discover_endpoint(
    connection_id: str, data: ConnectionAction = None, db: AsyncSession = Depends(get_db)
):
    try:
        result = await discover_accounts(db, connection_id, data.actor if data else "operator")
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.get("/{connection_id}/resources")
async def connection_resources(connection_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        (
            await db.execute(
                select(ConnectedAccount).where(ConnectedAccount.connection_id == connection_id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "connection_id": connection_id,
        "linked": [
            {
                "id": str(r.id),
                "platform": r.platform,
                "username": r.username,
                "account_type": r.account_type,
                "external_account_id": r.external_account_id,
                "status": r.status,
            }
            for r in rows
        ],
    }


@router.post("/{connection_id}/link-accounts")
async def link_accounts_endpoint(
    connection_id: str, data: LinkAccounts, db: AsyncSession = Depends(get_db)
):
    try:
        linked = await link_accounts(
            db,
            connection_id=connection_id,
            external_account_ids=data.external_account_ids,
            workspace_id=data.workspace_id,
            brand_id=data.brand_id,
            account_group_id=data.account_group_id,
            actor=data.actor,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "linked": [
            {
                "id": str(r.id),
                "platform": r.platform,
                "username": r.username,
                "external_account_id": r.external_account_id,
            }
            for r in linked
        ]
    }


@router.get("/{connection_id}/health")
async def health_endpoint(connection_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await connection_health(db, connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@capabilities_router.get("")
async def list_provider_capabilities(
    provider: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)
):
    from app.models.social import ProviderCapability

    query = select(ProviderCapability).order_by(
        ProviderCapability.provider, ProviderCapability.capability_key
    )
    if provider:
        query = query.where(ProviderCapability.provider == provider.upper())
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "provider": r.provider,
            "platform": r.platform,
            "capability_key": r.capability_key,
            "default_supported": r.default_supported,
            "requires_permission": r.requires_permission,
            "provider_version": r.provider_version,
            "description": r.description,
        }
        for r in rows
    ]
