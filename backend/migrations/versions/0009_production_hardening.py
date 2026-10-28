"""PART 07 production hardening — oauth transactions, browser nodes, releases,
retention policies.

Revision ID: 0009_production_hardening
Revises: 0008_governance_optimization
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_production_hardening"
down_revision: Union[str, None] = "0008_governance_optimization"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "oauth_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("state_hash", sa.String(128), nullable=False),
        sa.Column("pkce_verifier_reference", sa.String(512), nullable=True),
        sa.Column("redirect_uri", sa.String(512), nullable=False),
        sa.Column("initiated_by", sa.String(128), nullable=True),
        sa.Column("expires_at", UTC, nullable=False),
        sa.Column("consumed_at", UTC, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_oauth_transactions_workspace", "oauth_transactions", ["workspace_id"])
    op.create_index("ix_oauth_transactions_provider", "oauth_transactions", ["provider"])
    op.create_index("ix_oauth_transactions_status", "oauth_transactions", ["status"])
    op.create_index("uq_oauth_state_hash", "oauth_transactions", ["state_hash"], unique=True)

    op.create_table(
        "browser_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="OFFLINE"),
        sa.Column("allowed_workspace_ids", JSONB, nullable=True),
        sa.Column("last_heartbeat_at", UTC, nullable=True),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("credential_reference", sa.String(512), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_browser_nodes_status", "browser_nodes", ["status"])

    op.create_table(
        "releases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("git_sha", sa.String(64), nullable=False),
        sa.Column("image_digests", JSONB, nullable=True),
        sa.Column("db_revision", sa.String(64), nullable=True),
        sa.Column("deployed_by", sa.String(128), nullable=True),
        sa.Column("deployed_at", UTC, nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("rollback_from", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_releases_version", "releases", ["version"])
    op.create_index("ix_releases_environment", "releases", ["environment"])

    op.create_table(
        "retention_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("archive_after_days", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(32), nullable=False, server_default="DELETE"),
        sa.Column("pii", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_retention_policies_category", "retention_policies", ["category"], unique=True)


def downgrade() -> None:
    for table in ("retention_policies", "releases", "browser_nodes", "oauth_transactions"):
        op.drop_table(table)
