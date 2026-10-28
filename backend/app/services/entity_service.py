"""Canonical entity registry + external ID resolver (review 4.1).

Rules, recommendations, scopes, caches and execution intents carry only the
canonical entity_id; provider calls resolve external IDs here.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import EntityRegistry, EntityRelation, ExternalEntityRef


async def resolve_or_create_entity(
    db: AsyncSession,
    *,
    workspace_id: str,
    brand_id: Optional[str],
    entity_type: str,
    display_name: Optional[str] = None,
    external_refs: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> EntityRegistry:
    """Find an existing canonical entity by type+name, otherwise create it and
    attach provider-native external refs."""
    entity_type = entity_type.upper()
    existing = None
    if display_name:
        existing = (
            await db.execute(
                select(EntityRegistry).where(
                    EntityRegistry.workspace_id == workspace_id,
                    EntityRegistry.entity_type == entity_type,
                    EntityRegistry.display_name == display_name,
                    EntityRegistry.status == "ACTIVE",
                )
            )
        ).scalar_one_or_none()
    if existing is None:
        existing = EntityRegistry(
            workspace_id=workspace_id,
            brand_id=brand_id,
            entity_type=entity_type,
            display_name=display_name or f"{entity_type} {workspace_id[:8]}",
            status="ACTIVE",
            metadata=metadata,
        )
        db.add(existing)
        await db.flush()
    for ref in external_refs or []:
        await register_external_ref(
            db,
            entity_id=str(existing.id),
            provider=ref["provider"],
            connected_account_id=ref.get("connected_account_id"),
            external_type=ref.get("external_type", "PRIMARY"),
            external_id=ref["external_id"],
            metadata=ref.get("metadata"),
        )
    return existing


async def register_external_ref(
    db: AsyncSession,
    *,
    entity_id: str,
    provider: str,
    connected_account_id: Optional[str],
    external_type: str,
    external_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> ExternalEntityRef:
    existing = (
        await db.execute(
            select(ExternalEntityRef).where(
                ExternalEntityRef.provider == provider,
                ExternalEntityRef.connected_account_id == connected_account_id,
                ExternalEntityRef.external_type == external_type,
                ExternalEntityRef.external_id == external_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.entity_id != entity_id:
            # Re-point the ref when the same provider id now belongs to a new canonical entity.
            existing.entity_id = entity_id
            existing.valid_from = datetime.now(timezone.utc)
        return existing
    row = ExternalEntityRef(
        entity_id=entity_id,
        provider=provider,
        connected_account_id=connected_account_id,
        external_type=external_type,
        external_id=external_id,
        valid_from=datetime.now(timezone.utc),
        metadata=metadata,
    )
    db.add(row)
    await db.flush()
    return row


async def get_entity(db: AsyncSession, entity_id: str) -> Optional[EntityRegistry]:
    return (await db.execute(select(EntityRegistry).where(EntityRegistry.id == entity_id))).scalar_one_or_none()


async def resolve_external_id(
    db: AsyncSession,
    *,
    entity_id: str,
    provider: str,
    connected_account_id: Optional[str] = None,
    external_type: str = "PRIMARY",
) -> Optional[str]:
    """Resolve canonical entity -> provider-native ID under the account."""
    query = select(ExternalEntityRef).where(
        ExternalEntityRef.entity_id == entity_id,
        ExternalEntityRef.provider == provider,
        ExternalEntityRef.external_type == external_type,
        ExternalEntityRef.valid_to.is_(None),
    )
    if connected_account_id:
        query = query.where(ExternalEntityRef.connected_account_id == connected_account_id)
    row = (await db.execute(query.limit(1))).scalar_one_or_none()
    return row.external_id if row else None


async def find_entity_by_external(
    db: AsyncSession,
    *,
    workspace_id: str,
    provider: str,
    external_id: str,
    connected_account_id: Optional[str] = None,
) -> Optional[EntityRegistry]:
    query = (
        select(EntityRegistry)
        .join(ExternalEntityRef, ExternalEntityRef.entity_id == EntityRegistry.id)
        .where(
            EntityRegistry.workspace_id == workspace_id,
            ExternalEntityRef.provider == provider,
            ExternalEntityRef.external_id == external_id,
            ExternalEntityRef.valid_to.is_(None),
        )
    )
    if connected_account_id:
        query = query.where(ExternalEntityRef.connected_account_id == connected_account_id)
    return (await db.execute(query.limit(1))).scalar_one_or_none()


async def register_relation(
    db: AsyncSession,
    *,
    parent_entity_id: str,
    child_entity_id: str,
    relation_type: str = "HAS_CHILD",
) -> EntityRelation:
    existing = (
        await db.execute(
            select(EntityRelation).where(
                EntityRelation.parent_entity_id == parent_entity_id,
                EntityRelation.child_entity_id == child_entity_id,
                EntityRelation.relation_type == relation_type,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = EntityRelation(
        parent_entity_id=parent_entity_id,
        child_entity_id=child_entity_id,
        relation_type=relation_type,
        valid_from=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row


async def children_of(db: AsyncSession, entity_id: str, relation_type: Optional[str] = None) -> List[EntityRegistry]:
    query = (
        select(EntityRegistry)
        .join(EntityRelation, EntityRelation.child_entity_id == EntityRegistry.id)
        .where(EntityRelation.parent_entity_id == entity_id)
    )
    if relation_type:
        query = query.where(EntityRelation.relation_type == relation_type)
    return list((await db.execute(query)).scalars().all())


def entity_dict(entity: EntityRegistry) -> Dict[str, Any]:
    return {
        "id": str(entity.id),
        "workspace_id": entity.workspace_id,
        "brand_id": entity.brand_id,
        "entity_type": entity.entity_type,
        "display_name": entity.display_name,
        "status": entity.status,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
    }
