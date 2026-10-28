
from app.core.config import settings
from app.execution.providers.base import ExecutionProvider


def get_execution_provider(provider: str, force_mock: bool = False) -> ExecutionProvider:
    provider = provider.upper()
    if provider == "MOCK" or force_mock or settings.data_provider_mode == "mock":
        from app.execution.providers.mock import MockExecutionProvider

        return MockExecutionProvider()
    if provider == "META":
        from app.execution.providers.meta.provider import MetaExecutionProvider

        return MetaExecutionProvider()
    if provider == "GOOGLE_ADS":
        from app.execution.providers.google_ads.provider import GoogleAdsExecutionProvider

        return GoogleAdsExecutionProvider()
    raise ValueError(f"unknown execution provider: {provider}")
