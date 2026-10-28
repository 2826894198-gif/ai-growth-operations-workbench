"""Detection workflow settings and workspace-scoped business targets.

Revision ID: 0011_detection_workflow_settings
Revises: 0010_account_health_reviews
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_detection_workflow_settings"
down_revision: Union[str, None] = "0010_account_health_reviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    # Expand/contract: legacy rows remain readable while all current rows are
    # backfilled into the primary workspace.
    op.add_column("business_target_profiles", sa.Column("workspace_id", sa.String(36), nullable=True))
    op.create_index(
        "ix_business_target_profiles_workspace_id",
        "business_target_profiles",
        ["workspace_id"],
    )
    op.execute(
        "UPDATE business_target_profiles SET workspace_id = 'ws_main' "
        "WHERE workspace_id IS NULL"
    )

    op.create_table(
        "account_detection_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False, unique=True),
        sa.Column("sync_delay_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("sync_stale_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("content_inactive_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index(
        "ix_account_detection_settings_workspace_id",
        "account_detection_settings",
        ["workspace_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("account_detection_settings")
    op.drop_index(
        "ix_business_target_profiles_workspace_id",
        table_name="business_target_profiles",
    )
    op.drop_column("business_target_profiles", "workspace_id")
