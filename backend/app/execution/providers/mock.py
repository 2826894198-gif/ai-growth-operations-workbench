"""MockExecutionProvider — full lifecycle sandbox (PART 06 §AC, §187).

Simulates Meta/Google resources, budget ownership, shared budgets, statuses,
negative keywords, timeouts, unknown outcomes and verification failures.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.execution.providers.base import OperationResult, desired_state_matches

logger = logging.getLogger(__name__)


class MockExecutionProvider:
    """In-memory advertising provider sandbox."""

    provider = "MOCK"

    def __init__(self, store: Optional[Dict[str, Any]] = None):
        self.store = store if store is not None else self._default_store()
        self._lock = asyncio.Lock()

    @staticmethod
    def _default_store() -> Dict[str, Any]:
        return {
            "meta_campaigns": {
                "camp_1001": {"status": "ACTIVE", "effective_status": "ACTIVE", "budget_owner": "CAMPAIGN", "budget": 100},
                "camp_1002": {"status": "ACTIVE", "effective_status": "ACTIVE", "budget_owner": "AD_SET", "adset_budget": 80},
            },
            "meta_adsets": {"adset_2001": {"campaign_id": "camp_1002", "status": "ACTIVE", "effective_status": "ACTIVE", "daily_budget": 80}},
            "meta_ads": {"ad_3001": {"campaign_id": "camp_1001", "adset_id": "adset_2001", "status": "ACTIVE", "effective_status": "ACTIVE"}},
            "google_campaigns": {
                "camp_g1001": {"status": "ENABLED", "budget_resource": "customers/1/campaignBudgets/5001", "budget": 100},
                "camp_g1002": {"status": "PAUSED", "budget_resource": "customers/1/campaignBudgets/5002", "budget": 60},
                "camp_g1003": {"status": "ENABLED", "budget_resource": "customers/1/campaignBudgets/5003", "budget": 50},
            },
            "google_budgets": {
                "customers/1/campaignBudgets/5001": {
                    "amount_micros": 100_000_000,
                    "explicitly_shared": False,
                    "campaigns": ["camp_g1001"],
                },
                "customers/1/campaignBudgets/5002": {
                    "amount_micros": 60_000_000,
                    "explicitly_shared": True,
                    "campaigns": ["camp_g1002", "camp_g1003"],
                },
                "customers/1/campaignBudgets/5003": {"amount_micros": 50_000_000, "explicitly_shared": False, "campaigns": ["camp_g1003"]},
            },
            "google_negatives": {},
            "meta_negatives": {},
        }

    async def _resource(self, intent) -> Dict[str, Any]:
        provider = (intent.provider or "").upper()
        entity_type = (intent.entity_type or "").upper()
        entity_id = intent.entity_id
        async with self._lock:
            if provider == "META":
                if entity_type in ("CAMPAIGN",):
                    return self.store["meta_campaigns"].get(entity_id) or {}
                if entity_type in ("AD_SET",):
                    return self.store["meta_adsets"].get(entity_id) or {}
                if entity_type == "AD":
                    return self.store["meta_ads"].get(entity_id) or {}
            if provider == "GOOGLE_ADS":
                if entity_type in ("CAMPAIGN",):
                    return self.store["google_campaigns"].get(entity_id) or {}
                if entity_type in ("BUDGET",):
                    return self.store["google_budgets"].get(entity_id) or {}
        return {}

    def _entity_id_for_budget(self, intent, current_state: Dict[str, Any]) -> str:
        requested = intent.requested_change or {}
        owner = requested.get("budget_owner") or current_state.get("budget_owner")
        if owner == "AD_SET" or current_state.get("adset_budget") is not None:
            return current_state.get("budget_owner_entity_id") or "adset_2001"
        return intent.entity_id

    async def get_current_state(self, intent) -> Dict[str, Any]:
        await asyncio.sleep(0)
        state = dict(await self._resource(intent))
        state["entity_id"] = intent.entity_id
        state["external_entity_id"] = intent.external_entity_id
        if (intent.provider or "").upper() == "META" and (intent.entity_type or "").upper() == "CAMPAIGN":
            state["budget_owner"] = state.get("budget_owner", "CAMPAIGN")
            state["budget_owner_entity_id"] = intent.entity_id if state.get("budget_owner") == "CAMPAIGN" else state.get("adset_budget_entity_id", "adset_2001")
            if state.get("budget_owner") == "AD_SET":
                adset = self.store["meta_adsets"].get(state["budget_owner_entity_id"], {})
                state["budget"] = adset.get("daily_budget")
                state["daily_budget"] = adset.get("daily_budget")
            else:
                state["budget"] = state.get("budget")
                state["daily_budget"] = state.get("budget")
        if (intent.provider or "").upper() == "GOOGLE_ADS" and (intent.entity_type or "").upper() == "CAMPAIGN":
            budget_resource = state.get("budget_resource")
            budget = self.store["google_budgets"].get(budget_resource, {})
            state["amount_micros"] = budget.get("amount_micros")
            state["explicitly_shared"] = budget.get("explicitly_shared", False)
            state["reference_count"] = len(budget.get("campaigns", []))
            state["budget_resource"] = budget_resource
        return state

    async def validate_operation(self, intent, current_state: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(0)
        if (intent.requested_change or {}).get("simulate_validate_fail"):
            return {"ok": False, "code": "PROVIDER_VALIDATE_FAILED", "message": "mock validation rejected operation"}
        if "ADD_NEGATIVE_KEYWORD" in (intent.action_type or "").upper():
            scope = (intent.requested_change or {}).get("scope", "").upper()
            if scope not in ("AD_GROUP", "CAMPAIGN", "SHARED_SET", "ACCOUNT", "PMAX_CAMPAIGN"):
                return {"ok": False, "code": "ACTION_NOT_ALLOWED", "message": f"invalid negative keyword scope: {scope}"}
        return {"ok": True, "validate_only": True, "message": "mock validation passed"}

    async def execute(self, intent, current_state: Dict[str, Any]) -> OperationResult:
        await asyncio.sleep(0)
        requested = intent.requested_change or {}
        request_id = f"mock_req_{uuid4().hex[:10]}"
        provider = (intent.provider or "").upper()
        action = intent.action_type.upper()

        if requested.get("simulate_timeout_after_mutation"):
            # Apply the mutation, then report a timeout so the engine must
            # re-read state to resolve the outcome (PART 06 §S).
            async with self._lock:
                if "BUDGET" in action and provider == "META":
                    self.store["meta_campaigns"][intent.entity_id]["budget"] = float(requested["proposed_budget"])
                elif "BUDGET" in action:
                    budget_resource = requested.get("budget_resource") or current_state.get("budget_resource")
                    self.store["google_budgets"][budget_resource]["amount_micros"] = int(
                        Decimal(str(requested["proposed_budget"])) * Decimal("1000000")
                    )
            raise TimeoutError("mock provider timeout after successful mutation")

        if requested.get("simulate_timeout"):
            raise TimeoutError("mock provider timeout after request transmission")
        if requested.get("simulate_unknown"):
            return OperationResult(
                provider=self.provider,
                operation_type=action,
                provider_request_id=request_id,
                provider_resource=intent.entity_id,
                before_state=current_state,
                requested_state=requested,
                status="UNKNOWN",
                error_code="PROVIDER_OUTCOME_UNKNOWN",
                error_message="mock: request sent, outcome unknown",
                executed_at=datetime.now(timezone.utc).isoformat(),
            )

        async with self._lock:
            if "BUDGET" in action:
                if provider == "META":
                    resource = self._entity_id_for_budget(intent, current_state)
                    if resource == intent.entity_id:
                        self.store["meta_campaigns"][intent.entity_id]["budget"] = float(requested["proposed_budget"])
                    else:
                        self.store["meta_adsets"][resource]["daily_budget"] = float(requested["proposed_budget"])
                else:
                    budget_resource = requested.get("budget_resource") or current_state.get("budget_resource")
                    if budget_resource not in self.store["google_budgets"]:
                        return OperationResult(
                            provider=self.provider,
                            operation_type=action,
                            provider_request_id=request_id,
                            before_state=current_state,
                            requested_state=requested,
                            status="FAILED",
                            error_code="PROVIDER_MUTATION_FAILED",
                            error_message="mock budget resource not found",
                        )
                    self.store["google_budgets"][budget_resource]["amount_micros"] = int(
                        Decimal(str(requested["proposed_budget"])) * Decimal("1000000")
                    )
                    self.store["google_budgets"][budget_resource]["explicitly_shared"] = bool(requested.get("shared_budget_explicitly_approved"))
            elif "PAUSE" in action or "ENABLE" in action:
                desired = "PAUSED" if "PAUSE" in action else ("ACTIVE" if provider == "META" else "ENABLED")
                current_status = str(current_state.get("status", "")).upper()
                if "PAUSE" in action and current_status in ("PAUSED", "INACTIVE"):
                    return OperationResult(
                        provider=self.provider,
                        operation_type=action,
                        provider_request_id=request_id,
                        provider_resource=intent.entity_id,
                        before_state=current_state,
                        requested_state=requested,
                        provider_response={"noop": True, "desired_state_already_satisfied": True},
                        status="SUCCESS",
                        executed_at=datetime.now(timezone.utc).isoformat(),
                    )
                if provider == "META":
                    table = self._meta_table(intent.entity_type)
                    if table is not None:
                        table[intent.entity_id]["status"] = desired
                        table[intent.entity_id]["effective_status"] = desired
                else:
                    self.store["google_campaigns"][intent.entity_id]["status"] = desired
            elif "ADD_NEGATIVE_KEYWORD" in action:
                if provider == "GOOGLE_ADS":
                    key = (intent.entity_id, requested["keyword_text"], requested["match_type"])
                    if key in self.store["google_negatives"]:
                        return OperationResult(
                            provider=self.provider,
                            operation_type=action,
                            provider_request_id=request_id,
                            provider_resource=self.store["google_negatives"][key]["resource_name"],
                            before_state=current_state,
                            requested_state=requested,
                            provider_response={"noop": True, "already_excluded": True},
                            status="SUCCESS",
                            executed_at=datetime.now(timezone.utc).isoformat(),
                        )
                    resource_name = f"customers/1/{requested.get('scope', 'CAMPAIGN').lower()}Criterion/{uuid4().hex[:10]}"
                    self.store["google_negatives"][key] = {
                        "resource_name": resource_name,
                        "keyword_text": requested["keyword_text"],
                        "match_type": requested["match_type"],
                        "scope": requested["scope"],
                        "negative": True,
                        "created_by": "SYSTEM_EXECUTION",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    requested["created_resource_name"] = resource_name
                else:
                    self.store["meta_negatives"][intent.entity_id] = {
                        "keyword_text": requested["keyword_text"],
                        "match_type": requested["match_type"],
                        "created_by": "SYSTEM_EXECUTION",
                    }
            elif "REMOVE_SYSTEM_NEGATIVE_KEYWORD" in action:
                resource_name = requested.get("provider_resource_name")
                removed = [
                    key
                    for key, value in self.store["google_negatives"].items()
                    if value.get("resource_name") == resource_name and value.get("created_by") == "SYSTEM_EXECUTION"
                ]
                for key in removed:
                    del self.store["google_negatives"][key]

        after = await self.get_current_state(intent)
        if requested.get("simulate_verification_failure"):
            after["status"] = "DIFFERENT_FROM_REQUESTED"
        return OperationResult(
            provider=self.provider,
            operation_type=action,
            provider_request_id=request_id,
            provider_resource=intent.entity_id,
            before_state=current_state,
            requested_state=requested,
            provider_response={"status": "SUCCESS", "request_id": request_id},
            after_state=after,
            status="SUCCESS",
            executed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _meta_table(self, entity_type: str):
        entity_type = (entity_type or "").upper()
        if entity_type == "CAMPAIGN":
            return self.store["meta_campaigns"]
        if entity_type == "AD_SET":
            return self.store["meta_adsets"]
        if entity_type == "AD":
            return self.store["meta_ads"]
        return None

    async def verify(self, intent, current_state: Dict[str, Any], requested_state: Dict[str, Any]) -> Dict[str, Any]:
        await asyncio.sleep(0)
        if (intent.requested_change or {}).get("simulate_verification_failure"):
            return {"result": "MISMATCHED", "provider_state": {}, "matched": False, "simulated": True}
        after = await self.get_current_state(intent)
        action = (intent.action_type or "").upper()
        if "ADD_NEGATIVE_KEYWORD" in action:
            resource = (intent.requested_change or {}).get("created_resource_name")
            matched = (
                any(v.get("resource_name") == resource for v in self.store["google_negatives"].values())
                if resource
                else bool(self.store["google_negatives"])
            )
            return {"result": "MATCHED" if matched else "MISMATCHED", "provider_state": after, "matched": matched}
        if "REMOVE_SYSTEM_NEGATIVE_KEYWORD" in action:
            resource = (intent.requested_change or {}).get("provider_resource_name")
            matched = all(v.get("resource_name") != resource for v in self.store["google_negatives"].values())
            after = {**after, "removed_resource": resource, "negative_keyword_exists": not matched}
            return {"result": "MATCHED" if matched else "MISMATCHED", "provider_state": after, "matched": matched}
        matched = desired_state_matches(after, requested_state, intent.action_type)
        return {
            "result": "MATCHED" if matched else "MISMATCHED",
            "provider_state": after,
            "matched": matched,
        }

    async def build_compensation(
        self, intent, before_state: Dict[str, Any], after_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        action = intent.action_type.upper()
        requested = intent.requested_change or {}
        if "BUDGET" in action:
            return [
                {
                    "compensation_type": "RESTORE_BUDGET",
                    "target_state": {
                        "proposed_budget": str(requested.get("current_budget")),
                        "current_budget": str(requested.get("proposed_budget")),
                        "currency": requested.get("currency", "USD"),
                    },
                    "provider_resource_name": after_state.get("budget_resource") or intent.entity_id,
                    "action_type": intent.action_type,
                }
            ]
        if "PAUSE" in action:
            return [
                {
                    "compensation_type": "RE_ENABLE",
                    "target_state": {"proposed_status": "ACTIVE" if (intent.provider or "").upper() == "META" else "ENABLED"},
                    "provider_resource_name": intent.entity_id,
                    "action_type": intent.action_type.replace("PAUSE", "ENABLE"),
                }
            ]
        if "ENABLE" in action:
            return [
                {
                    "compensation_type": "RE_PAUSE",
                    "target_state": {"proposed_status": "PAUSED"},
                    "provider_resource_name": intent.entity_id,
                    "action_type": intent.action_type.replace("ENABLE", "PAUSE"),
                }
            ]
        if "ADD_NEGATIVE_KEYWORD" in action:
            resource_name = requested.get("created_resource_name") or after_state.get("resource_name")
            if not resource_name:
                return []
            return [
                {
                    "compensation_type": "REMOVE_CREATED_NEGATIVE",
                    "target_state": {
                        "provider_resource_name": resource_name,
                        "keyword_text": requested.get("keyword_text"),
                        "match_type": requested.get("match_type"),
                        "scope": requested.get("scope"),
                    },
                    "provider_resource_name": resource_name,
                    "action_type": "GOOGLE_REMOVE_SYSTEM_NEGATIVE_KEYWORD",
                }
            ]
        return []

    def resolve_lock_resources(self, intent, current_state: Dict[str, Any]) -> List[str]:
        if "BUDGET" in intent.action_type:
            if (intent.provider or "").upper() == "GOOGLE_ADS":
                budget_resource = (intent.requested_change or {}).get("budget_resource") or current_state.get("budget_resource")
                if budget_resource:
                    return [f"budget:{budget_resource}"]
            return [intent.entity_id]
        return [intent.entity_id]
