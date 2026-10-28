"""Part 02: data platform schema

Revision ID: 0002_part02_data_platform
Revises: 0001_initial
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_part02_data_platform"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
NUM = sa.Numeric(20, 8)
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    # ---------------------------------------------------------------- system
    op.create_table(
        "data_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=True),
        sa.Column("external_account_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("api_version", sa.String(32), nullable=True),
        sa.Column("timezone", sa.String(128), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("credential_reference", sa.String(512), nullable=True),
        sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_successful_sync_at", UTC, nullable=True),
        sa.Column("last_failed_sync_at", UTC, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_data_sources_provider", "data_sources", ["provider"])
    op.create_index("ix_data_sources_status", "data_sources", ["status"])

    op.create_table(
        "raw_api_payloads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("endpoint", sa.String(512), nullable=False),
        sa.Column("api_version", sa.String(32), nullable=True),
        sa.Column("request_hash", sa.String(128), nullable=True),
        sa.Column("request_metadata", JSONB, nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("fetched_at", UTC, nullable=False),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_raw_api_payloads_provider", "raw_api_payloads", ["provider"])
    op.create_index("ix_raw_api_payloads_source", "raw_api_payloads", ["data_source_id"])
    op.create_index("ix_raw_api_payloads_fetched", "raw_api_payloads", ["fetched_at"])
    op.create_index("ix_raw_api_payloads_hash", "raw_api_payloads", ["request_hash"])

    op.create_table(
        "raw_webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("delivery_id", sa.String(128), nullable=False),
        sa.Column("topic", sa.String(128), nullable=True),
        sa.Column("shop_domain", sa.String(255), nullable=True),
        sa.Column("api_version", sa.String(32), nullable=True),
        sa.Column("headers_metadata", JSONB, nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("received_at", UTC, nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("provider", "delivery_id", name="uq_webhook_delivery"),
    )

    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("range_start", sa.String(32), nullable=True),
        sa.Column("range_end", sa.String(32), nullable=True),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("records_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("api_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("error_message", sa.String(4000), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_sync_jobs_source_status", "sync_jobs", ["data_source_id", "status"])
    op.create_index("ix_sync_jobs_created_at", "sync_jobs", ["created_at"])

    op.create_table(
        "sync_cursors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("cursor_type", sa.String(32), nullable=False, server_default="updated_at"),
        sa.Column("cursor_value", sa.String(512), nullable=True),
        sa.Column("watermark_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "resource_type", "cursor_type", name="uq_sync_cursor_grain"),
    )

    op.create_table(
        "provider_api_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("window_start", UTC, nullable=False),
        sa.Column("window_end", UTC, nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rate_limit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_provider_api_usage_provider", "provider_api_usage", ["provider"])

    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("rule_code", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="WARNING"),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("context", JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("resolved_at", UTC, nullable=True),
    )
    op.create_index("ix_dq_source", "data_quality_issues", ["data_source_id"])
    op.create_index("ix_dq_rule", "data_quality_issues", ["rule_code"])
    op.create_index("ix_dq_status", "data_quality_issues", ["status"])

    # ----------------------------------------------------------- dimensions
    op.create_table(
        "dim_marketing_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("timezone", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "external_account_id", name="uq_marketing_account_external"),
    )
    op.create_index("ix_marketing_account_source", "dim_marketing_accounts", ["data_source_id"])

    op.create_table(
        "dim_campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("marketing_account_id", sa.String(36), sa.ForeignKey("dim_marketing_accounts.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("external_campaign_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("objective", sa.String(128), nullable=True),
        sa.Column("channel_type", sa.String(64), nullable=True),
        sa.Column("channel_sub_type", sa.String(64), nullable=True),
        sa.Column("start_at", UTC, nullable=True),
        sa.Column("end_at", UTC, nullable=True),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column("source_created_at", UTC, nullable=True),
        sa.Column("source_updated_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint(
            "platform", "marketing_account_id", "external_campaign_id", name="uq_campaign_platform_external"
        ),
    )
    op.create_index("ix_campaigns_source", "dim_campaigns", ["data_source_id"])
    op.create_index("ix_campaigns_account", "dim_campaigns", ["marketing_account_id"])

    op.create_table(
        "dim_ad_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("dim_campaigns.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_group_type", sa.String(32), nullable=True, server_default="ADSET"),
        sa.Column("external_group_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("optimization_goal", sa.String(128), nullable=True),
        sa.Column("billing_event", sa.String(128), nullable=True),
        sa.Column("daily_budget", NUM, nullable=True),
        sa.Column("lifetime_budget", NUM, nullable=True),
        sa.Column("targeting_metadata", JSONB, nullable=True),
        sa.Column("source_created_at", UTC, nullable=True),
        sa.Column("source_updated_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("campaign_id", "external_group_id", name="uq_ad_group_external"),
    )
    op.create_index("ix_ad_groups_campaign", "dim_ad_groups", ["campaign_id"])

    op.create_table(
        "dim_ads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("dim_campaigns.id"), nullable=False),
        sa.Column("ad_group_id", sa.String(36), sa.ForeignKey("dim_ad_groups.id"), nullable=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("external_ad_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("creative_id", sa.String(255), nullable=True),
        sa.Column("source_created_at", UTC, nullable=True),
        sa.Column("source_updated_at", UTC, nullable=True),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "external_ad_id", name="uq_ad_external"),
    )
    op.create_index("ix_ads_source", "dim_ads", ["data_source_id"])
    op.create_index("ix_ads_campaign", "dim_ads", ["campaign_id"])
    op.create_index("ix_ads_group", "dim_ads", ["ad_group_id"])

    op.create_table(
        "dim_creatives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("external_creative_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("title", sa.String(1000), nullable=True),
        sa.Column("body", sa.String(4000), nullable=True),
        sa.Column("image_url", sa.String(2000), nullable=True),
        sa.Column("thumbnail_url", sa.String(2000), nullable=True),
        sa.Column("video_id", sa.String(255), nullable=True),
        sa.Column("landing_page_url", sa.String(2000), nullable=True),
        sa.Column("cta_type", sa.String(128), nullable=True),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "external_creative_id", name="uq_creative_external"),
    )
    op.create_index("ix_creatives_source", "dim_creatives", ["data_source_id"])

    op.create_table(
        "dim_asset_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("campaign_id", sa.String(36), sa.ForeignKey("dim_campaigns.id"), nullable=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("external_asset_group_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "external_asset_group_id", name="uq_asset_group_external"),
    )
    op.create_index("ix_asset_groups_source", "dim_asset_groups", ["data_source_id"])
    op.create_index("ix_asset_groups_campaign", "dim_asset_groups", ["campaign_id"])

    # --------------------------------------------------------------- facts
    op.create_table(
        "fact_ad_performance_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("marketing_account_id", sa.String(36), sa.ForeignKey("dim_marketing_accounts.id"), nullable=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("external_entity_id", sa.String(255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("impressions", NUM, nullable=True),
        sa.Column("reach", NUM, nullable=True),
        sa.Column("clicks", NUM, nullable=True),
        sa.Column("link_clicks", NUM, nullable=True),
        sa.Column("outbound_clicks", NUM, nullable=True),
        sa.Column("spend_amount", NUM, nullable=True),
        sa.Column("platform_conversions", NUM, nullable=True),
        sa.Column("platform_conversion_value", NUM, nullable=True),
        sa.Column("platform_purchases", NUM, nullable=True),
        sa.Column("platform_purchase_value", NUM, nullable=True),
        sa.Column("cpm", NUM, nullable=True),
        sa.Column("cpc", NUM, nullable=True),
        sa.Column("ctr", NUM, nullable=True),
        sa.Column("frequency", NUM, nullable=True),
        sa.Column("platform_reported_roas", NUM, nullable=True),
        sa.Column("source_attribution_metadata", JSONB, nullable=True),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("source_updated_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint(
            "data_source_id", "entity_type", "external_entity_id", "date", name="uq_perf_daily_grain"
        ),
    )
    op.create_index("ix_perf_platform_date", "fact_ad_performance_daily", ["platform", "date"])
    op.create_index("ix_perf_entity_date", "fact_ad_performance_daily", ["entity_type", "entity_id", "date"])
    op.create_index("ix_perf_source_date", "fact_ad_performance_daily", ["data_source_id", "date"])
    op.create_index("ix_perf_job", "fact_ad_performance_daily", ["sync_job_id"])

    op.create_table(
        "fact_ad_performance_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("external_entity_id", sa.String(255), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=False),
        sa.Column("observed_at", UTC, nullable=False),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("spend_amount", NUM, nullable=True),
        sa.Column("impressions", NUM, nullable=True),
        sa.Column("clicks", NUM, nullable=True),
        sa.Column("platform_purchases", NUM, nullable=True),
        sa.Column("platform_conversion_value", NUM, nullable=True),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_snapshot_source", "fact_ad_performance_snapshots", ["data_source_id"])
    op.create_index("ix_snapshot_date", "fact_ad_performance_snapshots", ["source_date"])
    op.create_index("ix_snapshot_observed", "fact_ad_performance_snapshots", ["observed_at"])
    op.create_unique_constraint("uq_snapshot_grain", "fact_ad_performance_snapshots", [
        "data_source_id", "entity_type", "external_entity_id", "source_date", "observed_at",
    ])

    op.create_table(
        "fact_meta_actions_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_external_id", sa.String(255), nullable=False),
        sa.Column("action_type", sa.String(128), nullable=False),
        sa.Column("action_count", NUM, nullable=True),
        sa.Column("action_value", NUM, nullable=True),
        sa.Column("cost_per_action", NUM, nullable=True),
        sa.Column("attribution_setting", sa.String(64), nullable=True),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint(
            "data_source_id", "entity_type", "entity_external_id", "date", "action_type", "attribution_setting",
            name="uq_meta_action_grain",
        ),
    )
    op.create_index("ix_meta_actions_source", "fact_meta_actions_daily", ["data_source_id"])

    op.create_table(
        "fact_meta_breakdowns_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_external_id", sa.String(255), nullable=False),
        sa.Column("breakdown_dimension", sa.String(64), nullable=False),
        sa.Column("breakdown_value", sa.String(255), nullable=False),
        sa.Column("impressions", NUM, nullable=True),
        sa.Column("clicks", NUM, nullable=True),
        sa.Column("spend_amount", NUM, nullable=True),
        sa.Column("platform_conversions", NUM, nullable=True),
        sa.Column("platform_conversion_value", NUM, nullable=True),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint(
            "data_source_id", "entity_type", "entity_external_id", "date", "breakdown_dimension", "breakdown_value",
            name="uq_meta_breakdown_grain",
        ),
    )
    op.create_index("ix_meta_breakdowns_source", "fact_meta_breakdowns_daily", ["data_source_id"])

    op.create_table(
        "fact_google_keywords_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=True),
        sa.Column("ad_group_id", sa.String(36), nullable=True),
        sa.Column("criterion_id", sa.String(255), nullable=False),
        sa.Column("keyword_text", sa.String(1000), nullable=True),
        sa.Column("match_type", sa.String(64), nullable=True),
        sa.Column("impressions", NUM, nullable=True),
        sa.Column("clicks", NUM, nullable=True),
        sa.Column("cost", NUM, nullable=True),
        sa.Column("conversions", NUM, nullable=True),
        sa.Column("conversion_value", NUM, nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "criterion_id", "date", name="uq_google_keyword_grain"),
    )
    op.create_index("ix_google_keywords_source", "fact_google_keywords_daily", ["data_source_id"])

    op.create_table(
        "fact_google_search_terms_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=True),
        sa.Column("ad_group_id", sa.String(36), nullable=True),
        sa.Column("search_term", sa.String(1000), nullable=False),
        sa.Column("impressions", NUM, nullable=True),
        sa.Column("clicks", NUM, nullable=True),
        sa.Column("cost", NUM, nullable=True),
        sa.Column("conversions", NUM, nullable=True),
        sa.Column("conversion_value", NUM, nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint(
            "data_source_id", "ad_group_id", "search_term", "date", name="uq_google_search_term_grain"
        ),
    )
    op.create_index("ix_google_search_terms_source", "fact_google_search_terms_daily", ["data_source_id"])

    op.create_table(
        "fact_google_conversion_actions_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=True),
        sa.Column("ad_group_id", sa.String(36), nullable=True),
        sa.Column("conversion_action_id", sa.String(255), nullable=False),
        sa.Column("conversion_action_name", sa.String(512), nullable=True),
        sa.Column("conversions", NUM, nullable=True),
        sa.Column("conversion_value", NUM, nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint(
            "data_source_id", "ad_group_id", "conversion_action_id", "date", name="uq_google_conv_action_grain"
        ),
    )
    op.create_index("ix_google_conv_actions_source", "fact_google_conversion_actions_daily", ["data_source_id"])

    op.create_table(
        "dim_products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("external_product_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(1000), nullable=True),
        sa.Column("handle", sa.String(500), nullable=True),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("product_type", sa.String(255), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("source_created_at", UTC, nullable=True),
        sa.Column("source_updated_at", UTC, nullable=True),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "external_product_id", name="uq_product_external"),
    )
    op.create_index("ix_products_source", "dim_products", ["data_source_id"])

    op.create_table(
        "dim_product_variants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("dim_products.id"), nullable=False),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("external_variant_id", sa.String(255), nullable=False),
        sa.Column("external_product_id", sa.String(255), nullable=True),
        sa.Column("sku", sa.String(255), nullable=True),
        sa.Column("title", sa.String(1000), nullable=True),
        sa.Column("price", NUM, nullable=True),
        sa.Column("compare_at_price", NUM, nullable=True),
        sa.Column("inventory_item_id", sa.String(255), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "external_variant_id", name="uq_product_variant_external"),
    )
    op.create_index("ix_variants_product", "dim_product_variants", ["product_id"])
    op.create_index("ix_variants_source", "dim_product_variants", ["data_source_id"])

    op.create_table(
        "fact_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("external_order_id", sa.String(255), nullable=False),
        sa.Column("order_name", sa.String(255), nullable=True),
        sa.Column("order_created_at", UTC, nullable=False),
        sa.Column("order_updated_at", UTC, nullable=True),
        sa.Column("financial_status", sa.String(64), nullable=True),
        sa.Column("fulfillment_status", sa.String(64), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("subtotal_amount", NUM, nullable=True),
        sa.Column("discount_amount", NUM, nullable=True),
        sa.Column("shipping_amount", NUM, nullable=True),
        sa.Column("tax_amount", NUM, nullable=True),
        sa.Column("gross_amount", NUM, nullable=True),
        sa.Column("current_total_amount", NUM, nullable=True),
        sa.Column("refunded_amount", NUM, nullable=True, server_default="0"),
        sa.Column("net_revenue_amount", NUM, nullable=True),
        sa.Column("cancelled_at", UTC, nullable=True),
        sa.Column("source_name", sa.String(128), nullable=True),
        sa.Column("provider_customer_id_hash", sa.String(128), nullable=True),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "external_order_id", name="uq_order_external"),
    )
    op.create_index("ix_orders_source_created", "fact_orders", ["data_source_id", "order_created_at"])

    op.create_table(
        "fact_order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("fact_orders.id"), nullable=False),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("external_line_item_id", sa.String(255), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=True),
        sa.Column("variant_id", sa.String(36), nullable=True),
        sa.Column("sku", sa.String(255), nullable=True),
        sa.Column("title", sa.String(1000), nullable=True),
        sa.Column("quantity", NUM, nullable=True),
        sa.Column("unit_price", NUM, nullable=True),
        sa.Column("line_discount", NUM, nullable=True),
        sa.Column("line_total", NUM, nullable=True),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "external_line_item_id", name="uq_order_item_external"),
    )
    op.create_index("ix_order_items_order", "fact_order_items", ["order_id"])
    op.create_index("ix_order_items_source", "fact_order_items", ["data_source_id"])

    op.create_table(
        "fact_refunds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("fact_orders.id"), nullable=False),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("external_refund_id", sa.String(255), nullable=False),
        sa.Column("refund_created_at", UTC, nullable=True),
        sa.Column("refund_amount", NUM, nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("data_source_id", "external_refund_id", name="uq_refund_external"),
    )
    op.create_index("ix_refunds_order", "fact_refunds", ["order_id"])
    op.create_index("ix_refunds_source", "fact_refunds", ["data_source_id"])

    op.create_table(
        "fact_order_attribution",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("fact_orders.id"), nullable=False),
        sa.Column("journey_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("days_to_conversion", NUM, nullable=True),
        sa.Column("first_source", sa.String(255), nullable=True),
        sa.Column("first_landing_page", sa.String(2000), nullable=True),
        sa.Column("first_referrer_url", sa.String(2000), nullable=True),
        sa.Column("first_utm_source", sa.String(255), nullable=True),
        sa.Column("first_utm_medium", sa.String(255), nullable=True),
        sa.Column("first_utm_campaign", sa.String(255), nullable=True),
        sa.Column("first_utm_content", sa.String(255), nullable=True),
        sa.Column("first_utm_term", sa.String(255), nullable=True),
        sa.Column("last_source", sa.String(255), nullable=True),
        sa.Column("last_landing_page", sa.String(2000), nullable=True),
        sa.Column("last_referrer_url", sa.String(2000), nullable=True),
        sa.Column("last_utm_source", sa.String(255), nullable=True),
        sa.Column("last_utm_medium", sa.String(255), nullable=True),
        sa.Column("last_utm_campaign", sa.String(255), nullable=True),
        sa.Column("last_utm_content", sa.String(255), nullable=True),
        sa.Column("last_utm_term", sa.String(255), nullable=True),
        sa.Column("journey_state", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("fetched_at", UTC, nullable=True),
        sa.Column("raw_metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("order_id", name="uq_order_attribution_order"),
    )
    op.create_index("ix_order_attribution_order", "fact_order_attribution", ["order_id"])

    # ----------------------------------------------------------------- MART
    op.execute(
        """
        CREATE VIEW mart_platform_daily AS
        SELECT date, platform,
               SUM(spend_amount) AS spend,
               SUM(impressions) AS impressions,
               SUM(clicks) AS clicks,
               SUM(platform_conversions) AS platform_conversions,
               SUM(platform_conversion_value) AS platform_conversion_value,
               SUM(platform_purchases) AS platform_purchases,
               SUM(platform_purchase_value) AS platform_purchase_value
        FROM fact_ad_performance_daily
        WHERE entity_type = 'CAMPAIGN'
        GROUP BY date, platform
        """
    )
    op.execute(
        """
        CREATE VIEW mart_campaign_daily AS
        SELECT p.date, p.data_source_id, p.marketing_account_id, p.platform,
               c.external_campaign_id AS campaign_external_id,
               c.name AS campaign_name,
               p.spend_amount, p.impressions, p.clicks,
               p.platform_conversions, p.platform_conversion_value,
               p.platform_purchases, p.platform_purchase_value,
               p.cpm, p.cpc, p.ctr, p.platform_reported_roas
        FROM fact_ad_performance_daily p
        LEFT JOIN dim_campaigns c ON c.id = p.entity_id
        WHERE p.entity_type = 'CAMPAIGN'
        """
    )
    op.execute(
        """
        CREATE VIEW mart_commerce_daily AS
        SELECT DATE(order_created_at) AS date,
               data_source_id,
               COUNT(*) AS orders,
               COALESCE(SUM(gross_amount), 0) AS gross_revenue,
               COALESCE(SUM(discount_amount), 0) AS discounts,
               COALESCE(SUM(refunded_amount), 0) AS refunds,
               COALESCE(SUM(net_revenue_amount), 0) AS net_revenue
        FROM fact_orders
        GROUP BY DATE(order_created_at), data_source_id
        """
    )
    op.execute(
        """
        CREATE VIEW mart_daily_growth_overview AS
        WITH p AS (
            SELECT date,
                   COALESCE(SUM(CASE WHEN platform = 'META_ADS' THEN spend_amount END), 0) AS meta_spend,
                   COALESCE(SUM(CASE WHEN platform = 'GOOGLE_ADS' THEN spend_amount END), 0) AS google_spend,
                   COALESCE(SUM(spend_amount), 0) AS total_paid_spend,
                   COALESCE(SUM(CASE WHEN platform = 'META_ADS' THEN platform_purchase_value END), 0)
                       AS meta_platform_purchase_value,
                   COALESCE(SUM(CASE WHEN platform = 'GOOGLE_ADS' THEN platform_conversion_value END), 0)
                       AS google_platform_conversion_value
            FROM fact_ad_performance_daily
            WHERE entity_type = 'CAMPAIGN'
            GROUP BY date
        ),
        c AS (
            SELECT DATE(order_created_at) AS date,
                   COUNT(*) AS shopify_orders,
                   COALESCE(SUM(gross_amount), 0) AS shopify_gross_revenue,
                   COALESCE(SUM(discount_amount), 0) AS shopify_discounts,
                   COALESCE(SUM(refunded_amount), 0) AS shopify_refunds,
                   COALESCE(SUM(net_revenue_amount), 0) AS shopify_net_revenue
            FROM fact_orders
            GROUP BY 1
        )
        SELECT COALESCE(p.date, c.date) AS date,
               COALESCE(p.meta_spend, 0) AS meta_spend,
               COALESCE(p.google_spend, 0) AS google_spend,
               COALESCE(p.total_paid_spend, 0) AS total_paid_spend,
               COALESCE(c.shopify_orders, 0) AS shopify_orders,
               COALESCE(c.shopify_gross_revenue, 0) AS shopify_gross_revenue,
               COALESCE(c.shopify_discounts, 0) AS shopify_discounts,
               COALESCE(c.shopify_refunds, 0) AS shopify_refunds,
               COALESCE(c.shopify_net_revenue, 0) AS shopify_net_revenue,
               CASE WHEN COALESCE(p.total_paid_spend, 0) > 0
                    THEN c.shopify_net_revenue / p.total_paid_spend END AS blended_roas,
               COALESCE(p.meta_platform_purchase_value, 0) AS meta_platform_purchase_value,
               COALESCE(p.google_platform_conversion_value, 0) AS google_platform_conversion_value
        FROM p
        FULL OUTER JOIN c ON p.date = c.date
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS mart_daily_growth_overview")
    op.execute("DROP VIEW IF EXISTS mart_commerce_daily")
    op.execute("DROP VIEW IF EXISTS mart_campaign_daily")
    op.execute("DROP VIEW IF EXISTS mart_platform_daily")
    for table in (
        "fact_order_attribution",
        "fact_refunds",
        "fact_order_items",
        "fact_orders",
        "dim_product_variants",
        "dim_products",
        "fact_google_conversion_actions_daily",
        "fact_google_search_terms_daily",
        "fact_google_keywords_daily",
        "fact_meta_breakdowns_daily",
        "fact_meta_actions_daily",
        "fact_ad_performance_snapshots",
        "fact_ad_performance_daily",
        "dim_creatives",
        "dim_ads",
        "dim_asset_groups",
        "dim_ad_groups",
        "dim_campaigns",
        "dim_marketing_accounts",
        "data_quality_issues",
        "provider_api_usage",
        "sync_cursors",
        "sync_jobs",
        "raw_webhook_events",
        "raw_api_payloads",
        "data_sources",
    ):
        op.drop_table(table)
