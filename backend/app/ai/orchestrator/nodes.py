import asyncio
import json
from typing import Any, Dict

from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.base import run_agent
from app.ai.agents.definitions import SPECIALISTS, reviewer_agent, strategy_agent
from app.ai.orchestrator.state import GrowthAgentState
from app.ai.tools.registry import registry


def _tool_kwargs(agent: str, tool: str, **kwargs) -> Dict[str, Any]:
    return {"agent_type": agent, "tool_name": tool, "run_id": None, "step_id": None, "kwargs": kwargs}


async def _specialist_context(db: AsyncSession, agent_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
    run_id = state.get("run_id")
    seed: Dict[str, Any] = {"entity": state.get("scope", {}).get("entity_id", "campaign")}
    if agent_type == "performance":
        rules = await registry.call(db, agent_type="performance", tool_name="get_entity_rule_findings", run_id=run_id, step_id=None, kwargs={"entity_type": "CAMPAIGN", "entity_id": seed["entity"]})
        targets = await registry.call(db, agent_type="performance", tool_name="get_business_targets", run_id=run_id, step_id=None, kwargs={})
        seed["rule_findings"] = rules
        seed["business_targets"] = targets
        seed["source_metric_ids"] = [f"metric://campaign/{seed['entity']}"]
    elif agent_type == "funnel":
        funnel = await registry.call(db, agent_type="funnel", tool_name="get_funnel_performance", run_id=run_id, step_id=None, kwargs={"entity_id": seed["entity"]})
        seed["funnel"] = funnel
        seed["stage_of_failure"] = "CHECKOUT_TO_PURCHASE"
        seed["severity"] = "MEDIUM"
    elif agent_type == "search":
        terms = await registry.call(db, agent_type="search", tool_name="get_search_term_performance", run_id=run_id, step_id=None, kwargs={})
        seed["search_terms"] = terms
        seed["waste_candidates"] = [
            {"term": t["term"], "semantic_class": "IRRELEVANT", "commercial_relevance": "LOW", "negative_candidate_confidence": 0.6, "reason": "high spend, zero conversions", "spend": t["spend"], "clicks": t["clicks"], "conversions": t["conversions"]}
            for t in (terms.get("search_terms") or [])[:5]
            if t.get("conversions", 0) == 0 and t.get("clicks", 0) >= 10
        ]
    elif agent_type == "creative":
        creative_id = state.get("scope", {}).get("creative_id", "creative-1")
        meta = await registry.call(db, agent_type="creative", tool_name="get_creative_metadata", run_id=run_id, step_id=None, kwargs={"creative_id": creative_id})
        seed["creative_id"] = creative_id
        seed["creative_metadata"] = meta
        seed["analysis_mode"] = "FRAME_SAMPLE"
    elif agent_type == "competitor":
        url = state.get("scope", {}).get("url", "https://example.com")
        snapshot = await registry.call(db, agent_type="competitor", tool_name="public_page_snapshot", run_id=run_id, step_id=None, kwargs={"url": url, "profile_id": state.get("scope", {}).get("profile_id", "research-01")})
        seed["observations"] = [{"source_url": url, "capture_at": None, "observation": "Public page observed (snapshot stub).", "claim_type": "HYPOTHESIS", "evidence_refs": [snapshot.get("_output_ref", "browser-snapshot://unknown")]}]
    return seed


async def specialists_node(state: GrowthAgentState, db: AsyncSession) -> Dict[str, Any]:
    plan = state.get("plan") or {}
    agents = plan.get("agents") or ["performance"]
    outputs: Dict[str, Any] = {}
    errors: list = []

    async def run_one(agent_type: str) -> None:
        try:
            definition = SPECIALISTS[agent_type]
            seed = await _specialist_context(db, agent_type, state)
            task = f"Analyze {agent_type} for scope {state.get('scope')}. Request: {state.get('user_request')}"
            outputs[agent_type] = (await run_agent(db, definition, task_prompt=task, run_id=state["run_id"], seed=seed)).model_dump()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{agent_type}: {exc}")
            outputs[agent_type] = {"status": "ERROR", "error": str(exc)}

    await asyncio.gather(*[run_one(a) for a in agents])
    return {"specialist_outputs": outputs, "errors": errors, "status": "PARTIAL" if errors else "RUNNING"}


async def strategy_node(state: GrowthAgentState, db: AsyncSession) -> Dict[str, Any]:
    run_id = state.get("run_id")
    recs = await registry.call(db, agent_type="strategy", tool_name="get_open_recommendations", run_id=run_id, step_id=None, kwargs={})
    targets = await registry.call(db, agent_type="strategy", tool_name="get_business_targets", run_id=run_id, step_id=None, kwargs={})
    seed = {
        "rule_refs": [f"rule://{r.get('id')}" for r in (recs.get("recommendations") or [])],
        "evidence_refs": [],
        "actions_now": [r.get("primary_action") for r in (recs.get("recommendations") or [])[:5]],
    }
    review_feedback = state.get("review_output") or {}
    task = (
        f"Synthesize strategy. Request: {state.get('user_request')}. "
        f"Specialists: {json.dumps(state.get('specialist_outputs', {}), ensure_ascii=False)[:4000]}. "
        f"Recommendations: {json.dumps(recs, ensure_ascii=False)[:2000]}. "
        f"Targets: {json.dumps(targets, ensure_ascii=False)[:1000]}."
    )
    if review_feedback and review_feedback.get("passed") is False:
        task += f" Reviewer revisions requested: {review_feedback.get('required_revisions')}"
    strategy = await run_agent(db, strategy_agent, task_prompt=task, run_id=run_id, seed=seed)
    return {"strategy_output": strategy.model_dump(), "status": "RUNNING"}


async def review_node(state: GrowthAgentState, db: AsyncSession) -> Dict[str, Any]:
    run_id = state.get("run_id")
    strategy = state.get("strategy_output") or {}
    seed = {}
    if state.get("force_review_fail"):
        seed["force_review_fail"] = True
    review = await run_agent(db, reviewer_agent, task_prompt=f"Review strategy: {json.dumps(strategy, ensure_ascii=False)[:3000]}", run_id=run_id, seed=seed)
    return {"review_output": review.model_dump(), "revision_count": (state.get("revision_count") or 0)}


async def revise_node(state: GrowthAgentState, db: AsyncSession) -> Dict[str, Any]:
    return {"revision_count": (state.get("revision_count") or 0) + 1, "review_output": None}


async def human_node(state: GrowthAgentState) -> Dict[str, Any]:
    strategy = state.get("strategy_output") or {}
    needs_approval = state.get("plan", {}).get("approval_expected") or state.get("status") == "HUMAN_REVIEW_REQUIRED"
    packet = {
        "recommendation_id": None,
        "action_type": "STRATEGY_REVIEW",
        "entity": state.get("scope", {}).get("entity_id"),
        "why": strategy.get("executive_summary", ""),
        "risk": "MEDIUM",
        "expires_at": None,
    }
    if needs_approval:
        decision = interrupt({"type": "human_approval", "packet": packet})
        return {"decision": decision, "pending_approval": packet, "status": "WAITING_HUMAN" if decision is None else "COMPLETED"}
    return {"pending_approval": packet, "status": "COMPLETED"}


async def complete_node(state: GrowthAgentState, db: AsyncSession) -> Dict[str, Any]:
    return {"status": "COMPLETED"}
