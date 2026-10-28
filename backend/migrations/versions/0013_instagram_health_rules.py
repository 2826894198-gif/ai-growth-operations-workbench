"""Instagram Growth Health and rule event persistence.

Revision ID: 0013_instagram_health_rules
Revises: 0012_instagram_growth_intelligence
Create Date: 2026-08-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_instagram_health_rules"
down_revision: Union[str, None] = "0012_instagram_growth_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "instagram_health_score_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("evaluated_at", UTC, nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("source_mode", sa.String(16), nullable=False),
        sa.Column("source_layer", sa.String(32), nullable=False, server_default="DERIVED"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("dimension_scores", JSONB, nullable=False),
        sa.Column("effective_weights", JSONB, nullable=False),
        sa.Column("missing_dimensions", JSONB, nullable=False),
        sa.Column("data_coverage", sa.Float(), nullable=False),
        sa.Column("sample_factor", sa.Float(), nullable=False),
        sa.Column("freshness_factor", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("confidence_level", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("calculation_version", sa.String(64), nullable=False),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.CheckConstraint("source_layer = 'DERIVED'", name="ck_instagram_health_score_derived_layer"),
        sa.CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_health_score_source_mode"),
    )
    op.create_index("ix_instagram_health_score_workspace", "instagram_health_score_snapshots", ["workspace_id"])
    op.create_index("ix_instagram_health_score_account", "instagram_health_score_snapshots", ["account_id"])
    op.create_index("ix_instagram_health_score_evaluated", "instagram_health_score_snapshots", ["evaluated_at"])
    op.create_index(
        "ix_instagram_health_score_account_window",
        "instagram_health_score_snapshots",
        ["account_id", "window_start", "window_end"],
    )
    op.create_index(
        "ix_instagram_health_score_confidence",
        "instagram_health_score_snapshots",
        ["confidence_level"],
    )
    op.create_unique_constraint(
        "uq_instagram_health_score_dedupe",
        "instagram_health_score_snapshots",
        ["dedupe_key"],
    )

    op.create_table(
        "instagram_rule_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=True),
        sa.Column("publication_id", sa.String(36), sa.ForeignKey("content_publications.id"), nullable=True),
        sa.Column("subject_ref", sa.String(255), nullable=False),
        sa.Column("rule_code", sa.String(128), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("source_mode", sa.String(16), nullable=False),
        sa.Column("source_layer", sa.String(32), nullable=False, server_default="DERIVED"),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("triggered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("severity", sa.String(32), nullable=False, server_default="INFO"),
        sa.Column("detected_at", UTC, nullable=False),
        sa.Column("resolved_at", UTC, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("missing_fields", JSONB, nullable=False),
        sa.Column("evidence", JSONB, nullable=False),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.CheckConstraint("source_layer = 'DERIVED'", name="ck_instagram_rule_event_derived_layer"),
        sa.CheckConstraint("source_mode IN ('DEMO', 'LIVE')", name="ck_instagram_rule_event_source_mode"),
    )
    op.create_index("ix_instagram_rule_events_workspace", "instagram_rule_events", ["workspace_id"])
    op.create_index("ix_instagram_rule_events_account", "instagram_rule_events", ["account_id"])
    op.create_index("ix_instagram_rule_events_publication", "instagram_rule_events", ["publication_id"])
    op.create_index("ix_instagram_rule_events_subject", "instagram_rule_events", ["subject_ref"])
    op.create_index("ix_instagram_rule_events_rule", "instagram_rule_events", ["rule_code"])
    op.create_index("ix_instagram_rule_events_status", "instagram_rule_events", ["status"])
    op.create_index(
        "ix_instagram_rule_events_subject_status",
        "instagram_rule_events",
        ["subject_ref", "status"],
    )
    op.create_index(
        "ix_instagram_rule_events_account_rule",
        "instagram_rule_events",
        ["account_id", "rule_code"],
    )
    op.create_unique_constraint(
        "uq_instagram_rule_event_dedupe",
        "instagram_rule_events",
        ["dedupe_key"],
    )


def downgrade() -> None:
    op.drop_table("instagram_rule_events")
    op.drop_table("instagram_health_score_snapshots")
