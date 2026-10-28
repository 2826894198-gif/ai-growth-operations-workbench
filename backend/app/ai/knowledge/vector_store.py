from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import KnowledgeChunk


class VectorStoreAdapter:
    """Hybrid vector adapter: pgvector in production, JSON fallback in dev."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(self, embedding: List[float], top_k: int = 5) -> List[KnowledgeChunk]:
        # Dev fallback: cosine over stored JSON embeddings.
        rows = (await self.db.execute(select(KnowledgeChunk))).scalars().all()
        scored = []
        for row in rows:
            stored = row.embedding or []
            if not stored:
                continue
            score = _cosine(embedding, stored)
            scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [row for _, row in scored[:top_k]]


def _cosine(a: List[float], b: List[float]) -> float:
    import math

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
