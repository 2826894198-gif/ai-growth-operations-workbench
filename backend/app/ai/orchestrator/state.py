from typing import Any, Dict, List, Optional, TypedDict


class GrowthAgentState(TypedDict, total=False):
    run_id: str
    thread_id: str
    task_type: str
    user_request: str
    scope: Dict[str, Any]
    as_of_time: str
    plan: Dict[str, Any]
    specialist_outputs: Dict[str, Any]
    strategy_output: Dict[str, Any]
    review_output: Dict[str, Any]
    revision_count: int
    status: str
    errors: List[str]
    tool_calls: int
    token_usage: Dict[str, int]
    cost_usage: float
    pending_approval: Optional[Dict[str, Any]]
    decision: Optional[str]
