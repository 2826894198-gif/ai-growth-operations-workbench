"""MetaExecutionProvider — v26 Marketing API write adapter (PART 06 §55-§65)."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.execution.errors import ExecutionError, ExecutionErrorCode
from app.execution.providers.base import OperationResult
from app.execution.providers.meta.budget import (
    cents_to_decimal,
    change_budget,
    resolve_budget_owner,
)
from app.execution.providers.meta.client import MetaWriteClient
from app.execution.providers.meta.compensation import build_meta_compensation
from app.execution.providers.meta.status import change_status
from app.execution.providers.meta.verifier import verify_state


class MetaExecutionProvider:
    provider = "META"

    def __init__(self, client: Optional[MetaWriteClient] = None):
        self._client = client or MetaWriteClient()
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_current_state(self, intent) -> Dict[str, Any]:
        entity_type = (intent.entity_type or "CAMPAIGN").upper()
        if entity_type == "CAMPAIGN":
            return await self._read_campaign_state(intent.entity_id)
        data = await self._client.get_object(intent.entity_id, entity_type)
        state = {
            "entity_id": intent.entity_id,
            "external_entity_id": intent.external_entity_id,
            "status": data.get("status"),
            "effective_status": data.get("effective_status"),
        }
        if entity_type == "AD_SET":
            state["daily_budget"] = data.get("daily_budget")
            state["lifetime_budget"] = data.get("lifetime_budget")
        return state

    async def _read_campaign_state(self, campaign_id: str) -> Dict[str, Any]:
        owner = await resolve_budget_owner(self._client, campaign_id)
        state = {
            "entity_id": campaign_id,
            "status": owner.get("campaign_status"),
            "effective_status": owner.get("effective_status"),
            "budget_owner": owner.get("owner"),
            "budget_owner_entity_id": owner.get("owner_entity_id"),
            "budget": cents_to_decimal(owner.get("daily_budget_cents")) if owner.get("daily_budget_cents") is not None else None,
            "daily_budget_cents": owner.get("daily_budget_cents"),
            "lifetime_budget_cents": owner.get("lifetime_budget_cents"),
        }
        if owner.get("owner") == "MULTIPLE_AD_SETS":
            state["ad_sets"] = owner.get("ad_sets")
        if owner.get("owner") == "UNKNOWN":
            state["budget_owner"] = "UNKNOWN"
        return state

    async def validate_operation(self, intent, current_state: Dict[str, Any]) -> Dict[str, Any]:
        if current_state.get("budget_owner") in ("UNKNOWN", "MULTIPLE_AD_SETS"):
            return {
                "ok": False,
                "code": "UNSUPPORTED_PROVIDER_CONFIGURATION",
                "message": f"Meta budget owner configuration unsupported: {current_state.get('budget_owner')}; blocking (no UI fallback)",
            }
        return {"ok": True, "validate_only": False, "message": "local validation passed (Meta has no mutate validate_only)"}

    async def execute(self, intent, current_state: Dict[str, Any]) -> OperationResult:
        requested = intent.requested_change or {}
        request_id = f"meta_{uuid4().hex[:12]}"
        action = intent.action_type.upper()
        try:
            if "BUDGET" in action:
                if current_state.get("budget_owner") in ("UNKNOWN", "MULTIPLE_AD_SETS"):
                    raise ExecutionError(
                        ExecutionErrorCode.UNSUPPORTED_PROVIDER_CONFIGURATION.value,
                        f"cannot mutate budget with owner {current_state.get('budget_owner')}",
                    )
                owner_id = requested.get("budget_owner_entity_id") or current_state.get("budget_owner_entity_id")
                if not owner_id:
                    raise ExecutionError(
                        ExecutionErrorCode.PRECONDITION_FAILED.value,
                        "budget owner entity id missing",
                    )
                proposed = Decimal(str(requested["proposed_budget"]))
                response = await change_budget(self._client, owner_id, proposed, requested.get("currency", "USD"))
                after = await self.get_current_state(intent)
                return OperationResult(
                    provider=self.provider,
                    operation_type=action,
                    provider_request_id=request_id,
                    provider_resource=owner_id,
                    before_state=current_state,
                    requested_state=requested,
                    provider_response=response,
                    after_state=after,
                    status="SUCCESS",
                    executed_at=datetime.now(timezone.utc).isoformat(),
                )
            if "PAUSE" in action or "ENABLE" in action:
                entity_type = (intent.entity_type or "CAMPAIGN").upper()
                response = await change_status(self._client, intent.entity_id, entity_type, requested.get("proposed_status", "PAUSED"))
                after = await self.get_current_state(intent)
                return OperationResult(
                    provider=self.provider,
                    operation_type=action,
                    provider_request_id=request_id,
                    provider_resource=intent.entity_id,
                    before_state=current_state,
                    requested_state=requested,
                    provider_response=response,
                    after_state=after,
                    status="SUCCESS",
                    executed_at=datetime.now(timezone.utc).isoformat(),
                )
            raise ExecutionError(ExecutionErrorCode.ACTION_NOT_ALLOWED.value, f"unsupported Meta action {action}")
        except ExecutionError as exc:
            return OperationResult(
                provider=self.provider,
                operation_type=action,
                provider_request_id=request_id,
                provider_resource=intent.entity_id,
                before_state=current_state,
                requested_state=requested,
                status="FAILED" if exc.code != "PROVIDER_TIMEOUT" else "UNKNOWN",
                error_code=exc.code,
                error_message=exc.message,
                provider_error_code=exc.provider_error_code,
                executed_at=datetime.now(timezone.utc).isoformat(),
            )

    async def verify(self, intent, current_state: Dict[str, Any], requested_state: Dict[str, Any]) -> Dict[str, Any]:
        entity_type = (intent.entity_type or "CAMPAIGN").upper()
        if "BUDGET" in intent.action_type:
            requested_state = {
                **requested_state,
                "action_type": intent.action_type,
                "proposed_budget_cents": int(Decimal(str(requested_state.get("proposed_budget", 0))) * 100),
            }
        return await verify_state(self._client, intent.entity_id, entity_type, requested_state)

    async def build_compensation(self, intent, before_state: Dict[str, Any], after_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        return build_meta_compensation(intent, before_state, after_state)

    def resolve_lock_resources(self, intent, current_state: Dict[str, Any]) -> List[str]:
        if "BUDGET" in intent.action_type:
            owner = (intent.requested_change or {}).get("budget_owner_entity_id") or current_state.get("budget_owner_entity_id")
            return [f"budget:{owner or intent.entity_id}"]
        return [intent.entity_id]
