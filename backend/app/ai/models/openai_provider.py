import json
import time
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from app.ai.models.base import (
    ModelAuthError,
    ModelCallResult,
    ModelContextTooLarge,
    ModelRateLimited,
    ModelSchemaError,
    ModelTimeout,
)
from app.core.config import settings


class OpenAIProvider:
    """OpenAI Responses API provider (structured outputs)."""

    name = "openai"

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.ai_primary_reasoning_model
        self._client = None

    def _ensure(self):
        if self._client is None:
            if not settings.openai_api_key:
                raise ModelAuthError("OPENAI_API_KEY not configured")
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def generate_structured(
        self,
        system_prompt: str,
        task_prompt: str,
        output_model: Type[BaseModel],
        *,
        seed: Optional[Dict[str, Any]] = None,
        modality: str = "text",
    ) -> ModelCallResult:
        client = self._ensure()
        schema = output_model.model_json_schema()
        started = time.monotonic()
        try:
            response = await client.responses.create(
                model=self.model,
                instructions=system_prompt,
                input=task_prompt,
                text={"format": {"type": "json_schema", "name": output_model.__name__, "schema": schema, "strict": True}},
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc).lower()
            if "auth" in message or "api key" in message:
                raise ModelAuthError(str(exc)) from exc
            if "rate" in message or "429" in message:
                raise ModelRateLimited(str(exc)) from exc
            if "timeout" in message:
                raise ModelTimeout(str(exc)) from exc
            if "context" in message and "length" in message:
                raise ModelContextTooLarge(str(exc)) from exc
            raise ModelAuthError(str(exc)) from exc
        try:
            structured = json.loads(response.output_text)
            parsed = output_model.model_validate(structured)
        except Exception as exc:  # noqa: BLE001
            raise ModelSchemaError(f"invalid structured output: {exc}") from exc
        usage = response.usage or {}
        return ModelCallResult(
            content=response.output_text,
            structured=parsed.model_dump(),
            provider="openai",
            model=self.model or "unknown",
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cached_tokens=getattr(usage, "input_tokens_details", None) and getattr(usage.input_tokens_details, "cached_tokens", 0) or 0,
            estimated_cost=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    async def generate_text(self, system_prompt: str, task_prompt: str) -> ModelCallResult:
        client = self._ensure()
        response = await client.responses.create(model=self.model, instructions=system_prompt, input=task_prompt)
        return ModelCallResult(content=response.output_text, provider="openai", model=self.model or "unknown")

    async def analyze_multimodal(
        self, system_prompt: str, media_refs: List[str], output_model: Type[BaseModel]
    ) -> ModelCallResult:
        raise ModelSchemaError("OpenAI provider not configured for video analysis in this build; use Gemini or mock")

    async def embed(self, texts: List[str]) -> List[List[float]]:
        client = self._ensure()
        response = await client.embeddings.create(model=settings.ai_embedding_model, input=texts)
        return [item.embedding for item in response.data]
