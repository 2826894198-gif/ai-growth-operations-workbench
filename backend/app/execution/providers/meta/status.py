"""Meta typed status actions (PART 06 §59-§61, Q)."""

from typing import Dict

from app.execution.errors import ExecutionError, ExecutionErrorCode
from app.execution.providers.meta.client import MetaWriteClient


async def change_status(client: MetaWriteClient, entity_id: str, entity_type: str, proposed_status: str) -> Dict:
    if entity_type.upper() not in ("CAMPAIGN", "AD_SET", "AD"):
        raise ExecutionError(
            ExecutionErrorCode.ACTION_NOT_ALLOWED.value,
            f"Meta status changes support CAMPAIGN/AD_SET/AD only, got {entity_type}",
        )
    meta_status = "ACTIVE" if proposed_status.upper() in ("ENABLED", "ACTIVE") else "PAUSED"
    return await client.update_status(entity_id, meta_status)
