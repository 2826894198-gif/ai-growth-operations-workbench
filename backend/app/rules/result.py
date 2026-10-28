from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

RESULT_TRIGGERED = "TRIGGERED"
RESULT_NOT_TRIGGERED = "NOT_TRIGGERED"
RESULT_NO_DECISION = "NO_DECISION"
RESULT_SUPPRESSED = "SUPPRESSED"
RESULT_CONFLICTED = "CONFLICTED"
RESULT_ERROR = "ERROR"


@dataclass
class EvaluationResult:
    rule_key: str
    rule_version: int
    entity_type: str
    entity_id: str
    platform: Optional[str] = None
    result: str = RESULT_NOT_TRIGGERED
    action: Optional[str] = None
    reason_group: Optional[str] = None
    severity: str = "MEDIUM"
    confidence: float = 0.0
    confidence_components: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)
    suppressed_reasons: List[str] = field(default_factory=list)
    feature_snapshot: Dict[str, Any] = field(default_factory=dict)
    guards: Dict[str, Any] = field(default_factory=dict)
    suggested_change_pct: Optional[float] = None
    current_budget: Optional[float] = None
    proposed_budget: Optional[float] = None
