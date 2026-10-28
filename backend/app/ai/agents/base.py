from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models.base import ModelProvider, ModelSchemaError, validate_structured
from app.ai.models.router import get_provider_for_task
from app.ai.prompts.registry import get_prompt
from app.models.ai import AIAgentStep, AIModelUsage


@dataclass
class AgentDefinition:
    agent_type: str
    prompt_key: str
    output_model: Type[BaseModel]
    model_route: str
    risk_level: str = "LOW"


async def run_agent(
    db: AsyncSession,
    agent: AgentDefinition,
    *,
    task_prompt: str,
    run_id: str,
    step_id: Optional[str] = None,
    seed: Optional[Dict[str, Any]] = None,
    provider: Optional[ModelProvider] = None,
) -> BaseModel:
    prompt = await get_prompt(db, agent.prompt_key)
    system_prompt = prompt.system_prompt if prompt else agent.prompt_key
    provider = provider or get_provider_for_task(agent.model_route, agent.risk_level)
    result = await provider.generate_structured(
        system_prompt=system_prompt,
        task_prompt=task_prompt,
        output_model=agent.output_model,
        seed=seed,
    )
    try:
        parsed = validate_structured(result, agent.output_model)
    except ModelSchemaError:
        # One structured repair retry.
        result = await provider.generate_structured(
            system_prompt=system_prompt + "\nFix the previous structured output to match the schema exactly.",
            task_prompt=task_prompt,
            output_model=agent.output_model,
            seed=seed,
        )
        parsed = validate_structured(result, agent.output_model)
    db.add(
        AIAgentStep(
            run_id=run_id,
            agent_type=agent.agent_type,
            step_type="AGENT",
            prompt_version=prompt.version if prompt else "unknown",
            model_provider=result.provider,
            model_name=result.model,
            input_ref="run-context",
            output_ref=f"run://{run_id}/agent/{agent.agent_type}",
            tool_calls=0,
            token_usage={"input": result.input_tokens, "output": result.output_tokens, "cached": result.cached_tokens},
            estimated_cost=result.estimated_cost,
            latency_ms=result.latency_ms,
            status="SUCCESS",
        )
    )
    db.add(
        AIModelUsage(
            run_id=run_id,
            step_id=step_id,
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cached_tokens=result.cached_tokens,
            estimated_cost=result.estimated_cost,
            latency_ms=result.latency_ms,
        )
    )
    await db.commit()
    return parsed
