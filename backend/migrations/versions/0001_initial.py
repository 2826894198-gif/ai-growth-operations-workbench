"""initial schema for Part 01

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "proxies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("proxy_type", sa.String(16), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username_encrypted", sa.String(2048), nullable=False, server_default=""),
        sa.Column("password_encrypted", sa.String(2048), nullable=False, server_default=""),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("region", sa.String(128), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("is_static", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("last_ip", sa.String(64), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_proxies_status", "proxies", ["status"])

    op.create_table(
        "browser_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="adspower"),
        sa.Column("provider_profile_id", sa.String(128), nullable=True, unique=True),
        sa.Column("profile_no", sa.String(128), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("profile_type", sa.String(32), nullable=False),
        sa.Column("platform", sa.String(64), nullable=True),
        sa.Column("proxy_id", sa.String(36), sa.ForeignKey("proxies.id"), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("region", sa.String(128), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("timezone", sa.String(128), nullable=True),
        sa.Column("language", sa.String(64), nullable=True),
        sa.Column("browser_engine", sa.String(32), nullable=True),
        sa.Column("os_type", sa.String(32), nullable=True),
        sa.Column("fingerprint_config", JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="INACTIVE"),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_browser_profiles_profile_type", "browser_profiles", ["profile_type"])
    op.create_index("ix_browser_profiles_status", "browser_profiles", ["status"])

    op.create_table(
        "browser_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("browser_profiles.id"), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column("log_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_browser_tasks_profile_id", "browser_tasks", ["profile_id"])
    op.create_index("ix_browser_tasks_status", "browser_tasks", ["status"])

    op.create_table(
        "environment_health_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("browser_profiles.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("public_ip", sa.String(64), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("timezone", sa.String(128), nullable=True),
        sa.Column("language", sa.String(128), nullable=True),
        sa.Column("proxy_latency_ms", sa.Integer(), nullable=True),
        sa.Column("browser_launch_ms", sa.Integer(), nullable=True),
        sa.Column("checks", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_environment_health_checks_profile_id", "environment_health_checks", ["profile_id"])
    op.create_index("ix_environment_health_checks_created_at", "environment_health_checks", ["created_at"])

    op.create_table(
        "browser_profile_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("browser_profiles.id"), nullable=False),
        sa.Column("field", sa.String(128), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("operator", sa.String(64), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_browser_profile_audits_profile_id", "browser_profile_audits", ["profile_id"])


def downgrade() -> None:
    op.drop_table("browser_profile_audits")
    op.drop_table("environment_health_checks")
    op.drop_table("browser_tasks")
    op.drop_table("browser_profiles")
    op.drop_table("proxies")
