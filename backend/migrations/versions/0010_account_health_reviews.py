"""Account health and review center.

Revision ID: 0010_account_health_reviews
Revises: 0009_production_hardening
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_account_health_reviews"
down_revision: Union[str, None] = "0009_production_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    # Expand first: old writers may continue omitting workspace_id during rollout.
    op.add_column("data_sources", sa.Column("workspace_id", sa.String(36), nullable=True))
    op.create_index("ix_data_sources_workspace_id", "data_sources", ["workspace_id"])
    op.execute("UPDATE data_sources SET workspace_id = 'ws_main' WHERE workspace_id IS NULL")

    op.create_table(
        "account_health_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("evaluated_at", UTC, nullable=False),
        sa.Column("connection_status", sa.String(32), nullable=False),
        sa.Column("data_status", sa.String(32), nullable=False),
        sa.Column("performance_status", sa.String(32), nullable=False),
        sa.Column("content_status", sa.String(32), nullable=False),
        sa.Column("overall_status", sa.String(32), nullable=False),
        sa.Column("data_usable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rule_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("summary", JSONB, nullable=True),
    )
    op.create_index("ix_health_snapshots_workspace", "account_health_snapshots", ["workspace_id"])
    op.create_index("ix_health_snapshots_account", "account_health_snapshots", ["account_id"])
    op.create_index("ix_health_snapshots_evaluated", "account_health_snapshots", ["evaluated_at"])
    op.create_index("ix_health_snapshots_overall", "account_health_snapshots", ["overall_status"])

    op.create_table(
        "account_health_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("rule_code", sa.String(128), nullable=False),
        sa.Column("rule_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("detected_at", UTC, nullable=False),
        sa.Column("resolved_at", UTC, nullable=True),
        sa.Column("observed_value", sa.String(255), nullable=True),
        sa.Column("baseline_value", sa.String(255), nullable=True),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("owner_id", sa.String(128), nullable=True),
        sa.Column("acknowledged_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    for name, columns in (
        ("ix_health_events_workspace", ["workspace_id"]),
        ("ix_health_events_account", ["account_id"]),
        ("ix_health_events_rule", ["rule_code"]),
        ("ix_health_events_severity", ["severity"]),
        ("ix_health_events_status", ["status"]),
    ):
        op.create_index(name, "account_health_events", columns)

    op.create_table(
        "review_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("review_type", sa.String(32), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("baseline_start", sa.Date(), nullable=False),
        sa.Column("baseline_end", sa.Date(), nullable=False),
        sa.Column("scope", JSONB, nullable=False),
        sa.Column("data_status", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("metric_snapshot", JSONB, nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("caveats", JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="operator"),
        sa.Column("locked_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    for name, columns in (
        ("ix_review_runs_workspace", ["workspace_id"]),
        ("ix_review_runs_type", ["review_type"]),
        ("ix_review_runs_data_status", ["data_status"]),
        ("ix_review_runs_status", ["status"]),
    ):
        op.create_index(name, "review_runs", columns)

    op.create_table(
        "review_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("review_runs.id"), nullable=False),
        sa.Column("finding_type", sa.String(32), nullable=False, server_default="OBSERVATION"),
        sa.Column("severity", sa.String(32), nullable=False, server_default="INFO"),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("health_event_id", sa.String(36), sa.ForeignKey("account_health_events.id"), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_review_findings_review", "review_findings", ["review_id"])

    op.create_table(
        "review_followups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("review_runs.id"), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("owner_id", sa.String(128), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_review_followups_review", "review_followups", ["review_id"])
    op.create_index("ix_review_followups_workspace", "review_followups", ["workspace_id"])
    op.create_index("ix_review_followups_status", "review_followups", ["status"])


def downgrade() -> None:
    for table in (
        "review_followups",
        "review_findings",
        "review_runs",
        "account_health_events",
        "account_health_snapshots",
    ):
        op.drop_table(table)
    op.drop_index("ix_data_sources_workspace_id", table_name="data_sources")
    op.drop_column("data_sources", "workspace_id")
