import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.marketing import Ad, AdGroup, Campaign
from app.models.rules import (
    ActiveExperiment,
    BusinessTargetProfile,
    EntityChangeEvent,
    RuleEvaluation,
    RuleEvaluationRun,
)
from app.rules.conflict.resolver import resolve_conflicts
from app.rules.context import RuleContext
from app.rules.evaluator import evaluate_rule
from app.rules.features.account import load_account_features
from app.rules.features.commerce import load_commerce_features
from app.rules.features.funnel import load_funnel_features
from app.rules.features.google import load_keyword_features, load_search_term_features
from app.rules.features.marketing import load_marketing_features
from app.rules.features.readiness import sample_reliability_score, source_freshness
from app.rules.recommendations.builder import persist_recommendations
from app.rules.recommendations.dedup import dedup_by_action_reason
from app.rules.registry import load_defaults, load_rules_from_db
from app.rules.result import RESULT_ERROR, RESULT_SUPPRESSED, RESULT_TRIGGERED, EvaluationResult

logger = logging.getLogger(__name__)


async def _discover_entities(db: AsyncSession, platform: Optional[str], evaluation_level: str) -> List[Dict[str, Any]]:
    if evaluation_level == "ACCOUNT":
        return [{"entity_type": "ACCOUNT", "entity_id": "ALL"}]
    model_map = {
        "CAMPAIGN": Campaign,
        "AD_GROUP": AdGroup,
        "AD": Ad,
    }
    if evaluation_level in model_map:
        model = model_map[evaluation_level]
        query = select(model)
        if platform:
            query = query.where(model.platform == platform)
        rows = (await db.execute(query)).scalars().all()
        out = []
        for row in rows:
            age = None
            created = row.source_created_at
            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - created).total_seconds() / 3600
            out.append(
                {
                    "entity_type": evaluation_level,
                    "entity_id": str(row.external_campaign_id if evaluation_level == "CAMPAIGN" else row.external_group_id if evaluation_level == "AD_GROUP" else row.external_ad_id),
                    "age_hours": age,
                    "campaign_id": getattr(row, "external_campaign_id", None),
                    "ad_group_id": getattr(row, "external_group_id", None),
                }
            )
        return out
    if evaluation_level == "KEYWORD":
        from app.models.ad_performance import GoogleKeywordDaily

        rows = (await db.execute(select(GoogleKeywordDaily.criterion_id).distinct())).scalars().all()
        return [{"entity_type": "KEYWORD", "entity_id": str(r)} for r in rows]
    if evaluation_level == "SEARCH_TERM":
        from app.models.ad_performance import GoogleSearchTermDaily

        rows = (await db.execute(select(GoogleSearchTermDaily.search_term).distinct())).scalars().all()
        return [{"entity_type": "SEARCH_TERM", "entity_id": str(r)} for r in rows]
    return []


async def _load_targets(db: AsyncSession, platform: Optional[str], campaign_id: Optional[str]) -> Dict[str, Any]:
    profiles = (await db.execute(select(BusinessTargetProfile))).scalars().all()
    result: Dict[str, Any] = {}
    priority = {"GLOBAL": 0, "PLATFORM": 1, "ACCOUNT": 2, "CAMPAIGN": 3}
    for profile in sorted(profiles, key=lambda p: priority.get(p.scope_type, 0)):
        if profile.scope_type == "GLOBAL":
            for key in ("target_cpa", "target_roas", "break_even_roas", "target_aov", "max_daily_spend", "refund_rate_critical", "refund_rate_warning"):
                value = getattr(profile, key)
                if value is not None:
                    result[key] = value
        elif profile.scope_type == "PLATFORM" and profile.scope_id == platform:
            for key in ("target_cpa", "target_roas", "break_even_roas"):
                value = getattr(profile, key)
                if value is not None:
                    result[key] = value
        elif profile.scope_type == "CAMPAIGN" and profile.scope_id == campaign_id:
            for key in ("target_cpa", "target_roas", "break_even_roas"):
                value = getattr(profile, key)
                if value is not None:
                    result[key] = value
    return result


