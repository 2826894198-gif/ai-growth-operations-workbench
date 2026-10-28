"""Part 05: growth dashboard product schema

Revision ID: 0005_part05_product
Revises: 0004_part04_ai_intelligence
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_part05_product"
down_revision: Union[str, None] = "0004_part04_ai_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(128), nullable=False, server_default="America/New_York"),
        sa.Column("reporting_currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )

    op.create_table(
        "feature_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("flag_key", sa.String(64), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rollout_pct", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="MEDIUM"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("recommendation_id", sa.String(36), nullable=True),
        sa.Column("read_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_notifications_user", "notifications", ["user_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])

    op.create_table(
        "user_dashboard_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, unique=True),
        sa.Column("default_workspace_id", sa.String(36), nullable=True),
        sa.Column("default_date_range", sa.String(32), nullable=False, server_default="LAST_7_DAYS"),
        sa.Column("default_comparison", sa.String(32), nullable=False, server_default="PREVIOUS_PERIOD"),
        sa.Column("density", sa.String(16), nullable=False, server_default="COMPACT"),
        sa.Column("theme", sa.String(16), nullable=False, server_default="DARK"),
        sa.Column("table_columns", JSONB, nullable=True),
        sa.Column("saved_filters", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )

    op.create_table(
        "creative_briefs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("first_3_seconds", sa.Text(), nullable=True),
        sa.Column("scene_sequence", JSONB, nullable=True),
        sa.Column("product_actions", JSONB, nullable=True),
        sa.Column("proof", JSONB, nullable=True),
        sa.Column("cta", sa.String(255), nullable=True),
        sa.Column("audio_direction", sa.Text(), nullable=True),
        sa.Column("duration", sa.String(32), nullable=True),
        sa.Column("aspect_ratio", sa.String(32), nullable=True),
        sa.Column("avoid", JSONB, nullable=True),
        sa.Column("measurement_plan", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("evidence_refs", JSONB, nullable=True),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_creative_briefs_status", "creative_briefs", ["status"])

    op.create_table(
        "experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("variable", sa.String(255), nullable=True),
        sa.Column("control", sa.Text(), nullable=True),
        sa.Column("treatment", sa.Text(), nullable=True),
        sa.Column("primary_metric", sa.String(128), nullable=True),
        sa.Column("guardrail_metrics", JSONB, nullable=True),
        sa.Column("start_at", UTC, nullable=True),
        sa.Column("end_at", UTC, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PLANNED"),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("learnings", JSONB, nullable=True),
        sa.Column("protected_by_rule", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("scope_type", sa.String(32), nullable=True),
        sa.Column("scope_id", sa.String(255), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_experiments_status", "experiments", ["status"])

    op.create_table(
        "saved_views",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("filters", JSONB, nullable=True),
        sa.Column("columns", JSONB, nullable=True),
        sa.Column("route", sa.String(255), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_saved_views_user", "saved_views", ["user_id"])


def downgrade() -> None:
    for table in (
        "saved_views",
        "experiments",
        "creative_briefs",
        "user_dashboard_preferences",
        "notifications",
        "feature_flags",
        "workspaces",
    ):
        op.drop_table(table)
