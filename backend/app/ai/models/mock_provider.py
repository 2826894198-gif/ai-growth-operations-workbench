import time
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from app.ai.models.base import ModelCallResult
from app.ai.schemas.creative import CreativeAnalysisOutput, CreativeDNA
from app.ai.schemas.funnel import FunnelDiagnosis
from app.ai.schemas.performance import PerformanceDiagnosis
from app.ai.schemas.review import ReviewResult
from app.ai.schemas.search import SearchIntelligenceResult
from app.ai.schemas.strategy import GrowthStrategy, Priority
from app.ai.schemas.supervisor import SupervisorPlan


class MockModelProvider:
    """Deterministic mock provider so the whole AI layer runs without keys."""

    name = "mock"

    def __init__(self, scenario: str = "healthy"):
        self.scenario = scenario

    async def generate_structured(
        self,
        system_prompt: str,
        task_prompt: str,
        output_model: Type[BaseModel],
        *,
        seed: Optional[Dict[str, Any]] = None,
        modality: str = "text",
    ) -> ModelCallResult:
        started = time.monotonic()
        payload = self._build(output_model, seed or {})
        return ModelCallResult(
            content=payload.model_dump_json(),
            structured=payload.model_dump(),
            provider="mock",
            model="mock-model",
            input_tokens=100,
            output_tokens=200,
            estimated_cost=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def generate_text(self, system_prompt: str, task_prompt: str) -> ModelCallResult:
        return ModelCallResult(content="Mock summary: deterministic text output.", provider="mock", model="mock-model")

    async def analyze_multimodal(
        self, system_prompt: str, media_refs: List[str], output_model: Type[BaseModel]
    ) -> ModelCallResult:
        return await self.generate_structured(system_prompt, str(media_refs), output_model, seed={"analysis_mode": "FRAME_SAMPLE"})

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * 8 for _ in texts]

    def _build(self, model: Type[BaseModel], seed: Dict[str, Any]) -> BaseModel:
        name = model.__name__
        if name == "SupervisorPlan":
            return SupervisorPlan(
                task_type=seed.get("task_type", "DAILY_GROWTH_REVIEW"),
                scope=seed.get("scope", {"platforms": ["META", "GOOGLE"], "date_window": "7d"}),
                agents=seed.get("agents", ["performance", "strategy", "reviewer"]),
                priority_questions=seed.get("priority_questions", ["Why did blended ROAS change?"]),
                approval_expected=False,
            )
        if name == "PerformanceDiagnosis":
            return PerformanceDiagnosis(
                entity=seed.get("entity", "campaign"),
                status="DEGRADED",
                primary_driver=seed.get("primary_driver", "funnel/checkout"),
                secondary_drivers=["creative fatigue possible"],
                evidence=seed.get("evidence", []),
                contradictions=[],
                tracking_risk=seed.get("tracking_risk", False),
                data_limitations=["sample small for some entities"],
                recommended_investigations=["Check checkout-to-purchase conversion"],
                confidence=0.7,
                source_metric_ids=seed.get("source_metric_ids", []),
            )
        if name == "FunnelDiagnosis":
            return FunnelDiagnosis(
                stage_of_failure=seed.get("stage_of_failure", "CHECKOUT_TO_PURCHASE"),
                severity=seed.get("severity", "MEDIUM"),
                likely_causes=["Payment friction", "Shipping surprise"],
                supporting_evidence=seed.get("evidence", []),
                technical_checks=["Checkout API errors", "Payment provider status"],
                business_checks=["Shipping cost policy", "Tax calculation"],
                confidence=0.65,
            )
        if name == "SearchIntelligenceResult":
            return SearchIntelligenceResult(
                query_clusters=seed.get("query_clusters", []),
                waste_candidates=seed.get("waste_candidates", []),
                expansion_candidates=seed.get("expansion_candidates", []),
                intent_shifts=seed.get("intent_shifts", []),
                brand_conflicts=[],
                recommendations=seed.get("recommendations", []),
                limitations=["Semantic classification is mock; performance evidence preserved"],
            )
        if name == "CreativeAnalysisOutput":
            return CreativeAnalysisOutput(
                creative_id=seed.get("creative_id", "creative-1"),
                analysis_mode=seed.get("analysis_mode", "FRAME_SAMPLE"),
                dna=CreativeDNA(
                    hook_type="tactile_product_demo",
                    hook_description="Close-up cassette loading with audible click",
                    product_appearance_second=1.2,
                    scene_types=["BEDROOM_NOSTALGIA", "DESK_SETUP"],
                    hand_present=True,
                    emotion="nostalgic",
                    nostalgia_signal=True,
                    cta_type="SHOP_NOW",
                    confidence=0.6,
                    taxonomy_labels=["CASSETTE_INSERT", "LID_CLOSE", "PLAY_BUTTON", "BEDROOM_NOSTALGIA"],
                ),
                source_asset_hash=seed.get("source_asset_hash"),
                blind=seed.get("blind", False),
            )
        if name == "GrowthStrategy":
            priorities = [
                Priority(
                    priority=1,
                    impact="HIGH",
                    urgency="HIGH",
                    confidence=0.7,
                    effort="MEDIUM",
                    risk="MEDIUM",
                    evidence_refs=seed.get("evidence_refs", []),
                    rule_refs=seed.get("rule_refs", []),
                    review_required=True,
                )
            ]
            return GrowthStrategy(
                executive_summary="Mock strategy: prioritize checkout investigation before creative changes.",
                top_priorities=priorities,
                actions_now=seed.get("actions_now", ["Investigate checkout-to-purchase drop"]),
                experiments_next=[],
                creative_requests=[],
                investigations=["Checkout funnel instrumentation"],
                do_not_change=["Do not pause creative without rule evidence"],
                risks=["Attribution delay may distort short-window conclusions"],
                expected_signal_to_watch=["checkout_to_purchase_7d"],
                confidence=0.65,
            )
        if name == "ReviewResult":
            force_fail = seed.get("force_review_fail", False)
            return ReviewResult(
                passed=not force_fail,
                numeric_errors=seed.get("numeric_errors", []),
                unsupported_claims=seed.get("unsupported_claims", []),
                missing_evidence=seed.get("missing_evidence", []),
                rule_conflicts=seed.get("rule_conflicts", []),
                permission_issues=seed.get("permission_issues", []),
                risk_issues=seed.get("risk_issues", []),
                required_revisions=seed.get("required_revisions", []),
                review_confidence=0.9,
            )
        # Generic fallback: fill required fields from seed or defaults.
        return model(**seed)
