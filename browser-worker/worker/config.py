from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    backend_api_url: str = "http://127.0.0.1:8000"
    worker_token: str = "change-me-worker-token"
    service_name: str = "browser-worker"
    log_level: str = "INFO"

    adspower_base_url: str = "http://127.0.0.1:50325"
    adspower_api_key: str = ""
    adspower_max_concurrency: int = 2
    adspower_requests_per_second: float = 1.0

    redis_url: str = "redis://localhost:6379/0"
    browser_worker_queue: str = "browser-worker"
    task_timeout_seconds: int = 300
    lock_margin_seconds: int = 60

    artifacts_dir: str = "./artifacts"
    navigation_timeout_ms: int = 45000
    diagnostic_url: str = "https://ipinfo.io/json"
    smoke_test_url: str = "https://example.com"
    page_guard_allow_private: bool = False

    @field_validator("adspower_base_url", "backend_api_url")
    @classmethod
    def strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def screenshot_dir(self) -> str:
        return f"{self.artifacts_dir.rstrip('/')}/screenshots"

    @property
    def log_dir(self) -> str:
        return f"{self.artifacts_dir.rstrip('/')}/logs"


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()
