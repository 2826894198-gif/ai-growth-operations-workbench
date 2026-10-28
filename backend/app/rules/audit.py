from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rules import RuleAuditLog


async def audit(
    db: AsyncSession,
    *,
    actor: str,
    action: str,
    target: str,
    before=None,
    after=None,
    request_id=None,
) -> None:
    db.add(
        RuleAuditLog(
            actor=actor,
            action=action,
            target=target,
            before=before,
            after=after,
            request_id=request_id,
        )
    )
