from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI DTC Growth Automation System - US Operation Environment"
    api_v1_prefix: str = "/api/v1"
    app_env: str = "local"  # local | test | staging | production
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://growth:growth@localhost:5432/growth"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-only-change-me"
    cors_origins: str = "http://localhost:5173"

    # AdsPower Local API
    adspower_base_url: str = "http://127.0.0.1:50325"
    adspower_api_key: str = ""
    adspower_max_concurrency: int = 2
    adspower_requests_per_second: float = 1.0
    adspower_connect_timeout: float = 3.0
    adspower_read_timeout: float = 15.0

    # Task queue / worker
    browser_worker_queue: str = "browser-worker"
    browser_task_timeout_seconds: int = 300
    browser_lock_margin_seconds: int = 60
    browser_task_max_retries: int = 3

    # Worker -> backend callback auth
    worker_token: str = "change-me-worker-token"
    backend_api_url: str = "http://127.0.0.1:8000"

    artifacts_dir: str = "./artifacts"

    # --- Part 02: Data platform core ---
    reporting_currency: str = "USD"
    data_provider_mode: str = "mock"  # mock | live
    mock_scenario: str = "healthy_growth"

    # --- Meta Marketing API ---
    meta_enabled: bool = False
    meta_graph_api_version: str = "v26.0"
    meta_access_token: str = ""
    meta_ad_account_id: str = ""
    meta_intraday_sync_minutes: int = 15
    meta_reconcile_days: int = 3
    meta_nightly_reconcile_days: int = 7
    meta_weekly_reconcile_days: int = 30
    meta_backfill_chunk_days: int = 7

    # --- Google Ads ---
    google_ads_enabled: bool = False
    google_ads_api_version: str = "v25"
    google_ads_developer_token: str = ""
    google_ads_customer_id: str = ""
    google_ads_login_customer_id: str = ""
    google_ads_service_account_json_path: str = ""
    google_intraday_sync_minutes: int = 15
    google_reconcile_days: int = 3
    google_nightly_reconcile_days: int = 7
    google_weekly_reconcile_days: int = 30
    google_backfill_chunk_days: int = 7

    # --- Shopify ---
    shopify_enabled: bool = False
    shopify_api_version: str = "2026-07"
    shopify_shop_domain: str = ""
    shopify_access_token: str = ""
    shopify_webhook_secret: str = ""
    shopify_reconcile_minutes: int = 60
    shopify_reconcile_days: int = 2
    shopify_nightly_reconcile_days: int = 7

    # --- Backfill / retention ---
    initial_backfill_days: int = 90
    backfill_max_concurrency: int = 1
    raw_payload_retention_days: int = 180
    webhook_retention_days: int = 180
    intraday_snapshot_retention_days: int = 90

    # --- Part 03: Growth Rule Engine ---
    rule_engine_enabled: bool = True
    rule_engine_mode: str = "shadow"  # shadow | active
    rule_intraday_interval_minutes: int = 15
    rule_daily_run_hour: int = 8
    rule_weekly_run_day: int = 1
    rule_default_timezone: str = "UTC"
    rule_confidence_min_display: float = 0.40
    rule_simulation_max_days: int = 180
    rule_enable_anomaly_detection: bool = True
    rule_recommendation_retention_days: int = 730
    rule_evaluation_retention_days: int = 730

    # --- Part 04: Multi-Agent & AI Intelligence ---
    ai_enabled: bool = True
    ai_provider_mode: str = "mock"  # mock | live
    ai_orchestrator: str = "langgraph"
    ai_primary_provider: str = "openai"
    ai_primary_reasoning_model: str = ""
    ai_fast_provider: str = "openai"
    ai_fast_model: str = ""
    ai_video_provider: str = "gemini"
    ai_video_model: str = ""
    ai_embedding_provider: str = "openai"
    ai_embedding_model: str = ""
    ai_max_review_revisions: int = 1
    ai_default_run_cost_limit: float = 0.0
    ai_daily_cost_limit: float = 0.0
    ai_max_parallel_agents: int = 4
    ai_trace_enabled: bool = True
    ai_store_model_inputs: bool = False
    ai_store_model_outputs: bool = True
    openai_api_key: str = ""
    gemini_api_key: str = ""
    knowledge_enabled: bool = True
    pgvector_enabled: bool = True
    knowledge_top_k: int = 5
    ai_memory_enabled: bool = True
    ai_memory_require_approval: bool = True
    ai_browser_research_enabled: bool = False
    adspower_mcp_enabled: bool = False
    ai_evals_enabled: bool = True
    ai_shadow_model_enabled: bool = False

    # --- Part 06: Automation Execution & Approval ---
    # Execution is DISABLED by default. Enable explicitly in non-production,
    # and always start with MODE_1_MANUAL.
    execution_enabled: bool = False
    execution_mode: str = "manual"  # observe | manual | guarded_auto
    execution_global_kill_switch: bool = False
    execution_max_actions_per_hour: int = 10
    execution_max_actions_per_day: int = 30
    execution_default_approval_expiry_hours: int = 4
    execution_max_budget_increase_pct: float = 20.0
    execution_max_budget_decrease_pct: float = 20.0
    execution_max_daily_cumulative_budget_change_pct: float = 30.0
    execution_default_cooldown_hours: int = 24
    execution_auto_compensation: bool = False
    execution_two_person_approval: bool = False
    execution_shadow_mode: bool = False
    execution_verification_retry_seconds: str = "2,5,10"
    execution_verification_failure_auto_kill_threshold: int = 3
    execution_unknown_outcome_auto_kill_threshold: int = 3
    execution_auto_kill_window_minutes: int = 10
    execution_resource_lock_ttl_seconds: int = 300
    execution_queue: str = "execution"
    execution_compensation_queue: str = "compensation"
    execution_worker_concurrency: int = 2
    execution_audit_retention_days: int = 730

    # Meta write credentials (execution worker only; never shared with readers)
    meta_write_enabled: bool = False
    meta_write_credential_reference: str = ""
    meta_write_access_token: str = ""

    # Google Ads write credentials (execution worker only)
    google_ads_write_enabled: bool = False
    google_ads_write_credential_reference: str = ""
    google_ads_validate_only_first: bool = True
    google_ads_partial_failure: bool = False

    # Live write test safety: explicit opt-in, refused in production
    allow_live_execution_tests: bool = False
    # Demo-mode permission bypass (must be false in production deployments)
    execution_demo_permissions: bool = True
    oauth_redirect_allowlist: str = ""
    otel_enabled: bool = False
    otel_endpoint: str = ""
    metrics_enabled: bool = True
    maintenance_mode: bool = False

    # --- Part 06-01: Multi-account / Social / Content Intelligence ---
    social_provider_mode: str = "mock"  # mock | live
    # Instagram Growth Intelligence uses META_GRAPH_API_VERSION through
    # meta_graph_api_version; the legacy field below remains for the old
    # generic adapter until Phase 6 replaces it.
    instagram_sync_enabled: bool = False
    instagram_demo_mode: bool = True
    instagram_calculation_version: str = "instagram-v1.0"
    instagram_default_window_days: int = 28
    instagram_content_history_days: int = 90
    # Instagram Growth Intelligence live connector (server-side only).
    # The OAuth/token exchange is intentionally separate from the DEMO fixture.
    instagram_oauth_mode: str = "instagram_login"  # instagram_login | facebook_login
    instagram_app_id: str = ""
    instagram_app_secret_reference: str = "env:INSTAGRAM_APP_SECRET"
    # OAuth tokens are encrypted before persistence.  The reference points to a
    # server-side key only; it is never returned by any API endpoint.
    instagram_token_encryption_key_reference: str = "env:INSTAGRAM_TOKEN_ENCRYPTION_KEY"
    instagram_access_token_reference: str = "env:INSTAGRAM_ACCESS_TOKEN"
    instagram_required_scopes: str = "instagram_business_basic,instagram_business_manage_insights"
    instagram_oauth_redirect_uri: str = "http://127.0.0.1:8000/api/v1/connections/instagram/oauth/callback"
    instagram_oauth_state_ttl_minutes: int = 10
    instagram_graph_api_base_url: str = "https://graph.instagram.com"
    instagram_oauth_base_url: str = "https://www.instagram.com"
    instagram_token_exchange_url: str = "https://api.instagram.com/oauth/access_token"
    instagram_sync_max_media: int = 100
    instagram_api_version: str = "v22.0"
    instagram_access_token: str = ""
    tiktok_api_version: str = "v2"
    tiktok_access_token: str = ""
    youtube_api_version: str = "v3"
    youtube_api_key: str = ""
    focus_default_refresh_minutes: int = 15
    focus_default_priority: str = "NORMAL"
    focus_max_monitors_per_workspace: int = 50
    content_snapshot_retention_days: int = 730
    social_backfill_days: int = 90
    social_sync_interval_minutes: int = 30

    @field_validator("adspower_base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def cors_origin_list(self) -> list:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _validate_environment(self):
        if self.app_env not in ("local", "test", "staging", "production"):
            raise ValueError(f"APP_ENV must be one of local|test|staging|production, got {self.app_env!r}")
        if self.app_env in ("staging", "production"):
            if self.execution_demo_permissions:
                raise ValueError("EXECUTION_DEMO_PERMISSIONS must be false in staging/production")
            if self.secret_key == "dev-only-change-me":
                raise ValueError("SECRET_KEY must be overridden in staging/production")
            if self.app_env == "production" and self.execution_mode != "manual":
                raise ValueError("production default requires EXECUTION_MODE=manual")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
