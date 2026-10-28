from typing import Optional

from app.core.config import settings
from app.integrations.base import MarketingDataProvider
from app.integrations.google_ads.provider import GoogleAdsProvider
from app.integrations.meta_ads.provider import MetaProvider
from app.integrations.mock_provider import MockProvider
from app.integrations.shopify.provider import ShopifyProvider


def get_provider(provider: str, scenario: Optional[str] = None) -> MarketingDataProvider:
    if settings.data_provider_mode == "mock":
        return MockProvider(provider, scenario=scenario or settings.mock_scenario)
    if provider == "META_ADS":
        return MetaProvider()
    if provider == "GOOGLE_ADS":
        return GoogleAdsProvider()
    if provider == "SHOPIFY":
        return ShopifyProvider()
    raise ValueError(f"unknown provider: {provider}")
