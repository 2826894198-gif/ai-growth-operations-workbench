"""PART 03 rule-engine smoke test (mock mode, no credentials).

Usage:  DATABASE_URL=sqlite+aiosqlite:///./smoke_rules.db RULE_ENGINE_MODE=active \
        python scripts/smoke_rules.py
"""

import asyncio
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/smoke_rules.db")
os.environ.setdefault("DATA_PROVIDER_MODE", "mock")
os.environ.setdefault("RULE_ENGINE_MODE", "active")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_fixtures  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.etl.pipeline import (  # noqa: E402
    run_google_pipeline,
    run_meta_pipeline,
    run_shopify_pipeline,
)
from app.models.data_source import DataSource  # noqa: E402
from app.models.rules import (  # noqa: E402
    BusinessTargetProfile,
    Recommendation,
    RuleAuditLog,
    RuleDefinition,
)
from app.rules.conflict.resolver import resolve_conflicts  # noqa: E402
from app.rules.engine import run_evaluation  # noqa: E402
from app.rules.registry import load_rule_packs  # noqa: E402
from app.rules.simulation.replay import replay_rule  # noqa: E402
from app.rules.simulation.simulator import simulate_rule  # noqa: E402

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL':<5} {name}" + (f"  {detail}" if detail else ""), flush=True)


