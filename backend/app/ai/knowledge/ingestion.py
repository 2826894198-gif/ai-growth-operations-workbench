import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.knowledge.chunking import chunk_text
from app.models.ai import KnowledgeChunk, KnowledgeDocument


async def ingest_document(
    db: AsyncSession,
    *,
    document_type: str,
    title: str,
    content: str,
    source_uri: Optional[str] = None,
    status: str = "APPROVED",
    trust_level: str = "DATA",
    version: str = "1",
) -> dict:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    doc = KnowledgeDocument(
        document_type=document_type.upper(),
        title=title,
        version=version,
        source_uri=source_uri,
        content_hash=content_hash,
        status=status,
        trust_level=trust_level,
        effective_from=datetime.now(timezone.utc),
    )
    db.add(doc)
    await db.flush()
    for index, chunk in enumerate(chunk_text(content)):
        db.add(KnowledgeChunk(document_id=str(doc.id), chunk_index=index, content=chunk, metadata={"title": title, "document_type": document_type.upper()}))
    await db.commit()
    return {"document_id": str(doc.id), "title": title, "chunks": len(chunk_text(content)), "content_hash": content_hash}
