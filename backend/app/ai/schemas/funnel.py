from typing import List, Optional

from pydantic import BaseModel, Field

from app.ai.schemas.common import Evidence


class FunnelDiagnosis(BaseModel):
    stage_of_failure: Optional[str] = None
    severity: str = "LOW"
    likely_causes: List[str] = Field(default_factory=list)
    supporting_evidence: List[Evidence] = Field(default_factory=list)
    counter_evidence: List[str] = Field(default_factory=list)
    technical_checks: List[str] = Field(default_factory=list)
    business_checks: List[str] = Field(default_factory=list)
    confidence: float = 0.0
