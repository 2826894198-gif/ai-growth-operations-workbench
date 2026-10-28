"""PART 06-01: multi-account, content intelligence & connection center schema

Revision ID: 0007_part0601_social
Revises: 0006_part06_execution
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_part0601_social"
down_revision: Union[str, None] = "0006_part06_execution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("default_timezone", sa.String(128), nullable=False, server_default="America/New_York"),
        sa.Column("reporting_currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_brands_workspace", "brands", ["workspace_id"])
    op.create_index("ix_brands_slug", "brands", ["slug"])
    op.create_unique_constraint("uq_brand_workspace_slug", "brands", ["workspace_id", "slug"])

    op.create_table(
        "account_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), sa.ForeignKey("brands.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_account_groups_workspace", "account_groups", ["workspace_id"])
    op.create_index("ix_account_groups_brand", "account_groups", ["brand_id"])

    op.create_table(
        "provider_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("connection_type", sa.String(64), nullable=False, server_default="OAUTH"),
        sa.Column("external_identity_id", sa.String(255), nullable=True),
        sa.Column("credential_reference", sa.String(512), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("authorized_scopes", JSONB, nullable=True),
        sa.Column("token_expires_at", UTC, nullable=True),
        sa.Column("last_validated_at", UTC, nullable=True),
        sa.Column("last_refreshed_at", UTC, nullable=True),
        sa.Column("app_id_reference", sa.String(255), nullable=True),
        sa.Column("webhook_status", sa.String(32), nullable=True),
        sa.Column("webhook_last_event_at", UTC, nullable=True),
        sa.Column("webhook_failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rate_limit_status", sa.String(32), nullable=True),
        sa.Column("rate_limit_retry_after", sa.Integer(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_provider_connections_workspace", "provider_connections", ["workspace_id"])
    op.create_index("ix_provider_connections_provider", "provider_connections", ["provider"])
    op.create_index("ix_provider_connections_identity", "provider_connections", ["external_identity_id"])
    op.create_index("ix_provider_connections_status", "provider_connections", ["status"])

    op.create_table(
        "connected_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), sa.ForeignKey("brands.id"), nullable=True),
        sa.Column("account_group_id", sa.String(36), sa.ForeignKey("account_groups.id"), nullable=True),
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("provider_connections.id"), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("account_type", sa.String(64), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=False),
        sa.Column("external_parent_id", sa.String(255), nullable=True),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("profile_url", sa.String(512), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("country", sa.String(8), nullable=True),
        sa.Column("timezone", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="LINKED"),
        sa.Column("health_status", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_profile_sync_at", UTC, nullable=True),
        sa.Column("last_content_sync_at", UTC, nullable=True),
        sa.Column("last_analytics_sync_at", UTC, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_connected_accounts_workspace", "connected_accounts", ["workspace_id"])
    op.create_index("ix_connected_accounts_brand", "connected_accounts", ["brand_id"])
    op.create_index("ix_connected_accounts_group", "connected_accounts", ["account_group_id"])
    op.create_index("ix_connected_accounts_connection", "connected_accounts", ["connection_id"])
    op.create_index("ix_connected_accounts_provider", "connected_accounts", ["provider"])
    op.create_index("ix_connected_accounts_platform", "connected_accounts", ["platform"])
    op.create_index("ix_connected_accounts_username", "connected_accounts", ["username"])
    op.create_index("ix_connected_accounts_status", "connected_accounts", ["status"])
    op.create_index("ix_connected_accounts_platform_workspace", "connected_accounts", ["workspace_id", "platform"])
    op.create_unique_constraint("uq_connected_account_external", "connected_accounts", ["workspace_id", "provider", "external_account_id"])

    op.create_table(
        "provider_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(64), nullable=True),
        sa.Column("capability_key", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("default_supported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_permission", sa.String(128), nullable=True),
        sa.Column("provider_version", sa.String(64), nullable=True),
        sa.Column("availability_notes", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_provider_capabilities_provider", "provider_capabilities", ["provider"])
    op.create_index("ix_provider_capabilities_platform", "provider_capabilities", ["platform"])
    op.create_unique_constraint("uq_provider_capability", "provider_capabilities", ["provider", "platform", "capability_key"])

    op.create_table(
        "account_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("capability_key", sa.String(128), nullable=False),
        sa.Column("supported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("permission_granted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider_field", sa.String(255), nullable=True),
        sa.Column("provider_version", sa.String(64), nullable=True),
        sa.Column("last_verified_at", UTC, nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_account_capabilities_account", "account_capabilities", ["account_id"])
    op.create_index("ix_account_capabilities_key", "account_capabilities", ["capability_key"])
    op.create_unique_constraint("uq_account_capability", "account_capabilities", ["account_id", "capability_key"])

    op.create_table(
        "social_metric_catalog",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("metric_key", sa.String(128), nullable=False),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("metric_level", sa.String(32), nullable=False, server_default="CONTENT"),
        sa.Column("aggregation_type", sa.String(32), nullable=False),
        sa.Column("unit", sa.String(64), nullable=True),
        sa.Column("comparable_cross_platform", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("positive_direction", sa.String(8), nullable=False, server_default="UP"),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("provider_metric_name", sa.String(255), nullable=True),
        sa.Column("availability_notes", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_social_metric_catalog_key", "social_metric_catalog", ["metric_key"])
    op.create_unique_constraint("uq_social_metric_key", "social_metric_catalog", ["metric_key", "provider"])

    op.create_table(
        "content_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), sa.ForeignKey("brands.id"), nullable=True),
        sa.Column("asset_type", sa.String(64), nullable=False, server_default="VIDEO"),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("internal_name", sa.String(512), nullable=True),
        sa.Column("source_asset_uri", sa.String(1024), nullable=True),
        sa.Column("thumbnail_uri", sa.String(1024), nullable=True),
        sa.Column("asset_hash", sa.String(128), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("aspect_ratio", sa.String(16), nullable=True),
        sa.Column("created_at_source", UTC, nullable=True),
        sa.Column("owner_user_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_content_assets_workspace", "content_assets", ["workspace_id"])
    op.create_index("ix_content_assets_brand", "content_assets", ["brand_id"])
    op.create_index("ix_content_assets_hash", "content_assets", ["asset_hash"])

    op.create_table(
        "content_publications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("content_asset_id", sa.String(36), sa.ForeignKey("content_assets.id"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("external_post_id", sa.String(255), nullable=False),
        sa.Column("external_media_id", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(64), nullable=False, server_default="VIDEO"),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("published_at", UTC, nullable=True),
        sa.Column("public_url", sa.String(1024), nullable=True),
        sa.Column("provider_status", sa.String(32), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_content_publications_asset", "content_publications", ["content_asset_id"])
    op.create_index("ix_content_publications_account", "content_publications", ["account_id"])
    op.create_index("ix_content_publications_provider", "content_publications", ["provider"])
    op.create_index("ix_content_publications_published", "content_publications", ["published_at"])
    op.create_index("ix_publications_account_published", "content_publications", ["account_id", "published_at"])
    op.create_unique_constraint("uq_publication_external", "content_publications", ["provider", "external_post_id"])

    op.create_table(
        "content_performance_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("content_publications.id"), nullable=False),
        sa.Column("observed_at", UTC, nullable=False),
        sa.Column("views", sa.Float(), nullable=True),
        sa.Column("reach", sa.Float(), nullable=True),
        sa.Column("likes", sa.Float(), nullable=True),
        sa.Column("comments", sa.Float(), nullable=True),
        sa.Column("shares", sa.Float(), nullable=True),
        sa.Column("saves", sa.Float(), nullable=True),
        sa.Column("watch_time", sa.Float(), nullable=True),
        sa.Column("average_watch_time", sa.Float(), nullable=True),
        sa.Column("completion_rate", sa.Float(), nullable=True),
        sa.Column("skip_rate", sa.Float(), nullable=True),
        sa.Column("profile_visits", sa.Float(), nullable=True),
        sa.Column("follows", sa.Float(), nullable=True),
        sa.Column("provider_native_metrics", JSONB, nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="API"),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_content_perf_snapshots_pub", "content_performance_snapshots", ["publication_id"])
    op.create_index("ix_content_perf_snapshots_observed", "content_performance_snapshots", ["observed_at"])
    op.create_index("ix_perf_snapshot_publication_observed", "content_performance_snapshots", ["publication_id", "observed_at"])

    op.create_table(
        "fact_content_performance_daily",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("content_asset_id", sa.String(36), sa.ForeignKey("content_assets.id"), nullable=True),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("content_publications.id"), nullable=False),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("views", sa.Float(), nullable=True),
        sa.Column("reach", sa.Float(), nullable=True),
        sa.Column("likes", sa.Float(), nullable=True),
        sa.Column("comments", sa.Float(), nullable=True),
        sa.Column("shares", sa.Float(), nullable=True),
        sa.Column("saves", sa.Float(), nullable=True),
        sa.Column("watch_time", sa.Float(), nullable=True),
        sa.Column("follows", sa.Float(), nullable=True),
        sa.Column("provider_native_metrics", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_fact_content_daily_workspace", "fact_content_performance_daily", ["workspace_id"])
    op.create_index("ix_fact_content_daily_account", "fact_content_performance_daily", ["account_id"])
    op.create_index("ix_fact_content_daily_asset", "fact_content_performance_daily", ["content_asset_id"])
    op.create_index("ix_fact_content_daily_pub", "fact_content_performance_daily", ["publication_id"])
    op.create_index("ix_fact_content_daily_date", "fact_content_performance_daily", ["date"])
    op.create_unique_constraint("uq_content_perf_daily", "fact_content_performance_daily", ["publication_id", "date"])

    op.create_table(
        "content_promotion_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("content_asset_id", sa.String(36), sa.ForeignKey("content_assets.id"), nullable=False),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("content_publications.id"), nullable=False),
        sa.Column("paid_platform", sa.String(64), nullable=False),
        sa.Column("paid_account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=True),
        sa.Column("creative_id", sa.String(255), nullable=True),
        sa.Column("ad_id", sa.String(255), nullable=True),
        sa.Column("ad_group_id", sa.String(255), nullable=True),
        sa.Column("campaign_id", sa.String(255), nullable=True),
        sa.Column("promotion_type", sa.String(64), nullable=False, server_default="PAID_BOOST"),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("ended_at", UTC, nullable=True),
        sa.Column("mapping_confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("mapping_source", sa.String(64), nullable=False, server_default="MANUAL"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_content_promotion_workspace", "content_promotion_links", ["workspace_id"])
    op.create_index("ix_content_promotion_asset", "content_promotion_links", ["content_asset_id"])
    op.create_index("ix_content_promotion_pub", "content_promotion_links", ["publication_id"])
    op.create_index("ix_content_promotion_paid_account", "content_promotion_links", ["paid_account_id"])
    op.create_index("ix_content_promotion_creative", "content_promotion_links", ["creative_id"])
    op.create_index("ix_content_promotion_ad", "content_promotion_links", ["ad_id"])

    op.create_table(
        "focus_monitors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("scope_type", sa.String(64), nullable=False),
        sa.Column("scope_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("priority", sa.String(32), nullable=False, server_default="NORMAL"),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("rules", JSONB, nullable=True),
        sa.Column("refresh_interval_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("notification_policy", JSONB, nullable=True),
        sa.Column("baseline_strategy", sa.String(64), nullable=False, server_default="PREVIOUS_PERIOD"),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("ends_at", UTC, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_focus_monitors_workspace", "focus_monitors", ["workspace_id"])
    op.create_index("ix_focus_monitors_status", "focus_monitors", ["status"])
    op.create_index("ix_focus_workspace_status", "focus_monitors", ["workspace_id", "status"])

    op.create_table(
        "watchlists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_watchlists_workspace", "watchlists", ["workspace_id"])

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("watchlist_id", sa.String(36), sa.ForeignKey("watchlists.id"), nullable=False),
        sa.Column("focus_monitor_id", sa.String(36), sa.ForeignKey("focus_monitors.id"), nullable=True),
        sa.Column("scope_type", sa.String(64), nullable=False),
        sa.Column("scope_id", sa.String(255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_watchlist_items_list", "watchlist_items", ["watchlist_id"])
    op.create_index("ix_watchlist_items_focus", "watchlist_items", ["focus_monitor_id"])

    op.create_table(
        "saved_scopes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scope", JSONB, nullable=False),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_saved_scopes_workspace", "saved_scopes", ["workspace_id"])

    op.create_table(
        "developer_app_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("app_display_name", sa.String(255), nullable=False),
        sa.Column("client_id_reference", sa.String(512), nullable=True),
        sa.Column("secret_reference", sa.String(512), nullable=True),
        sa.Column("redirect_uri", sa.String(512), nullable=True),
        sa.Column("approval_status", sa.String(32), nullable=False, server_default="NOT_CONFIGURED"),
        sa.Column("scopes", JSONB, nullable=True),
        sa.Column("environment", sa.String(32), nullable=False, server_default="SANDBOX"),
        sa.Column("last_validation", UTC, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_developer_apps_workspace", "developer_app_configs", ["workspace_id"])
    op.create_index("ix_developer_apps_provider", "developer_app_configs", ["provider"])

    op.create_table(
        "connection_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("connection_id", sa.String(36), nullable=True),
        sa.Column("account_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("before", JSONB, nullable=True),
        sa.Column("after", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_connection_audits_workspace", "connection_audits", ["workspace_id"])
    op.create_index("ix_connection_audits_connection", "connection_audits", ["connection_id"])
    op.create_index("ix_connection_audits_account", "connection_audits", ["account_id"])
    op.create_index("ix_connection_audits_action", "connection_audits", ["action"])


def downgrade() -> None:
    for table in (
        "connection_audits",
        "developer_app_configs",
        "saved_scopes",
        "watchlist_items",
        "watchlists",
        "focus_monitors",
        "content_promotion_links",
        "fact_content_performance_daily",
        "content_performance_snapshots",
        "content_publications",
        "content_assets",
        "social_metric_catalog",
        "account_capabilities",
        "provider_capabilities",
        "connected_accounts",
        "provider_connections",
        "account_groups",
        "brands",
    ):
        op.drop_table(table)
