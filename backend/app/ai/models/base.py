from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Type, runtime_checkable

from pydantic import BaseModel


class ModelError(Exception):
    error_code = "MODEL_PROVIDER_ERROR"


class ModelAuthError(ModelError):
    error_code = "MODEL_AUTH_ERROR"


class ModelRateLimited(ModelError):
    error_code = "MODEL_RATE_LIMITED"


class ModelTimeout(ModelError):
    error_code = "MODEL_TIMEOUT"


class ModelSchemaError(ModelError):
    error_code = "MODEL_SCHEMA_ERROR"


class ModelContextTooLarge(ModelError):
    error_code = "MODEL_CONTEXT_TOO_LARGE"


@dataclass
class ModelCallResult:
    content: str
    structured: Optional[Dict[str, Any]] = None
    provider: str = "mock"
    model: str = "mock"
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: int = 0
    error_code: Optional[str] = None
    media_usage: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ModelProvider(Protocol):
    name: str

    async def generate_structured(
        self,
        system_prompt: str,
        task_prompt: str,
        output_model: Type[BaseModel],
        *,
        seed: Optional[Dict[str, Any]] = None,
        modality: str = "text",
    ) -> ModelCallResult: ...

    async def generate_text(self, system_prompt: str, task_prompt: str) -> ModelCallResult: ...

    async def analyze_multimodal(
        self, system_prompt: str, media_refs: List[str], output_model: Type[BaseModel]
    ) -> ModelCallResult: ...

    async def embed(self, texts: List[str]) -> List[List[float]]: ...


def validate_structured(result: ModelCallResult, output_model: Type[BaseModel]) -> BaseModel:
    try:
        return output_model.model_validate(result.structured)
    except Exception as exc:
        raise ModelSchemaError(f"structured output validation failed: {exc}") from exc
