from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class RuleContext:
    evaluation_time: datetime
    source_timezone: str = "America/New_York"
    platform: Optional[str] = None
    account_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    campaign_id: Optional[str] = None
    ad_group_id: Optional[str] = None
    ad_id: Optional[str] = None
    creative_id: Optional[str] = None
    objective: Optional[str] = None
    product_id: Optional[str] = None
    market: Optional[str] = None
    currency: Optional[str] = "USD"
    business_targets: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    windows: Dict[str, Any] = field(default_factory=dict)
    data_freshness_minutes: Optional[int] = None
    sample_size: Dict[str, Any] = field(default_factory=dict)
    current_platform_status: Optional[str] = None
    recent_changes: List[Dict[str, Any]] = field(default_factory=list)
    active_experiments: List[Dict[str, Any]] = field(default_factory=list)
    entity_age_hours: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def metric(self, name: str) -> Any:
        return self.metrics.get(name)
