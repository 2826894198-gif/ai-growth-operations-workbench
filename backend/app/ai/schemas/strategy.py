from typing import List, Optional

from pydantic import BaseModel, Field

from app.ai.schemas.common import Evidence


class Priority(BaseModel):
    priority: int = 0
    impact: str = "UNKNOWN"
    urgency: str = "UNKNOWN"
    confidence: float = 0.0
    effort: str = "UNKNOWN"
    risk: str = "LOW"
    evidence_refs: List[str] = Field(default_factory=list)
    rule_refs: List[str] = Field(default_factory=list)
    owner_type: str = "HUMAN"
    review_required: bool = True


class ExperimentProposal(BaseModel):
    hypothesis: str
    variable: str
    control: str
    treatment: str
    primary_metric: str
    guardrail_metrics: List[str] = Field(default_factory=list)
    minimum_runtime: str
    sample_requirement: str
    stop_conditions: List[str] = Field(default_factory=list)
    risk: str = "MEDIUM"
    expected_learning: str


class CreativeBrief(BaseModel):
    objective: str
    audience: str
    hook: str
    first_3_seconds: str
    scene_sequence: List[str] = Field(default_factory=list)
    product_actions: List[str] = Field(default_factory=list)
    proof: List[str] = Field(default_factory=list)
    cta: str
    audio_direction: str
    duration: str
    aspect_ratio: str
    avoid: List[str] = Field(default_factory=list)
    measurement_plan: str


class GrowthStrategy(BaseModel):
    executive_summary: str
    top_priorities: List[Priority] = Field(default_factory=list)
    actions_now: List[str] = Field(default_factory=list)
    experiments_next: List[ExperimentProposal] = Field(default_factory=list)
    creative_requests: List[CreativeBrief] = Field(default_factory=list)
    investigations: List[str] = Field(default_factory=list)
    do_not_change: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    expected_signal_to_watch: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class HumanApprovalPacket(BaseModel):
    recommendation_id: Optional[str] = None
    action_type: str
    entity: str
    current_state: dict = Field(default_factory=dict)
    proposed_change: dict = Field(default_factory=dict)
    why: str
    evidence: List[Evidence] = Field(default_factory=list)
    risk: str = "MEDIUM"
    confidence: float = 0.0
    rule_guard_status: dict = Field(default_factory=dict)
    expected_metric_to_watch: str
    rollback_plan: str
    expires_at: Optional[str] = None
