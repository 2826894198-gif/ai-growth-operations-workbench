from functools import lru_cache

from app.core.config import settings
from app.integrations.adspower.browser_service import AdsPowerBrowserService
from app.integrations.adspower.client import AdsPowerClient
from app.integrations.adspower.health_service import AdsPowerHealthService
from app.integrations.adspower.profile_service import AdsPowerProfileService
from app.services.browser_profile_service import BrowserProfileService
from app.services.browser_task_service import BrowserTaskService
from app.services.dashboard_service import DashboardService
from app.services.data_health_service import DataHealthService
from app.services.data_source_service import DataSourceService
from app.services.environment_health_service import EnvironmentHealthService
from app.services.metrics_service import MetricsService
from app.services.sync_service import SyncService


@lru_cache
def get_adspower_client() -> AdsPowerClient:
    return AdsPowerClient(
        base_url=settings.adspower_base_url,
        api_key=settings.adspower_api_key,
        max_concurrency=settings.adspower_max_concurrency,
        requests_per_second=settings.adspower_requests_per_second,
        connect_timeout=settings.adspower_connect_timeout,
        read_timeout=settings.adspower_read_timeout,
    )


def get_adspower_profile_service() -> AdsPowerProfileService:
    return AdsPowerProfileService(get_adspower_client())


def get_adspower_browser_service() -> AdsPowerBrowserService:
    return AdsPowerBrowserService(get_adspower_client())


def get_adspower_health_service() -> AdsPowerHealthService:
    return AdsPowerHealthService(get_adspower_client())


def get_browser_profile_service() -> BrowserProfileService:
    return BrowserProfileService(get_adspower_profile_service())


def get_environment_health_service() -> EnvironmentHealthService:
    return EnvironmentHealthService()


def get_browser_task_service() -> BrowserTaskService:
    return BrowserTaskService(get_environment_health_service())


def get_data_source_service() -> DataSourceService:
    return DataSourceService()


def get_sync_service() -> SyncService:
    return SyncService()


def get_metrics_service() -> MetricsService:
    return MetricsService()


def get_data_health_service() -> DataHealthService:
    return DataHealthService()


def get_dashboard_service() -> DashboardService:
    return DashboardService()
