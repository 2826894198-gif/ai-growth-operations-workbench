from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.metrics_service import MetricsService

INTENT_RULES = [
    ("weekly", "WEEKLY_GROWTH_REVIEW"),
    ("周报", "WEEKLY_GROWTH_REVIEW"),
    ("daily", "DAILY_GROWTH_REVIEW"),
    ("日报", "DAILY_GROWTH_REVIEW"),
    ("strategy", "STRATEGY_REQUEST"),
    ("策略", "STRATEGY_REQUEST"),
    ("experiment", "EXPERIMENT_REQUEST"),
    ("实验", "EXPERIMENT_REQUEST"),
    ("creative", "CREATIVE_QA"),
    ("素材", "CREATIVE_QA"),
    ("search term", "SEARCH_QA"),
    ("搜索词", "SEARCH_QA"),
    ("negative", "SEARCH_QA"),
    ("否词", "SEARCH_QA"),
    ("funnel", "FUNNEL_QA"),
    ("checkout", "FUNNEL_QA"),
    ("结账", "FUNNEL_QA"),
    ("competitor", "COMPETITOR_QA"),
    ("竞品", "COMPETITOR_QA"),
    ("recommendation", "RECOMMENDATION_EXPLAIN"),
    ("推荐", "RECOMMENDATION_EXPLAIN"),
    ("roas", "PERFORMANCE_QA"),
    ("cpa", "PERFORMANCE_QA"),
    ("spend", "PERFORMANCE_QA"),
    ("花费", "PERFORMANCE_QA"),
    ("表现", "PERFORMANCE_QA"),
]


def classify_intent(query: str) -> str:
    lowered = query.lower()
    for keyword, intent in INTENT_RULES:
        if keyword in lowered:
            return intent
    return "PERFORMANCE_QA"


async def try_direct_answer(db: AsyncSession, query: str) -> Optional[Dict[str, Any]]:
    """Deterministic query gate: simple factual questions cost 0 LLM calls."""
    lowered = query.lower()
    # Fact dates are normalized against UTC; using the host's local date here
    # makes the deterministic gate miss the just-written row around midnight
    # in non-UTC environments.
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    if "spend" in lowered or "花费" in query:
        platform = None
        if "meta" in lowered or "facebook" in lowered or "facebook" in query:
            platform = "META_ADS"
        if "google" in lowered:
            platform = "GOOGLE_ADS"
        platforms = await MetricsService().platforms(db, yesterday, yesterday)
        if platform:
            platforms = [p for p in platforms if p["platform"] == platform]
        if platforms:
            return {
                "mode": "direct",
                "answer": f"昨日 {platforms[0]['platform']} 花费 ${platforms[0]['spend']:.2f}",
                "source": "Metrics API",
                "metrics": platforms,
            }
    return None
