from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreativeDNA(BaseModel):
    hook_type: Optional[str] = None
    hook_description: Optional[str] = None
    opening_action: Optional[str] = None
    product_appearance_second: Optional[float] = None
    scene_types: List[str] = Field(default_factory=list)
    shot_types: List[str] = Field(default_factory=list)
    person_present: Optional[bool] = None
    hand_present: Optional[bool] = None
    emotion: Optional[str] = None
    nostalgia_signal: Optional[bool] = None
    music_role: Optional[str] = None
    audio_style: Optional[str] = None
    text_overlay_style: Optional[str] = None
    benefit_claims: List[str] = Field(default_factory=list)
    proof_elements: List[str] = Field(default_factory=list)
    cta_type: Optional[str] = None
    cta_timing: Optional[str] = None
    pacing: Optional[str] = None
    visual_density: Optional[str] = None
    story_structure: Optional[str] = None
    target_intent: Optional[str] = None
    taxonomy_labels: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class CreativeAnalysisOutput(BaseModel):
    creative_id: str
    analysis_mode: str = "FRAME_SAMPLE"
    dna: CreativeDNA = Field(default_factory=CreativeDNA)
    scene_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    hook_analysis: Dict[str, Any] = Field(default_factory=dict)
    audio_analysis: Dict[str, Any] = Field(default_factory=dict)
    source_asset_hash: Optional[str] = None
    blind: bool = False
    limitations: List[str] = Field(default_factory=list)
