"""Part 06: automation execution, approval, revalidation & rollback schema

Revision ID: 0006_part06_execution
Revises: 0005_part05_product
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_part06_execution"
down_revision: Union[str, None] = "0005_part05_product"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "execution_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("recommendation_id", sa.String(36), sa.ForeignKey("recommendations.id"), nullable=False),
        sa.Column("approved_by", sa.String(128), nullable=False),
        sa.Column("approved_at", UTC, nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("external_entity_id", sa.String(255), nullable=True),
        sa.Column("approved_change", JSONB, nullable=False),
        sa.Column("expected_before_state", JSONB, nullable=True),
        sa.Column("expected_before_hash", sa.String(64), nullable=True),
        sa.Column("risk_level", sa.String(32), nullable=False, server_default="MEDIUM"),
        sa.Column("expires_at", UTC, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("approval_hash", sa.String(64), nullable=False),
        sa.Column("revocation_reason", sa.String(255), nullable=True),
        sa.Column("revoked_by", sa.String(128), nullable=True),
        sa.Column("revoked_at", UTC, nullable=True),
        sa.Column("consumed_by_intent_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_execution_approvals_recommendation", "execution_approvals", ["recommendation_id"])
    op.create_index("ix_execution_approvals_provider", "execution_approvals", ["provider"])
    op.create_index("ix_execution_approvals_action", "execution_approvals", ["action_type"])
    op.create_index("ix_execution_approvals_entity", "execution_approvals", ["entity_id"])
    op.create_index("ix_execution_approvals_status", "execution_approvals", ["status"])
    op.create_index("ix_execution_approval_hash", "execution_approvals", ["approval_hash"])

    op.create_table(
        "execution_intents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("recommendation_id", sa.String(36), sa.ForeignKey("recommendations.id"), nullable=False),
        sa.Column("approval_id", sa.String(36), sa.ForeignKey("execution_approvals.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("account_id", sa.String(255), nullable=True),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("external_entity_id", sa.String(255), nullable=True),
        sa.Column("requested_change", JSONB, nullable=False),
        sa.Column("expected_before_state", JSONB, nullable=True),
        sa.Column("expected_before_hash", sa.String(64), nullable=True),
        sa.Column("risk_level", sa.String(32), nullable=False, server_default="MEDIUM"),
        sa.Column("blast_radius", sa.String(32), nullable=True),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approval_expires_at", UTC, nullable=True),
        sa.Column("execution_policy_version", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("execution_group_id", sa.String(36), nullable=True),
        sa.Column("shadow_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("superseded_by_recommendation_id", sa.String(36), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_execution_intents_recommendation", "execution_intents", ["recommendation_id"])
    op.create_index("ix_execution_intents_approval", "execution_intents", ["approval_id"])
    op.create_index("ix_execution_intents_provider", "execution_intents", ["provider"])
    op.create_index("ix_execution_intents_action", "execution_intents", ["action_type"])
    op.create_index("ix_execution_intents_entity", "execution_intents", ["entity_id"])
    op.create_index("ix_execution_intents_status", "execution_intents", ["status"])
    op.create_index("uq_execution_intent_idempotency", "execution_intents", ["idempotency_key"], unique=True)

    op.create_table(
        "execution_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("intent_id", sa.String(36), sa.ForeignKey("execution_intents.id"), nullable=False),
        sa.Column("approval_id", sa.String(36), sa.ForeignKey("execution_approvals.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("external_entity_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_request_id", sa.String(255), nullable=True),
        sa.Column("provider_resource_name", sa.String(255), nullable=True),
        sa.Column("before_state", JSONB, nullable=True),
        sa.Column("requested_state", JSONB, nullable=True),
        sa.Column("after_state", JSONB, nullable=True),
        sa.Column("revalidation_result", sa.String(32), nullable=True),
        sa.Column("provider_validation_result", sa.String(32), nullable=True),
        sa.Column("verification_result", sa.String(32), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("shadow_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_execution_jobs_intent", "execution_jobs", ["intent_id"])
    op.create_index("ix_execution_jobs_approval", "execution_jobs", ["approval_id"])
    op.create_index("ix_execution_jobs_provider", "execution_jobs", ["provider"])
    op.create_index("ix_execution_jobs_action", "execution_jobs", ["action_type"])
    op.create_index("ix_execution_jobs_entity", "execution_jobs", ["entity_id"])
    op.create_index("ix_execution_jobs_status", "execution_jobs", ["status"])

    op.create_table(
        "execution_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_id", sa.String(36), nullable=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("execution_jobs.id"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_data", JSONB, nullable=True),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_execution_events_execution", "execution_events", ["execution_id"])
    op.create_index("ix_execution_events_job", "execution_events", ["job_id"])
    op.create_index("ix_execution_events_type", "execution_events", ["event_type"])
    op.create_index("ix_execution_events_created", "execution_events", ["created_at"])

    op.create_table(
        "execution_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("recommendation_id", sa.String(36), nullable=True),
        sa.Column("approval_id", sa.String(36), nullable=True),
        sa.Column("intent_id", sa.String(36), nullable=True),
        sa.Column("job_id", sa.String(36), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("action_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(255), nullable=True),
        sa.Column("revalidation", JSONB, nullable=True),
        sa.Column("before_state", JSONB, nullable=True),
        sa.Column("provider_request", JSONB, nullable=True),
        sa.Column("provider_response", JSONB, nullable=True),
        sa.Column("after_state", JSONB, nullable=True),
        sa.Column("verification", JSONB, nullable=True),
        sa.Column("compensation", JSONB, nullable=True),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("event", sa.String(64), nullable=False, server_default="EXECUTION_AUDIT"),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_execution_audits_recommendation", "execution_audits", ["recommendation_id"])
    op.create_index("ix_execution_audits_approval", "execution_audits", ["approval_id"])
    op.create_index("ix_execution_audits_intent", "execution_audits", ["intent_id"])
    op.create_index("ix_execution_audits_job", "execution_audits", ["job_id"])
    op.create_index("ix_execution_audits_provider", "execution_audits", ["provider"])
    op.create_index("ix_execution_audits_action", "execution_audits", ["action_type"])
    op.create_index("ix_execution_audits_entity", "execution_audits", ["entity_id"])
    op.create_index("ix_execution_audits_created", "execution_audits", ["created_at"])

    op.create_table(
        "execution_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("max_risk_level", sa.String(32), nullable=False, server_default="HIGH"),
        sa.Column("min_confidence", sa.Float(), nullable=False, server_default="0.6"),
        sa.Column("max_change_pct", sa.Float(), nullable=True),
        sa.Column("max_actions_per_hour", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("max_actions_per_day", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_total_budget_change_pct_per_day", sa.Float(), nullable=False, server_default="30"),
        sa.Column("allowed_scope", JSONB, nullable=True),
        sa.Column("require_fresh_data_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("max_affected_campaigns", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("auto_execution_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("standing_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("canary_scope", JSONB, nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_execution_policies_provider", "execution_policies", ["provider"])
    op.create_index("ix_execution_policies_action", "execution_policies", ["action_type"])
    op.create_index("uq_execution_policy_version", "execution_policies", ["workspace_id", "provider", "action_type", "version"], unique=True)

    op.create_table(
        "execution_kill_switches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("scope_id", sa.String(255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("activated_by", sa.String(128), nullable=True),
        sa.Column("activated_at", UTC, nullable=True),
        sa.Column("deactivated_by", sa.String(128), nullable=True),
        sa.Column("deactivated_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_execution_kill_switches_scope", "execution_kill_switches", ["scope_type"])
    op.create_index("ix_execution_kill_switches_scope_id", "execution_kill_switches", ["scope_id"])

    op.create_table(
        "execution_compensations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_job_id", sa.String(36), sa.ForeignKey("execution_jobs.id"), nullable=False),
        sa.Column("compensation_type", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("before_state", JSONB, nullable=True),
        sa.Column("target_state", JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("provider_request_id", sa.String(255), nullable=True),
        sa.Column("provider_resource_name", sa.String(255), nullable=True),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_execution_compensations_job", "execution_compensations", ["execution_job_id"])

    op.create_table(
        "execution_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_job_id", sa.String(36), sa.ForeignKey("execution_jobs.id"), nullable=False),
        sa.Column("intent_id", sa.String(36), nullable=True),
        sa.Column("observation_start", UTC, nullable=True),
        sa.Column("observation_end", UTC, nullable=True),
        sa.Column("before_metrics", JSONB, nullable=True),
        sa.Column("after_metrics", JSONB, nullable=True),
        sa.Column("expected_signal", JSONB, nullable=True),
        sa.Column("observed_signal", JSONB, nullable=True),
        sa.Column("outcome_label", sa.String(32), nullable=False, server_default="INSUFFICIENT_DATA"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_execution_outcomes_job", "execution_outcomes", ["execution_job_id"])


def downgrade() -> None:
    for table in (
        "execution_outcomes",
        "execution_compensations",
        "execution_kill_switches",
        "execution_policies",
        "execution_audits",
        "execution_events",
        "execution_jobs",
        "execution_intents",
        "execution_approvals",
    ):
        op.drop_table(table)
