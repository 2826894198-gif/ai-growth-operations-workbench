"""GoogleAdsExecutionProvider — v25 write adapter (PART 06 §66-§84)."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.execution.errors import ExecutionError, ExecutionErrorCode
from app.execution.providers.base import OperationResult
from app.execution.providers.google_ads.budget import change_budget, get_budget_state
from app.execution.providers.google_ads.campaign import change_campaign_status, get_campaign_state
from app.execution.providers.google_ads.client import GoogleWriteClient
from app.execution.providers.google_ads.compensation import build_google_compensation
from app.execution.providers.google_ads.negative_keyword import (
    add_negative_keyword,
    remove_system_negative_keyword,
)
from app.execution.providers.google_ads.validate import provider_validate
from app.execution.providers.google_ads.verifier import verify_state


class GoogleAdsExecutionProvider:
    provider = "GOOGLE_ADS"

    def __init__(self, client: Optional[GoogleWriteClient] = None):
        self._client = client or GoogleWriteClient()

    async def get_current_state(self, intent) -> Dict[str, Any]:
        action = intent.action_type.upper()
        if "BUDGET" in action:
            budget_resource = (intent.requested_change or {}).get("budget_resource")
            state = await get_budget_state(self._client, budget_resource)
            state["entity_id"] = intent.entity_id
            return state
        if "NEGATIVE_KEYWORD" in action:
            campaign = await get_campaign_state(self._client, intent.entity_id)
            return {
                **campaign,
                "entity_id": intent.entity_id,
                "negative_keywords": [],
            }
        campaign = await get_campaign_state(self._client, intent.entity_id)
        return {**campaign, "entity_id": intent.entity_id}

    async def validate_operation(self, intent, current_state: Dict[str, Any]) -> Dict[str, Any]:
        if "CHANGE_BUDGET" in intent.action_type and current_state.get("explicitly_shared"):
            if not (intent.requested_change or {}).get("shared_budget_explicitly_approved"):
                return {
                    "ok": False,
                    "code": "SHARED_BUDGET_SCOPE_UNAPPROVED",
                    "message": f"shared budget affects {current_state.get('reference_count', 'multiple')} campaigns; explicit approval required",
                }
        if "ADD_NEGATIVE_KEYWORD" in intent.action_type:
            campaign_type = current_state.get("advertising_channel_type") or (intent.requested_change or {}).get("campaign_type")
            try:
                from app.execution.providers.google_ads.negative_keyword import (
                    validate_negative_keyword_capability,
                )

                validate_negative_keyword_capability(
                    campaign_type,
                    (intent.requested_change or {}).get("match_type", "EXACT"),
                    (intent.requested_change or {}).get("scope", "CAMPAIGN"),
                )
            except ExecutionError as exc:
                return {"ok": False, "code": exc.code, "message": exc.message}
        return await provider_validate(self._client, intent, current_state)

    async def execute(self, intent, current_state: Dict[str, Any]) -> OperationResult:
        requested = intent.requested_change or {}
        request_id = f"google_{uuid4().hex[:12]}"
        action = intent.action_type.upper()
        try:
            if "BUDGET" in action:
                budget_resource = requested.get("budget_resource") or current_state.get("budget_resource")
                if not budget_resource:
                    raise ExecutionError(ExecutionErrorCode.PRECONDITION_FAILED.value, "budget resource missing")
                response = await change_budget(self._client, budget_resource, Decimal(str(requested["proposed_budget"])), validate_only=False)
                after = await get_budget_state(self._client, budget_resource)
                return OperationResult(
                    provider=self.provider,
                    operation_type=action,
                    provider_request_id=request_id,
                    provider_resource=budget_resource,
                    before_state=current_state,
                    requested_state=requested,
                    provider_response=response,
                    after_state=after,
                    status="SUCCESS",
                    executed_at=datetime.now(timezone.utc).isoformat(),
                )
            if "PAUSE" in action or "ENABLE" in action:
                response = await change_campaign_status(
                    self._client, intent.entity_id, requested.get("proposed_status", "PAUSED"), validate_only=False
                )
                after = await get_campaign_state(self._client, intent.entity_id)
                return OperationResult(
                    provider=self.provider,
                    operation_type=action,
                    provider_request_id=request_id,
                    provider_resource=response.get("resource_name"),
                    before_state=current_state,
                    requested_state=requested,
                    provider_response=response,
                    after_state=after,
                    status="SUCCESS",
                    executed_at=datetime.now(timezone.utc).isoformat(),
                )
            if "ADD_NEGATIVE_KEYWORD" in action:
                response = await add_negative_keyword(
                    self._client,
                    keyword_text=requested.get("keyword_text", ""),
                    match_type=requested.get("match_type", "EXACT"),
                    scope=requested.get("scope", "CAMPAIGN"),
                    target_resource=requested.get("target_resource", ""),
                    campaign_id=intent.entity_id,
                    campaign_type=current_state.get("advertising_channel_type") or requested.get("campaign_type", "SEARCH"),
                    validate_only=False,
                )
                requested["created_resource_name"] = response.get("resource_name")
                return OperationResult(
                    provider=self.provider,
                    operation_type=action,
                    provider_request_id=request_id,
                    provider_resource=response.get("resource_name"),
                    before_state=current_state,
                    requested_state=requested,
                    provider_response=response,
                    status="SUCCESS",
                    executed_at=datetime.now(timezone.utc).isoformat(),
                )
            if "REMOVE_SYSTEM_NEGATIVE_KEYWORD" in action:
                response = await remove_system_negative_keyword(
                    self._client, requested.get("provider_resource_name", ""), validate_only=False
                )
                return OperationResult(
                    provider=self.provider,
                    operation_type=action,
                    provider_request_id=request_id,
                    provider_resource=requested.get("provider_resource_name"),
                    before_state=current_state,
                    requested_state=requested,
                    provider_response=response,
                    status="SUCCESS",
                    executed_at=datetime.now(timezone.utc).isoformat(),
                )
            raise ExecutionError(ExecutionErrorCode.ACTION_NOT_ALLOWED.value, f"unsupported Google action {action}")
        except ExecutionError as exc:
            return OperationResult(
                provider=self.provider,
                operation_type=action,
                provider_request_id=request_id,
                provider_resource=intent.entity_id,
                before_state=current_state,
                requested_state=requested,
                status="UNKNOWN" if exc.code == ExecutionErrorCode.PROVIDER_TIMEOUT.value else "FAILED",
                error_code=exc.code,
                error_message=exc.message,
                provider_error_code=exc.provider_error_code,
                executed_at=datetime.now(timezone.utc).isoformat(),
            )

    async def verify(self, intent, current_state: Dict[str, Any], requested_state: Dict[str, Any]) -> Dict[str, Any]:
        return await verify_state(self._client, intent, requested_state)

    async def build_compensation(self, intent, before_state: Dict[str, Any], after_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        return build_google_compensation(intent, before_state, after_state)

    def resolve_lock_resources(self, intent, current_state: Dict[str, Any]) -> List[str]:
        if "BUDGET" in intent.action_type:
            budget_resource = (intent.requested_change or {}).get("budget_resource") or current_state.get("budget_resource")
            return [f"budget:{budget_resource or intent.entity_id}"]
        if "NEGATIVE_KEYWORD" in intent.action_type:
            return [intent.entity_id, "negative_keyword_store"]
        return [intent.entity_id]
