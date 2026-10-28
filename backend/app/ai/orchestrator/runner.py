from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator.graph import build_graph
from app.models.ai import AIAgentRun


def _thread_id() -> str:
    return uuid4().hex


async def start_run(
    db: AsyncSession,
    *,
    task_type: str,
    user_request: str,
    scope: Optional[Dict[str, Any]] = None,
    thread_id: Optional[str] = None,
    plan_agents_override: Optional[list] = None,
) -> dict:
    thread_id = thread_id or _thread_id()
    run = AIAgentRun(
        thread_id=thread_id,
        task_type=task_type,
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
        orchestrator_version="0.1-langgraph",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    graph = build_graph(db)
    initial = {
        "run_id": str(run.id),
        "thread_id": thread_id,
        "task_type": task_type,
        "user_request": user_request,
        "scope": scope or {},
        "as_of_time": datetime.now(timezone.utc).isoformat(),
        "revision_count": 0,
        "status": "RUNNING",
        "errors": [],
        "tool_calls": 0,
        "token_usage": {},
        "cost_usage": 0.0,
    }
    if plan_agents_override:
        initial["plan_agents_override"] = plan_agents_override
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(initial, config)
    run.status = result.get("status", "COMPLETED")
    run.output_ref = f"run://{run.id}/output"
    run.meta = {
        "strategy_output": result.get("strategy_output"),
        "review_output": result.get("review_output"),
        "specialist_outputs": {k: v for k, v in (result.get("specialist_outputs") or {}).items()},
    }
    run.finished_at = datetime.now(timezone.utc)
    await db.commit()
    return {"run_id": str(run.id), "thread_id": thread_id, "status": run.status, "result": result}


async def resume_run(db: AsyncSession, thread_id: str, decision: str) -> dict:
    graph = build_graph(db)
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(Command(resume=decision), config)
    run = (await db.execute(select(AIAgentRun).where(AIAgentRun.thread_id == thread_id))).scalar_one_or_none()
    if run:
        run.status = result.get("status", "COMPLETED")
        run.finished_at = datetime.now(timezone.utc)
        await db.commit()
    return {"thread_id": thread_id, "status": result.get("status"), "result": result}


async def cancel_run(db: AsyncSession, run_id: str) -> dict:
    run = (await db.execute(select(AIAgentRun).where(AIAgentRun.id == run_id))).scalar_one_or_none()
    if run is None:
        return {"error": "not found"}
    run.status = "CANCELLED"
    run.finished_at = datetime.now(timezone.utc)
    await db.commit()
    return {"run_id": run_id, "status": "CANCELLED"}
