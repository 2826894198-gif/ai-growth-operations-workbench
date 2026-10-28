from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator.router import classify_intent, try_direct_answer
from app.ai.orchestrator.runner import start_run
from app.core.database import get_db

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    scope: Dict[str, Any] = {}


@router.post("/query")
async def ai_query(data: QueryRequest, db: AsyncSession = Depends(get_db)):
    # Deterministic query gate: simple factual questions cost 0 LLM calls.
    direct = await try_direct_answer(db, data.query)
    if direct:
        return direct
    task_type = classify_intent(data.query)
    return await start_run(
        db,
        task_type=task_type,
        user_request=data.query,
        scope=data.scope,
    )
