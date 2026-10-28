from typing import Any, Optional

from pydantic import BaseModel


class Evidence(BaseModel):
    metric: Optional[str] = None
    value: Optional[Any] = None
    baseline: Optional[Any] = None
    window: Optional[str] = None
    source_ref: str
    explanation: Optional[str] = None


class ToolResultRef(BaseModel):
    tool: str
    output_ref: str
    summary: Optional[str] = None
