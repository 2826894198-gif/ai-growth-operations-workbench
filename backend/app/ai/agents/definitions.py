from app.ai.agents.base import AgentDefinition
from app.ai.schemas.competitor import CompetitorIntelligenceResult
from app.ai.schemas.creative import CreativeAnalysisOutput
from app.ai.schemas.funnel import FunnelDiagnosis
from app.ai.schemas.performance import PerformanceDiagnosis
from app.ai.schemas.review import ReviewResult
from app.ai.schemas.search import SearchIntelligenceResult
from app.ai.schemas.strategy import GrowthStrategy

performance_agent = AgentDefinition("performance", "performance", PerformanceDiagnosis, "performance_diagnosis", risk_level="MEDIUM")
funnel_agent = AgentDefinition("funnel", "funnel", FunnelDiagnosis, "funnel_diagnosis", risk_level="MEDIUM")
search_agent = AgentDefinition("search", "search", SearchIntelligenceResult, "search_term_classification", risk_level="MEDIUM")
creative_agent = AgentDefinition("creative", "creative", CreativeAnalysisOutput, "creative_video_analysis", risk_level="LOW")
competitor_agent = AgentDefinition("competitor", "competitor", CompetitorIntelligenceResult, "competitor_summary", risk_level="LOW")
strategy_agent = AgentDefinition("strategy", "strategy", GrowthStrategy, "strategy_synthesis", risk_level="HIGH")
reviewer_agent = AgentDefinition("reviewer", "reviewer", ReviewResult, "reviewer", risk_level="MEDIUM")

SPECIALISTS = {
    "performance": performance_agent,
    "funnel": funnel_agent,
    "search": search_agent,
    "creative": creative_agent,
    "competitor": competitor_agent,
}
