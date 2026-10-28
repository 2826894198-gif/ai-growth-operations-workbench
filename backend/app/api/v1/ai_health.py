from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models.router import route_task
from app.ai.observability.metrics import ai_metrics
from app.ai.tools.registry import registry
from app.core.config import settings
from app.core.database import get_db
from app.models.ai import AIAgentRun, AIBusinessMemory, AIModelUsage, KnowledgeDocument

router = APIRouter()


@router.get("/health")
async def ai_health(db: AsyncSession = Depends(get_db)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    runs_today = (await db.execute(select(func.count()).select_from(AIAgentRun).where(AIAgentRun.created_at >= today_start))).scalar_one()
    failed = (await db.execute(select(func.count()).select_from(AIAgentRun).where(AIAgentRun.status == "FAILED"))).scalar_one()
    cost_today = (await db.execute(select(func.sum(AIModelUsage.estimated_cost)).where(AIModelUsage.created_at >= today_start))).scalar_one() or 0
    return {
        "orchestrator": {"runtime": settings.ai_orchestrator, "version": "0.1-langgraph", "mode": settings.ai_provider_mode},
        "model_providers": {
            "primary": {"provider": settings.ai_primary_provider, "model": settings.ai_primary_reasoning_model or "mock"},
            "fast": {"provider": settings.ai_fast_provider, "model": settings.ai_fast_model or "mock"},
            "video": {"provider": settings.ai_video_provider, "model": settings.ai_video_model or "mock"},
            "status": "HEALTHY" if settings.ai_provider_mode == "mock" else "CONFIGURED",
        },
        "model_route_sample": route_task("performance_diagnosis").__dict__,
        "knowledge": {"documents": (await db.execute(select(func.count()).select_from(KnowledgeDocument))).scalar_one()},
        "memory": {"memories": (await db.execute(select(func.count()).select_from(AIBusinessMemory))).scalar_one()},
        "tool_registry": {"tools": len(registry.list())},
        "runs_today": runs_today,
        "failed_runs": failed,
        "cost_today": float(cost_today or 0),
        "metrics": ai_metrics.snapshot(),
    }
