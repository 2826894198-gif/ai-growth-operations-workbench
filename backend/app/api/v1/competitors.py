from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("")
async def competitors(db: AsyncSession = Depends(get_db)):
    return {"watchlist": [], "enabled": settings.ai_browser_research_enabled}


@router.get("/{competitor_id}")
async def competitor_detail(competitor_id: str, db: AsyncSession = Depends(get_db)):
    return {"id": competitor_id, "status": "UNKNOWN", "note": "competitor research requires browser research enabled"}


@router.get("/{competitor_id}/snapshots")
async def competitor_snapshots(competitor_id: str, db: AsyncSession = Depends(get_db)):
    return {"snapshots": []}


@router.get("/competitor-intelligence/trends")
async def competitor_trends(db: AsyncSession = Depends(get_db)):
    return {"trends": [], "note": "observed public samples only"}