async def main() -> int:
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        check("Database", (await conn.execute(text("SELECT 1"))).scalar() == 1)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    from app.etl.metric_registry import METRICS
    from app.rules.features.registry import FEATURE_REGISTRY

    check("Metric Registry", len(METRICS) >= 5)
    check("Feature Registry", len(FEATURE_REGISTRY) >= 20)

    rng = random.Random("smoke-rules")
    meta = generate_fixtures.build_meta(7, rng, "zero_purchase_burn")
    google = generate_fixtures.build_google(7, rng, "google_high_cpc")
    shopify = generate_fixtures.build_shopify(7, rng, "shopify_refund_spike")

    async with factory() as db:
        now = datetime.now(timezone.utc)
        sources = [
            DataSource(provider="META_ADS", name="Smoke Meta", external_account_id="act_smoke", meta={"scenario": "zero_purchase_burn"}, last_successful_sync_at=now),
            DataSource(provider="GOOGLE_ADS", name="Smoke Google", external_account_id="g_smoke", meta={"scenario": "google_high_cpc"}, last_successful_sync_at=now),
            DataSource(provider="SHOPIFY", name="Smoke Shopify", external_account_id="s_smoke", meta={"scenario": "shopify_refund_spike"}, last_successful_sync_at=now),
        ]
        db.add_all(sources)
        await db.flush()
        ids = {s.provider: str(s.id) for s in sources}

        await run_meta_pipeline(db, ids["META_ADS"], accounts=meta["accounts"], campaigns=meta["campaigns"], ad_groups=meta["ad_groups"], ads=meta["ads"], creatives=meta["creatives"], performance=meta["performance"], sync_job_id="smoke")
        await run_google_pipeline(db, ids["GOOGLE_ADS"], accounts=google["accounts"], campaigns=google["campaigns"], ad_groups=google["ad_groups"], ads=google["ads"], asset_groups=google["asset_groups"], keywords=google["keywords"], search_terms=google["search_terms"], conversion_actions=google["conversion_actions"], performance=google["performance"], sync_job_id="smoke")
        await run_shopify_pipeline(db, ids["SHOPIFY"], products=shopify["products"], variants=shopify["variants"], orders=shopify["orders"], order_items=shopify["order_items"], refunds=shopify["refunds"], journeys=shopify["journeys"], sync_job_id="smoke")
        db.add(
            BusinessTargetProfile(
                name="Smoke Global", scope_type="GLOBAL", currency="USD",
                target_cpa=30.0, target_roas=2.2, break_even_roas=1.2,
                max_daily_spend=2000.0, refund_rate_critical=0.08,
            )
        )
        await db.commit()

        packs = load_rule_packs()
        check("Rule Load", len(packs) >= 30, f"{len(packs)} rules from YAML packs")
        for rule in packs:
            db.add(
                RuleDefinition(
                    rule_key=rule["rule_key"], name=rule["name"], category=rule["category"],
                    platform=rule.get("platform"), evaluation_level=rule.get("evaluation_level", "AD"),
                    severity=rule.get("severity", "MEDIUM"), version=1, status="ACTIVE", enabled=True,
                    schedule_group=rule.get("schedule_group", "DAILY"),
                    conditions=rule.get("conditions"), guards=rule.get("guards"),
                    action_template=rule.get("action"),
                    required_capabilities=rule.get("required_capabilities", []),
                    cooldown_minutes=rule.get("cooldown_minutes", 1440),
                )
            )
        db.add(RuleAuditLog(actor="smoke", action="rule_created", target="packs"))
        await db.commit()
        check("Rule Versioning", (await db.execute(select(func.count()).select_from(RuleDefinition))).scalar_one() == len(packs))

        keys = [
            "META_NO_PURCHASE_BURN",
            "GOOGLE_SEARCH_TERM_WASTE",
            "COM_REFUND_SPIKE",
            "XC_BLENDED_ROAS_GUARD",
            "FUNNEL_CHECKOUT_TO_PURCHASE",
        ]
        run = await run_evaluation(db, trigger_type="MANUAL", rule_keys=keys, as_of=now)
        check("Mock Meta Rules", run.triggered > 0, f"triggered={run.triggered}")
        check("Rule Evaluator", run.entities_evaluated > 0 and run.rules_evaluated == len(keys))
        recs = (await db.execute(select(Recommendation))).scalars().all()
        check("Recommendation System", len(recs) > 0, f"recommendations={len(recs)}")
        check("Audit", (await db.execute(select(func.count()).select_from(RuleAuditLog))).scalar_one() >= 1)

        # Guards (unit-level)
        from app.rules.context import RuleContext
        from app.rules.guards.freshness import check_freshness
        from app.rules.guards.sample import check_sample

        ctx = RuleContext(evaluation_time=now, data_freshness_minutes=5, entity_age_hours=72, metrics={"clicks_7d": 100, "purchases_7d": 5, "spend_7d": 200})
        check("Freshness Guard", check_freshness(ctx, {"data_freshness_minutes": 30})[0])
        check("Sample Guard", check_sample(ctx, {}, {"min_active_hours": 24, "min_clicks_units": 30, "min_spend_units": 20})[0])
        learning_ctx = RuleContext(evaluation_time=now, data_freshness_minutes=5, entity_age_hours=3, metrics={"clicks_7d": 100, "purchases_7d": 5, "spend_7d": 200})
        from app.rules.guards.learning import check_learning

        check("Learning Guard", check_learning(learning_ctx, {"min_stable_hours": 48})[0] is False)

        # Conflict + dedup + confidence
        from app.rules.confidence.scorer import confidence_band
        from app.rules.recommendations.dedup import dedup_by_action_reason
        from app.rules.result import EvaluationResult

        a = EvaluationResult(rule_key="A", rule_version=1, entity_type="AD", entity_id="x", result="TRIGGERED", action="CHECK_TRACKING", reason_group="T", severity="HIGH", confidence=0.8)
        b = EvaluationResult(rule_key="B", rule_version=1, entity_type="AD", entity_id="x", result="TRIGGERED", action="REVIEW_SCALE", reason_group="S", severity="MEDIUM", confidence=0.9)
        resolved = resolve_conflicts([a, b])
        check("Conflict Resolver", any(r.result == "SUPPRESSED" for r in resolved))
        dup = dedup_by_action_reason([a, EvaluationResult(rule_key="A2", rule_version=1, entity_type="AD", entity_id="x", result="TRIGGERED", action="CHECK_TRACKING", reason_group="T", severity="HIGH", confidence=0.8)])
        check("Recommendation Dedup", len(dup) == 1)
        check("Confidence Engine", confidence_band(0.8) == "HIGH")

        replay = await replay_rule(db, "META_NO_PURCHASE_BURN", (date.today() - timedelta(days=1)).isoformat(), date.today().isoformat())
        check("Historical Replay", replay["approximate"] is True and len(replay["days"]) >= 1)
        sim = await simulate_rule(db, "META_NO_PURCHASE_BURN", {"multiple": 1.5}, (date.today() - timedelta(days=1)).isoformat(), date.today().isoformat())
        check("Simulation", "total_triggers" in sim)
        check("Simulation No Mutation", (await db.execute(select(func.count()).select_from(RuleDefinition).where(RuleDefinition.rule_key.like("%__SIM%")))).scalar_one() == 0)

    await engine.dispose()
    failed = sum(1 for ok in RESULTS if not ok)
    print("SMOKE RULES " + ("PASSED" if failed == 0 else "FAILED"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
