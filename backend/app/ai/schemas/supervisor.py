from typing import List

from pydantic import BaseModel, Field


class SupervisorPlan(BaseModel):
    task_type: str
    scope: dict = Field(default_factory=dict)
    agents: List[str] = Field(default_factory=list)
    priority_questions: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    approval_expected: bool = False
    limitations: List[str] = Field(default_factory=list)
