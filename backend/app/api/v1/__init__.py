from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    ads,
    ai_health,
    ai_query,
    ai_runs,
    browser_profiles,
    browser_tasks,
    competitors,
    connections,
    content_intelligence,
    creative_ai,
    creatives,
    dashboard,
    data_health,
    data_sources,
    environment,
    execution_health,
    execution_intents,
    execution_jobs,
    execution_kill_switches,
    execution_policies,
    experiments,
    focus_monitors,
    funnel,
    governance,
    health,
    instagram,
    metrics,
    notifications,
    portfolio,
    production,
    recommendations,
    reviews,
    rule_health,
    rules,
    saved_scopes,
    search_intelligence,
    settings,
    simulations,
    sync_jobs,
    webhooks_shopify,
)

api_router = APIRouter()
api_router.include_router(browser_profiles.router, prefix="/browser-profiles", tags=["browser-profiles"])
api_router.include_router(browser_tasks.router, prefix="/browser-tasks", tags=["browser-tasks"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
api_router.include_router(content_intelligence.router, prefix="/content", tags=["content"])
api_router.include_router(focus_monitors.router, prefix="/focus-monitors", tags=["focus"])
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
api_router.include_router(connections.capabilities_router, prefix="/provider-capabilities", tags=["connections"])
api_router.include_router(saved_scopes.router, prefix="/saved-scopes", tags=["saved-scopes"])
api_router.include_router(governance.router, tags=["governance"])
api_router.include_router(production.router, tags=["production"])
api_router.include_router(environment.router, prefix="/environment", tags=["environment"])
api_router.include_router(data_sources.router, prefix="/data-sources", tags=["data-sources"])
api_router.include_router(sync_jobs.router, prefix="/sync-jobs", tags=["sync-jobs"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(data_health.router, prefix="/data-health", tags=["data-health"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(instagram.router, prefix="/instagram", tags=["instagram"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(webhooks_shopify.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(rules.router, prefix="/rules", tags=["rules"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(simulations.router, prefix="", tags=["simulations"])
api_router.include_router(rule_health.router, prefix="/rule-health", tags=["rule-health"])
api_router.include_router(ai_runs.router, prefix="/ai", tags=["ai"])
api_router.include_router(ai_query.router, prefix="/ai", tags=["ai"])
api_router.include_router(ai_health.router, prefix="/ai", tags=["ai"])
api_router.include_router(creative_ai.router, prefix="", tags=["ai"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(ads.router, prefix="/ads", tags=["ads"])
api_router.include_router(creatives.router, prefix="", tags=["creatives"])
api_router.include_router(search_intelligence.router, prefix="/search-intelligence", tags=["search-intelligence"])
api_router.include_router(funnel.router, prefix="/funnel", tags=["funnel"])
api_router.include_router(competitors.router, prefix="/competitors", tags=["competitors"])
api_router.include_router(experiments.router, prefix="/experiments", tags=["experiments"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(execution_intents.router, prefix="/execution", tags=["execution"])
api_router.include_router(execution_jobs.router, prefix="/execution", tags=["execution"])
api_router.include_router(execution_policies.router, prefix="/execution", tags=["execution"])
api_router.include_router(execution_kill_switches.router, prefix="/execution", tags=["execution"])
api_router.include_router(execution_health.router, tags=["execution"])
