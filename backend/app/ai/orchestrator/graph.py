from typing import Any, Dict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestrator.checkpoints import build_checkpointer
from app.ai.orchestrator.nodes import (
    complete_node,
    human_node,
    review_node,
    revise_node,
    specialists_node,
    strategy_node,
)
from app.ai.orchestrator.state import GrowthAgentState
from app.ai.orchestrator.supervisor import build_plan


def _deps(db: AsyncSession) -> Dict[str, Any]:
    return {"db": db}


def build_graph(db: AsyncSession):
    graph = StateGraph(GrowthAgentState)

    async def supervisor_node(state: GrowthAgentState):
        plan = await build_plan(
            db,
            run_id=state["run_id"],
            task_type=state.get("task_type", "DAILY_GROWTH_REVIEW"),
            user_request=state.get("user_request", ""),
            scope=state.get("scope", {}),
            seed={"agents": state.get("plan_agents_override", [])},
        )
        return {"plan": plan.model_dump(), "status": "RUNNING"}

    async def specialists(state: GrowthAgentState):
        return await specialists_node(state, db)

    async def strategy(state: GrowthAgentState):
        return await strategy_node(state, db)

    async def review(state: GrowthAgentState):
        return await review_node(state, db)

    async def revise(state: GrowthAgentState):
        return await revise_node(state, db)

    async def complete(state: GrowthAgentState):
        return await complete_node(state, db)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("specialists", specialists)
    graph.add_node("strategy", strategy)
    graph.add_node("review", review)
    graph.add_node("revise", revise)
    graph.add_node("human", human_node)
    graph.add_node("complete", complete)

    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "specialists")
    graph.add_edge("specialists", "strategy")
    graph.add_edge("strategy", "review")

    def after_review(state: GrowthAgentState) -> str:
        review = state.get("review_output") or {}
        if review.get("passed") is False and (state.get("revision_count") or 0) < 1:
            return "revise"
        return "human"

    graph.add_conditional_edges("review", after_review, {"revise": "revise", "human": "human"})
    graph.add_edge("revise", "strategy")
    graph.add_edge("human", "complete")
    graph.add_edge("complete", END)
    return graph.compile(checkpointer=build_checkpointer())
