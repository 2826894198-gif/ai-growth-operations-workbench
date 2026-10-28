from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_browser_task_service
from app.core.database import get_db
from app.core.security import require_worker_token
from app.schemas.browser_task import (
    BrowserTaskCreate,
    BrowserTaskListOut,
    BrowserTaskOut,
    BrowserTaskResultUpdate,
)
from app.services.browser_task_service import BrowserTaskService

router = APIRouter()


@router.post("", response_model=BrowserTaskOut, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    data: BrowserTaskCreate,
    db: AsyncSession = Depends(get_db),
    service: BrowserTaskService = Depends(get_browser_task_service),
):
    try:
        task = await service.create_task(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return BrowserTaskOut.model_validate(task)


@router.get("", response_model=BrowserTaskListOut)
async def list_tasks(
    profile_id: Optional[str] = Query(None),
    task_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    service: BrowserTaskService = Depends(get_browser_task_service),
):
    tasks = await service.list_tasks(db, profile_id=profile_id, status=task_status, limit=limit)
    return BrowserTaskListOut(items=[BrowserTaskOut.model_validate(t) for t in tasks], total=len(tasks))


@router.get("/{task_id}", response_model=BrowserTaskOut)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    service: BrowserTaskService = Depends(get_browser_task_service),
):
    task = await service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return BrowserTaskOut.model_validate(task)


@router.post("/{task_id}/cancel", response_model=BrowserTaskOut)
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    service: BrowserTaskService = Depends(get_browser_task_service),
):
    try:
        task = await service.cancel_task(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return BrowserTaskOut.model_validate(task)


# --- Worker-only endpoints (Bearer WORKER_TOKEN) ---------------------------


@router.get("/worker/tasks/{task_id}")
async def worker_get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    service: BrowserTaskService = Depends(get_browser_task_service),
    _: None = Depends(require_worker_token),
):
    data = await service.worker_task(db, task_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return data


@router.post("/{task_id}/result", response_model=BrowserTaskOut)
async def update_task_result(
    task_id: str,
    update: BrowserTaskResultUpdate,
    db: AsyncSession = Depends(get_db),
    service: BrowserTaskService = Depends(get_browser_task_service),
    _: None = Depends(require_worker_token),
):
    try:
        task = await service.update_result(db, task_id, update)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BrowserTaskOut.model_validate(task)


@router.post("/{task_id}/requeue", response_model=BrowserTaskOut)
async def requeue_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    service: BrowserTaskService = Depends(get_browser_task_service),
    _: None = Depends(require_worker_token),
):
    try:
        task = await service.requeue(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BrowserTaskOut.model_validate(task)
