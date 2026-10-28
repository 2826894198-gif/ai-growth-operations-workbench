import time
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from app.ai.models.base import (
    ModelAuthError,
    ModelCallResult,
    ModelSchemaError,
    ModelTimeout,
)
from app.core.config import settings


class GeminiProvider:
    """Gemini provider for native video understanding (structured JSON)."""

    name = "gemini"

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.ai_video_model
        self._client = None

    def _ensure(self):
        if self._client is None:
            if not settings.gemini_api_key:
                raise ModelAuthError("GEMINI_API_KEY not configured")
            try:
                from google import genai
            except ImportError as exc:
                raise ModelAuthError("google-genai package not installed; run pip install -e '.[google]'") from exc
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    async def analyze_multimodal(
        self, system_prompt: str, media_refs: List[str], output_model: Type[BaseModel]
    ) -> ModelCallResult:
        client = self._ensure()
        started = time.monotonic()
        schema = output_model.model_json_schema()
        contents = [system_prompt]
        contents.extend(media_refs)
        try:
            response = await client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config={"response_mime_type": "application/json", "response_schema": schema},
            )
        except Exception as exc:  # noqa: BLE001
            raise ModelTimeout(str(exc)) from exc
        try:
            structured = output_model.model_validate_json(response.text)
        except Exception as exc:  # noqa: BLE001
            raise ModelSchemaError(f"invalid structured output: {exc}") from exc
        return ModelCallResult(
            content=response.text,
            structured=structured.model_dump(),
            provider="gemini",
            model=self.model or "unknown",
            estimated_cost=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
            media_usage={"video_media_refs": len(media_refs)},
        )

    async def generate_structured(
        self,
        system_prompt: str,
        task_prompt: str,
        output_model: Type[BaseModel],
        *,
        seed: Optional[Dict[str, Any]] = None,
        modality: str = "text",
    ) -> ModelCallResult:
        return await self.analyze_multimodal(system_prompt, [task_prompt], output_model)

    async def generate_text(self, system_prompt: str, task_prompt: str) -> ModelCallResult:
        client = self._ensure()
        response = await client.aio.models.generate_content(model=self.model, contents=[system_prompt, task_prompt])
        return ModelCallResult(content=response.text, provider="gemini", model=self.model or "unknown")

    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError("embedding not implemented on Gemini provider")
