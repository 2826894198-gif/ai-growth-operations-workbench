
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIAgentRun, AIAgentStep, AIModelUsage, AIToolAudit


async def run_summary(db: AsyncSession, run_id: str) -> dict:
    run = (await db.execute(select(AIAgentRun).where(AIAgentRun.id == run_id))).scalar_one_or_none()
    if run is None:
        return {"error": "not found"}
    steps = (
        await db.execute(
            select(AIAgentStep).where(AIAgentStep.run_id == run_id).order_by(AIAgentStep.created_at.asc())
        )
    ).scalars().all()
    tool_audits = (
        await db.execute(select(AIToolAudit).where(AIToolAudit.run_id == run_id).order_by(AIToolAudit.created_at.asc()))
    ).scalars().all()
    usage = (
        await db.execute(select(AIModelUsage).where(AIModelUsage.run_id == run_id))
    ).scalars().all()
    return {
        "run": {
            "id": str(run.id),
            "thread_id": run.thread_id,
            "task_type": run.task_type,
            "status": run.status,
            "input_ref": run.input_ref,
            "output_ref": run.output_ref,
            "estimated_cost": run.estimated_cost,
        },
        "steps": [
            {
                "agent_type": s.agent_type,
                "step_type": s.step_type,
                "model": s.model_name,
                "latency_ms": s.latency_ms,
                "status": s.status,
                "cost": s.estimated_cost,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in steps
        ],
        "tool_calls": [
            {
                "agent_type": t.agent_type,
                "tool_name": t.tool_name,
                "risk_level": t.risk_level,
                "duration_ms": t.duration_ms,
                "success": t.success,
            }
            for t in tool_audits
        ],
        "usage": [
            {
                "provider": u.provider,
                "model": u.model,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "estimated_cost": u.estimated_cost,
            }
            for u in usage
        ],
    }
