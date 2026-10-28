from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.rules import RuleEvaluationRun
from app.rules.simulation.replay import replay_rule
from app.rules.simulation.simulator import simulate_rule

router = APIRouter()


class SimulationRequest(BaseModel):
    rule_key: str
    candidate_parameters: Dict[str, Any] = {}
    start_date: str
    end_date: str
    scope: str = "ALL"


class ReplayRequest(BaseModel):
    rule_key: str
    start_date: str
    end_date: str
    scope: str = "ALL"


@router.post("/rule-simulations")
async def create_simulation(data: SimulationRequest, db: AsyncSession = Depends(get_db)):
    result = await simulate_rule(db, data.rule_key, data.candidate_parameters, data.start_date, data.end_date, data.scope)
    return {"id": None, "status": "completed", **result}


@router.post("/rule-replays")
async def create_replay(data: ReplayRequest, db: AsyncSession = Depends(get_db)):
    return await replay_rule(db, data.rule_key, data.start_date, data.end_date, data.scope)


@router.get("/rule-simulations/{run_id}")
async def get_simulation(run_id: str, db: AsyncSession = Depends(get_db)):
    run = (
        await db.execute(
            select(RuleEvaluationRun).where(
                RuleEvaluationRun.id == run_id,
                RuleEvaluationRun.trigger_type.in_(["SIMULATION", "REPLAY"]),
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="simulation run not found")
    return {
        "run_id": str(run.id),
        "trigger_type": run.trigger_type,
        "triggered": run.triggered,
        "entities": run.entities_evaluated,
        "status": run.status,
    }
