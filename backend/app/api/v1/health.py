"""Detection-center read APIs."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.account_health_service import (
    account_health_detail,
    health_summary,
    update_event_workflow,
)

router = APIRouter()


class EventWorkflowUpdate(BaseModel):
    workspace_id: str = "ws_main"
    account_id: str
    rule_code: str
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED", "IGNORED"]
    owner_id: Optional[str] = None


@router.get("/summary")
async def summary(
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    return await health_summary(db, workspace_id=workspace_id)


@router.get("/accounts/{account_id}")
async def detail(
    account_id: str,
    workspace_id: str = Query("ws_main"),
    db: AsyncSession = Depends(get_db),
):
    result = await account_health_detail(db, workspace_id=workspace_id, account_id=account_id)
    if result is None:
        raise HTTPException(status_code=404, detail="account not found in workspace")
    return result


@router.patch("/events/workflow")
async def update_workflow(
    data: EventWorkflowUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await update_event_workflow(
        db,
        workspace_id=data.workspace_id,
        account_id=data.account_id,
        rule_code=data.rule_code,
        status=data.status,
        owner_id=data.owner_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="active event not found in workspace")
    await db.commit()
    return result
