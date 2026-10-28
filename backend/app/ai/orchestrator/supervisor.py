from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.base import AgentDefinition, run_agent
from app.ai.schemas.supervisor import SupervisorPlan

supervisor_agent = AgentDefinition(
    agent_type="supervisor",
    prompt_key="supervisor",
    output_model=SupervisorPlan,
    model_route="supervisor_planning",
)


async def build_plan(
    db: AsyncSession,
    *,
    run_id: str,
    task_type: str,
    user_request: str,
    scope: Dict[str, Any],
    seed: Dict[str, Any],
) -> SupervisorPlan:
    prompt = f"Task: {user_request}\nDetected type: {task_type}\nScope: {scope}"
    plan = await run_agent(
        db,
        supervisor_agent,
        task_prompt=prompt,
        run_id=run_id,
        seed={"task_type": task_type, "scope": scope, **seed},
    )
    return plan
