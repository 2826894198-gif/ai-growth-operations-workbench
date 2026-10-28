"""Execution provider interface (PART 06 §30-§31)."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class OperationResult:
    provider: str
    operation_type: str
    provider_request_id: str
    provider_resource: Optional[str] = None
    before_state: Optional[Dict[str, Any]] = None
    requested_state: Optional[Dict[str, Any]] = None
    provider_response: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    status: str = "SUCCESS"  # SUCCESS | FAILED | TIMEOUT | UNKNOWN
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    executed_at: Optional[str] = None
    provider_error_code: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class ExecutionProvider(Protocol):
    provider: str

    async def get_current_state(self, intent) -> Dict[str, Any]: ...

    async def validate_operation(self, intent, current_state: Dict[str, Any]) -> Dict[str, Any]: ...

    async def execute(self, intent, current_state: Dict[str, Any]) -> OperationResult: ...

    async def verify(self, intent, current_state: Dict[str, Any], requested_state: Dict[str, Any]) -> Dict[str, Any]: ...

    async def build_compensation(
        self, intent, before_state: Dict[str, Any], after_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]: ...

    def resolve_lock_resources(self, intent, current_state: Dict[str, Any]) -> List[str]: ...


def desired_state_matches(provider_state: Dict[str, Any], requested_state: Dict[str, Any], action_type: str) -> bool:
    """Compare provider read-after-write state against the requested state."""
    action = action_type.upper()
    if "BUDGET" in action:
        for key in ("budget", "daily_budget", "amount_micros", "amount"):
            if key in provider_state and key in requested_state:
                try:
                    return Decimal(str(provider_state[key])) == Decimal(str(requested_state[key]))
                except (TypeError, ValueError):
                    continue
        if provider_state.get("amount_micros") is not None and requested_state.get("proposed_budget") is not None:
            try:
                return Decimal(str(provider_state["amount_micros"])) / Decimal("1000000") == Decimal(
                    str(requested_state["proposed_budget"])
                )
            except (TypeError, ValueError):
                return False
        try:
            current = provider_state.get("budget") if provider_state.get("budget") is not None else provider_state.get("daily_budget")
            return Decimal(str(current)) == Decimal(str(requested_state.get("proposed_budget")))
        except (TypeError, ValueError):
            return False
    if "PAUSE" in action:
        return str(provider_state.get("status", "")).upper() in ("PAUSED", "INACTIVE")
    if "ENABLE" in action:
        return str(provider_state.get("status", "")).upper() in ("ENABLED", "ACTIVE")
    if "REMOVE_SYSTEM_NEGATIVE_KEYWORD" in action:
        resource_name = requested_state.get("provider_resource_name")
        return provider_state.get("removed_resource") == resource_name or not provider_state.get("negative_keyword_exists", True)
    if "NEGATIVE_KEYWORD" in action:
        return bool(provider_state.get("negative_keyword_created")) or bool(provider_state.get("resource_name"))
    return False
