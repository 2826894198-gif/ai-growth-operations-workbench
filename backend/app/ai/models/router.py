from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml

from app.ai.models.base import ModelProvider
from app.ai.models.gemini_provider import GeminiProvider
from app.ai.models.mock_provider import MockModelProvider
from app.ai.models.openai_provider import OpenAIProvider
from app.core.config import settings
from app.core.project_paths import config_path

CONFIG_PATH = config_path("ai", "model_routes.yaml")


@dataclass
class ModelRoute:
    task_type: str
    provider_name: str
    model: str
    capability: str
    fallback_chain: List[str]
    reasoning_effort: Optional[str] = None


def _routes() -> Dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _provider_instance(provider_name: str, model: str) -> ModelProvider:
    if provider_name == "openai":
        return OpenAIProvider(model=model)
    if provider_name == "gemini":
        return GeminiProvider(model=model)
    return MockModelProvider()


def _resolve(preferred: str) -> tuple:
    if settings.ai_provider_mode == "mock":
        return "mock", "mock-model"
    if preferred == "primary":
        return settings.ai_primary_provider, settings.ai_primary_reasoning_model
    if preferred == "fast":
        return settings.ai_fast_provider, settings.ai_fast_model
    if preferred == "video":
        return settings.ai_video_provider, settings.ai_video_model
    return "mock", "mock-model"


def route_task(task_type: str, risk_level: str = "LOW", modality: str = "text") -> ModelRoute:
    routes = _routes().get("routes", {})
    config = routes.get(task_type, {"capability": "reasoning", "preferred": "fast", "fallback": ["primary"]})
    preferred = config.get("preferred", "fast")
    provider, model = _resolve(preferred)
    fallback = []
    for item in config.get("fallback", []):
        fallback.extend(list(_resolve(item)))
    return ModelRoute(
        task_type=task_type,
        provider_name=provider,
        model=model,
        capability=config.get("capability", "reasoning"),
        fallback_chain=fallback,
    )


def get_provider_for_task(task_type: str, risk_level: str = "LOW", modality: str = "text") -> ModelProvider:
    route = route_task(task_type, risk_level, modality)
    return _provider_instance(route.provider_name, route.model)
