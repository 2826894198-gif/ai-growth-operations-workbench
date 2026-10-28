"""Instagram Growth Intelligence V1 raw and derived storage.

Revision ID: 0012_instagram_growth_intelligence
Revises: 0011_detection_workflow_settings
Create Date: 2026-08-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_instagram_growth_intelligence"
down_revision: Union[str, None] = "0011_detection_workflow_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "instagram_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("metric_key", sa.String(128), nullable=False),
        sa.Column("metric_level", sa.String(32), nullable=False),
        sa.Column("media_type", sa.String(64), nullable=True),
        sa.Column("scope_key", sa.String(255), nullable=False),
        sa.Column("supported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("permission_granted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(32), nullable=True),
        sa.Column("provider_field", sa.String(255), nullable=True),
        sa.Column("provider_version", sa.String(64), nullable=True),
        sa.Column("last_checked_at", UTC, nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.CheckConstraint(
            "reason IS NULL OR reason IN ('available', 'unavailable', 'unsupported', 'permission_denied', 'empty')",
            name="ck_instagram_capability_reason",
        ),
    )
    op.create_index("ix_instagram_capabilities_account", "instagram_capabilities", ["account_id"])
    op.create_index(
        "ix_instagram_capabilities_account_level",
        "instagram_capabilities",
        ["account_id", "metric_level"],
    )
    op.create_unique_constraint(
        "uq_instagram_capability_scope",
        "instagram_capabilities",
        ["account_id", "scope_key"],
    )

    op.create_table(
        "instagram_account_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("observed_at", UTC, nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("source_layer", sa.String(32), nullable=False, server_default="RAW"),
        sa.Column("source_mode", sa.String(16), nullable=False, server_default="DEMO"),
        sa.Column("api_version", sa.String(64), nullable=False),
        sa.Column("raw_payload_id", sa.String(36), sa.ForeignKey("raw_api_payloads.id"), nullable=False),
        sa.Column("timezone", sa.String(128), nullable=False, server_default="UTC"),
        sa.Column("metrics", JSONB, nullable=False),
        sa.Column("metric_availability", JSONB, nullable=False),
        sa.Column("record_status", sa.String(32), nullable=False, server_default="COMPLETE"),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.CheckConstraint("source_layer = 'RAW'", name="ck_instagram_account_snapshot_raw_layer"),
        sa.CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_account_snapshot_source_mode"),
    )
    op.create_index("ix_instagram_account_snapshots_account", "instagram_account_snapshots", ["account_id"])
    op.create_index("ix_instagram_account_snapshots_observed", "instagram_account_snapshots", ["observed_at"])
    op.create_index(
        "ix_instagram_account_snapshots_window",
        "instagram_account_snapshots",
        ["account_id", "window_start", "window_end"],
    )
    op.create_index(
        "ix_instagram_account_snapshots_source",
        "instagram_account_snapshots",
        ["source_mode", "source_layer"],
    )
    op.create_unique_constraint(
        "uq_instagram_account_snapshot_dedupe",
        "instagram_account_snapshots",
        ["dedupe_key"],
    )

    op.create_table(
        "instagram_media_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("content_publications.id"), nullable=True),
        sa.Column("external_media_id", sa.String(255), nullable=False),
        sa.Column("observed_at", UTC, nullable=False),
        sa.Column("media_type", sa.String(64), nullable=False),
        sa.Column("source_layer", sa.String(32), nullable=False, server_default="RAW"),
        sa.Column("source_mode", sa.String(16), nullable=False, server_default="DEMO"),
        sa.Column("api_version", sa.String(64), nullable=False),
        sa.Column("raw_payload_id", sa.String(36), sa.ForeignKey("raw_api_payloads.id"), nullable=False),
        sa.Column("metrics", JSONB, nullable=False),
        sa.Column("metric_availability", JSONB, nullable=False),
        sa.Column("record_status", sa.String(32), nullable=False, server_default="COMPLETE"),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.CheckConstraint("source_layer = 'RAW'", name="ck_instagram_media_snapshot_raw_layer"),
        sa.CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_media_snapshot_source_mode"),
    )
    op.create_index("ix_instagram_media_snapshots_account", "instagram_media_snapshots", ["account_id"])
    op.create_index("ix_instagram_media_snapshots_publication", "instagram_media_snapshots", ["publication_id"])
    op.create_index("ix_instagram_media_snapshots_external", "instagram_media_snapshots", ["external_media_id"])
    op.create_index("ix_instagram_media_snapshots_observed", "instagram_media_snapshots", ["observed_at"])
    op.create_index("ix_instagram_media_snapshots_type", "instagram_media_snapshots", ["media_type"])
    op.create_index(
        "ix_instagram_media_snapshots_source",
        "instagram_media_snapshots",
        ["source_mode", "source_layer"],
    )
    op.create_unique_constraint(
        "uq_instagram_media_snapshot_observation",
        "instagram_media_snapshots",
        ["account_id", "external_media_id", "observed_at", "source_mode"],
    )
    op.create_unique_constraint(
        "uq_instagram_media_snapshot_dedupe",
        "instagram_media_snapshots",
        ["dedupe_key"],
    )

    op.create_table(
        "instagram_derived_metric_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_ref", sa.String(255), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=True),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("content_publications.id"), nullable=True),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("source_mode", sa.String(16), nullable=False),
        sa.Column("source_layer", sa.String(32), nullable=False, server_default="DERIVED"),
        sa.Column("metrics", JSONB, nullable=False),
        sa.Column("metric_availability", JSONB, nullable=False),
        sa.Column("input_metric_keys", JSONB, nullable=False),
        sa.Column("input_snapshot_refs", JSONB, nullable=False),
        sa.Column("calculation_version", sa.String(64), nullable=False),
        sa.Column("baseline_ref", sa.String(255), nullable=True),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.CheckConstraint("source_layer = 'DERIVED'", name="ck_instagram_derived_metric_derived_layer"),
        sa.CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_derived_metric_source_mode"),
    )
    op.create_index(
        "ix_instagram_derived_subject_window",
        "instagram_derived_metric_snapshots",
        ["subject_type", "subject_ref", "window_start", "window_end"],
    )
    op.create_index("ix_instagram_derived_account", "instagram_derived_metric_snapshots", ["account_id"])
    op.create_index(
        "ix_instagram_derived_publication",
        "instagram_derived_metric_snapshots",
        ["publication_id"],
    )
    op.create_index(
        "ix_instagram_derived_calculation_version",
        "instagram_derived_metric_snapshots",
        ["calculation_version"],
    )
    op.create_unique_constraint(
        "uq_instagram_derived_metric_snapshot_dedupe",
        "instagram_derived_metric_snapshots",
        ["dedupe_key"],
    )

    op.create_table(
        "instagram_sync_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=True),
        sa.Column("run_type", sa.String(64), nullable=False),
        sa.Column("source_mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="RUNNING"),
        sa.Column("requested_window_start", sa.Date(), nullable=True),
        sa.Column("requested_window_end", sa.Date(), nullable=True),
        sa.Column("started_at", UTC, nullable=False),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("items_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_payloads_written", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_instagram_sync_runs_workspace", "instagram_sync_runs", ["workspace_id"])
    op.create_index("ix_instagram_sync_runs_account", "instagram_sync_runs", ["account_id"])
    op.create_index("ix_instagram_sync_runs_status", "instagram_sync_runs", ["status"])


def downgrade() -> None:
    op.drop_table("instagram_sync_runs")
    op.drop_table("instagram_derived_metric_snapshots")
    op.drop_table("instagram_media_snapshots")
    op.drop_table("instagram_account_snapshots")
    op.drop_table("instagram_capabilities")
