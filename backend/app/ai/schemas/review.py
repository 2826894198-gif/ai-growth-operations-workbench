from typing import List

from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    passed: bool
    numeric_errors: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    rule_conflicts: List[str] = Field(default_factory=list)
    permission_issues: List[str] = Field(default_factory=list)
    risk_issues: List[str] = Field(default_factory=list)
    required_revisions: List[str] = Field(default_factory=list)
    review_confidence: float = 0.0
