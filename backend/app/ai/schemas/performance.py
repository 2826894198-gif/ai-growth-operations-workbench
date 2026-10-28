from typing import List

from pydantic import BaseModel, Field

from app.ai.schemas.common import Evidence


class PerformanceDiagnosis(BaseModel):
    entity: str
    status: str
    primary_driver: str
    secondary_drivers: List[str] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    tracking_risk: bool = False
    data_limitations: List[str] = Field(default_factory=list)
    recommended_investigations: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    source_metric_ids: List[str] = Field(default_factory=list)
