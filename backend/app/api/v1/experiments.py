from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Experiment

router = APIRouter()


class ExperimentCreate(BaseModel):
    name: str
    hypothesis: Optional[str] = None
    variable: Optional[str] = None
    control: Optional[str] = None
    treatment: Optional[str] = None
    primary_metric: Optional[str] = None
    guardrail_metrics: Optional[list] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    status: str = "PLANNED"
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None


class ExperimentUpdate(BaseModel):
    status: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    learnings: Optional[Dict[str, Any]] = None
    end_at: Optional[str] = None


@router.get("")
async def list_experiments(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(Experiment).order_by(Experiment.created_at.desc())
    if status:
        query = query.where(Experiment.status == status)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "hypothesis": r.hypothesis,
            "variable": r.variable,
            "primary_metric": r.primary_metric,
            "status": r.status,
            "start_at": r.start_at.isoformat() if r.start_at else None,
            "end_at": r.end_at.isoformat() if r.end_at else None,
            "protected_by_rule": r.protected_by_rule,
        }
        for r in rows
    ]


@router.post("")
async def create_experiment(data: ExperimentCreate, db: AsyncSession = Depends(get_db)):
    row = Experiment(**data.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": str(row.id), "status": row.status}


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Experiment).where(Experiment.id == experiment_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return {
        "id": str(row.id),
        "name": row.name,
        "hypothesis": row.hypothesis,
        "variable": row.variable,
        "control": row.control,
        "treatment": row.treatment,
        "primary_metric": row.primary_metric,
        "guardrail_metrics": row.guardrail_metrics,
        "status": row.status,
        "result": row.result,
        "learnings": row.learnings,
        "protected_by_rule": row.protected_by_rule,
        "scope_type": row.scope_type,
        "scope_id": row.scope_id,
    }


@router.put("/{experiment_id}")
async def update_experiment(experiment_id: str, data: ExperimentUpdate, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Experiment).where(Experiment.id == experiment_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, key, value)
    await db.commit()
    return {"id": experiment_id, "status": row.status}


@router.post("/{experiment_id}/complete")
async def complete_experiment(experiment_id: str, result: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(Experiment).where(Experiment.id == experiment_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    row.status = "COMPLETED"
    row.result = result
    row.end_at = datetime.now()
    await db.commit()
    return {"id": experiment_id, "status": "COMPLETED"}
