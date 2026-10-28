from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import KnowledgeChunk, KnowledgeDocument


async def hybrid_search(
    db: AsyncSession,
    query: str,
    *,
    document_types: Optional[List[str]] = None,
    top_k: int = 5,
    embedding: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Metadata filter + keyword search + optional vector similarity."""
    stmt = (
        select(KnowledgeChunk)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeDocument.status.in_(["APPROVED", "ACTIVE"]))
    )
    if document_types:
        stmt = stmt.where(KnowledgeDocument.document_type.in_([d.upper() for d in document_types]))
    keyword_hits = list(
        (
            await db.execute(
                stmt.where(or_(KnowledgeChunk.content.ilike(f"%{query}%"), KnowledgeDocument.title.ilike(f"%{query}%")))
                .limit(top_k)
            )
        ).scalars().all()
    )
    results = [{"document_id": c.document_id, "chunk_index": c.chunk_index, "content": c.content[:2000], "metadata": c.metadata} for c in keyword_hits]
    if embedding:
        from app.ai.knowledge.vector_store import VectorStoreAdapter

        vector_rows = await VectorStoreAdapter(db).search(embedding, top_k=top_k)
        existing = {r["document_id"] + str(r["chunk_index"]) for r in results}
        for row in vector_rows:
            key = row.document_id + str(row.chunk_index)
            if key not in existing:
                results.append({"document_id": row.document_id, "chunk_index": row.chunk_index, "content": row.content[:2000], "metadata": row.metadata})
    return {"chunks": results, "method": "hybrid" if embedding else "keyword"}
