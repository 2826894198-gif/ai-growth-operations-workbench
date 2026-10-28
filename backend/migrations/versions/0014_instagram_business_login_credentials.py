"""Encrypted credentials for Instagram Business Login.

Revision ID: 0014_instagram_business_login_credentials
Revises: 0013_instagram_health_rules
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_instagram_business_login_credentials"
down_revision: Union[str, None] = "0013_instagram_health_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "instagram_oauth_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("provider_connections.id"), nullable=False),
        sa.Column("key_version", sa.String(64), nullable=False, server_default="instagram-token-v1"),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("token_type", sa.String(64), nullable=True),
        sa.Column("expires_at", UTC, nullable=True),
        sa.Column("granted_scopes", JSONB, nullable=True),
        sa.Column("revoked_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("connection_id", name="uq_instagram_oauth_credentials_connection"),
    )
    op.create_index("ix_instagram_oauth_credentials_connection", "instagram_oauth_credentials", ["connection_id"])
    op.create_index("ix_instagram_oauth_credentials_expires", "instagram_oauth_credentials", ["expires_at"])


def downgrade() -> None:
    op.drop_table("instagram_oauth_credentials")
