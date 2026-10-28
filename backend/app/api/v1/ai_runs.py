from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.observability.tracing import run_summary
from app.ai.orchestrator.runner import cancel_run, resume_run, start_run
from app.core.database import get_db
from app.models.ai import AIAgentRun

router = APIRouter()


class RunCreate(BaseModel):
    task_type: str
    user_request: str
    scope: Dict[str, Any] = {}
    plan_agents_override: Optional[List[str]] = None


class ResumeRequest(BaseModel):
    thread_id: str
    decision: str


@router.post("/runs")
async def create_run(data: RunCreate, db: AsyncSession = Depends(get_db)):
    return await start_run(
        db,
        task_type=data.task_type,
        user_request=data.user_request,
        scope=data.scope,
        plan_agents_override=data.plan_agents_override,
    )


@router.get("/runs")
async def list_runs(
    task_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(AIAgentRun).order_by(AIAgentRun.created_at.desc()).limit(limit)
    if task_type:
        query = query.where(AIAgentRun.task_type == task_type)
    if status:
        query = query.where(AIAgentRun.status == status)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "thread_id": r.thread_id,
            "task_type": r.task_type,
            "status": r.status,
            "estimated_cost": r.estimated_cost,
            "total_model_calls": r.total_model_calls,
            "total_tool_calls": r.total_tool_calls,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/runs/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(AIAgentRun).where(AIAgentRun.id == run_id))).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return await run_summary(db, run_id)


@router.post("/runs/{run_id}/cancel")
async def cancel(run_id: str, db: AsyncSession = Depends(get_db)):
    return await cancel_run(db, run_id)


@router.post("/runs/resume")
async def resume(data: ResumeRequest, db: AsyncSession = Depends(get_db)):
    return await resume_run(db, data.thread_id, data.decision)
