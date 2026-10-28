from typing import List, Optional

from pydantic import BaseModel, Field


class QueryCluster(BaseModel):
    cluster_name: str
    query_count: int = 0
    spend: Optional[float] = None
    conversions: Optional[float] = None
    semantic_class: str = "UNKNOWN"
    commercial_relevance: str = "UNKNOWN"


class WasteCandidate(BaseModel):
    term: str
    semantic_class: str
    commercial_relevance: str
    negative_candidate_confidence: float = 0.0
    reason: str
    spend: Optional[float] = None
    clicks: Optional[float] = None
    conversions: Optional[float] = None


class ExpansionCandidate(BaseModel):
    term: str
    reason: str
    evidence_refs: List[str] = Field(default_factory=list)


class SearchIntelligenceResult(BaseModel):
    query_clusters: List[QueryCluster] = Field(default_factory=list)
    waste_candidates: List[WasteCandidate] = Field(default_factory=list)
    expansion_candidates: List[ExpansionCandidate] = Field(default_factory=list)
    intent_shifts: List[str] = Field(default_factory=list)
    brand_conflicts: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