async def run_evaluation(
    db: AsyncSession,
    *,
    trigger_type: str = "SCHEDULED",
    rule_keys: Optional[List[str]] = None,
    as_of: Optional[datetime] = None,
    shadow: Optional[bool] = None,
) -> RuleEvaluationRun:
    as_of = as_of or datetime.now(timezone.utc)
    eval_date = as_of.date()
    shadow_mode = settings.rule_engine_mode == "shadow" if shadow is None else shadow
    ignore_cooldown = trigger_type in ("REPLAY", "SIMULATION")
    defaults = load_defaults()
    rules = [r for r in await load_rules_from_db(db) if r.get("enabled", True) and r.get("status") in ("ACTIVE", "SHADOW")]
    if rule_keys:
        rules = [r for r in rules if r["rule_key"] in rule_keys]
    schedule_filter = {
        "INTRADAY": "INTRADAY",
        "DAILY": "DAILY",
        "WEEKLY": "WEEKLY",
    }.get(trigger_type)
    if schedule_filter:
        rules = [r for r in rules if r.get("schedule_group", "DAILY") == schedule_filter]
    if not settings.rule_engine_enabled or not rules:
        return None

    run = RuleEvaluationRun(scope="ALL", trigger_type=trigger_type, status="RUNNING", started_at=as_of, data_as_of=as_of)
    db.add(run)
    await db.flush()

    freshness = await source_freshness(db)
    account_features = await load_account_features(db, eval_date)
    commerce_features = await load_commerce_features(db, eval_date)
    experiments = (await db.execute(select(ActiveExperiment).where(ActiveExperiment.status == "ACTIVE"))).scalars().all()

    triggered: List[EvaluationResult] = []
    entities_evaluated = 0
    feature_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for rule in rules:
        platform = rule.get("platform")
        fact_platform = {"META": "META_ADS", "GOOGLE": "GOOGLE_ADS", "SHOPIFY": "SHOPIFY"}.get(platform, platform)
        level = rule.get("evaluation_level", "AD")
        cache_key = f"{fact_platform}:{level}"
        entities = await _discover_entities(db, fact_platform, level)
        if cache_key not in feature_cache:
            external_ids = [e["entity_id"] for e in entities]
            if level in ("CAMPAIGN", "AD_GROUP", "AD"):
                feature_cache[cache_key] = await load_marketing_features(db, fact_platform or "", level, external_ids, eval_date)
            elif level == "KEYWORD":
                feature_cache[cache_key] = await load_keyword_features(db, external_ids, eval_date)
            elif level == "SEARCH_TERM":
                feature_cache[cache_key] = await load_search_term_features(db, external_ids, eval_date)
            elif level == "ACCOUNT":
                feature_cache[cache_key] = {"ALL": {**account_features, **commerce_features}}

        for entity in entities:
            entity_type = entity["entity_type"]
            entity_id = entity["entity_id"]
            metrics = dict(feature_cache.get(cache_key, {}).get(entity_id, {}))
            if level in ("CAMPAIGN", "AD_GROUP", "AD") and fact_platform == "META_ADS" and level == "AD":
                funnel = await load_funnel_features(db, level, [entity_id], eval_date)
                metrics.update(funnel.get(entity_id, {}))
            sample_score = sample_reliability_score({**metrics, "entity_age_hours": entity.get("age_hours")}, defaults.get("sample_reliability", {}))
            metrics["sample_reliability_score"] = sample_score
            metrics["in_learning"] = bool(
                entity.get("age_hours") is not None and entity["age_hours"] < (rule.get("guards") or {}).get("min_stable_hours", 48)
            )
            metrics["source_stale"] = freshness["stale"]
            metrics["shopify_stale"] = freshness["shopify_stale"]
            if fact_platform == "META_ADS" and metrics.get("purchases_7d", 0) == 0 and metrics.get("clicks_7d", 0) > 0:
                metrics["in_learning"] = metrics["in_learning"] or bool(entity.get("age_hours") is not None and entity["age_hours"] < 24)

            targets = await _load_targets(db, fact_platform, entity.get("campaign_id"))
            changes = (
                await db.execute(
                    select(EntityChangeEvent).where(
                        EntityChangeEvent.entity_id == entity_id,
                        EntityChangeEvent.occurred_at >= as_of - timedelta(days=7),
                    )
                )
            ).scalars().all()
            context = RuleContext(
                evaluation_time=as_of,
                platform=fact_platform,
                entity_type=entity_type,
                entity_id=entity_id,
                campaign_id=entity.get("campaign_id"),
                ad_group_id=entity.get("ad_group_id"),
                business_targets=targets,
                metrics=metrics,
                data_freshness_minutes=freshness["minutes"],
                entity_age_hours=entity.get("age_hours"),
                recent_changes=[{"occurred_at": c.occurred_at, "change_type": c.change_type} for c in changes],
                active_experiments=[
                    {"name": e.name, "scope_type": e.scope_type, "scope_id": e.scope_id} for e in experiments
                ],
                extra={"cross_source_confirmed": None, "ignore_cooldown": ignore_cooldown},
            )
            try:
                result = await evaluate_rule(db, rule, context, defaults)
            except Exception:  # noqa: BLE001
                logger.exception("rule evaluation failed", extra={"rule": rule["rule_key"], "entity": entity_id})
                result = EvaluationResult(
                    rule_key=rule["rule_key"],
                    rule_version=rule.get("version", 1),
                    entity_type=entity_type,
                    entity_id=entity_id,
                    result=RESULT_ERROR,
                )
            entities_evaluated += 1
            db.add(
                RuleEvaluation(
                    evaluation_run_id=str(run.id),
                    rule_key=rule["rule_key"],
                    rule_version=rule.get("version", 1),
                    entity_type=entity_type,
                    entity_id=entity_id,
                    result=result.result,
                    context_snapshot={"platform": fact_platform, "targets": targets},
                    feature_snapshot=result.feature_snapshot,
                    confidence=result.confidence,
                    reason_codes=result.reason_codes,
                    evaluated_at=as_of,
                )
            )
            if result.result == RESULT_TRIGGERED:
                triggered.append(result)

    resolved = resolve_conflicts(triggered)
    deduped = dedup_by_action_reason(resolved)
    if not shadow_mode:
        await persist_recommendations(db, deduped, shadow=False)

    run.rules_evaluated = len(rules)
    run.entities_evaluated = entities_evaluated
    run.triggered = len(triggered)
    run.no_decision = 0
    run.suppressed = sum(1 for r in resolved if r.result == RESULT_SUPPRESSED)
    run.failed = 0
    run.finished_at = datetime.now(timezone.utc)
    run.status = "SUCCESS"
    await db.commit()
    await db.refresh(run)
    return run
