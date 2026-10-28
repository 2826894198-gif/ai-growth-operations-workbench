from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import KnowledgeChunk, KnowledgeDocument


async def _search_knowledge(db: AsyncSession, query: str, document_types: List[str], top_k: int = 5) -> Dict[str, Any]:
    chunks = (
        await db.execute(
            select(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(
                KnowledgeDocument.status.in_(["APPROVED", "ACTIVE"]),
                KnowledgeDocument.document_type.in_(document_types),
                or_(KnowledgeChunk.content.ilike(f"%{query}%"), KnowledgeDocument.title.ilike(f"%{query}%")),
            )
            .limit(top_k)
        )
    ).scalars().all()
    return {
        "chunks": [
            {"document_id": c.document_id, "chunk_index": c.chunk_index, "content": c.content[:2000], "metadata": c.metadata}
            for c in chunks
        ]
    }


async def search_brand_knowledge(db: AsyncSession, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
    return await _search_knowledge(db, query, ["BRAND"], top_k or 5)


async def search_product_knowledge(db: AsyncSession, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
    return await _search_knowledge(db, query, ["PRODUCT"], top_k or 5)


async def search_growth_playbook(db: AsyncSession, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
    return await _search_knowledge(db, query, ["PLAYBOOK", "RULES"], top_k or 5)


async def search_site_knowledge(db: AsyncSession, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
    return await _search_knowledge(db, query, ["SITE"], top_k or 5)


async def search_creative_taxonomy(db: AsyncSession, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
    return await _search_knowledge(db, query, ["CREATIVE"], top_k or 5)
