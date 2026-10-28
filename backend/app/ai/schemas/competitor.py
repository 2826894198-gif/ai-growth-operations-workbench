from typing import List, Optional

from pydantic import BaseModel, Field


class CompetitorObservation(BaseModel):
    source_url: str
    capture_at: Optional[str] = None
    profile_id: Optional[str] = None
    content_hash: Optional[str] = None
    observation: str
    claim_type: str = "HYPOTHESIS"
    evidence_refs: List[str] = Field(default_factory=list)


class CompetitorIntelligenceResult(BaseModel):
    observations: List[CompetitorObservation] = Field(default_factory=list)
    themes: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    confidence: float = 0.0
