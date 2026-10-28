"""Architecture optimization pass — canonical entity, metric semantics, RBAC,
provider control plane, job registry, execution bindings.

Revision ID: 0008_governance_optimization
Revises: 0007_part0601_social
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_governance_optimization"
down_revision: Union[str, None] = "0007_part0601_social"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "entity_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("brand_id", sa.String(36), sa.ForeignKey("brands.id"), nullable=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("display_name", sa.String(512), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_entity_registry_workspace", "entity_registry", ["workspace_id"])
    op.create_index("ix_entity_registry_type", "entity_registry", ["entity_type"])
    op.create_index("ix_entity_registry_status", "entity_registry", ["status"])
    op.create_index("ix_entity_registry_workspace_type", "entity_registry", ["workspace_id", "entity_type"])
    op.create_unique_constraint("uq_entity_registry_scope", "entity_registry", ["workspace_id", "entity_type", "display_name"])

    op.create_table(
        "external_entity_refs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_id", sa.String(36), sa.ForeignKey("entity_registry.id"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("connected_account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=True),
        sa.Column("external_type", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("valid_from", UTC, nullable=True),
        sa.Column("valid_to", UTC, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_external_refs_entity", "external_entity_refs", ["entity_id"])
    op.create_index("ix_external_refs_account", "external_entity_refs", ["connected_account_id"])
    op.create_index("ix_external_ref_entity_provider", "external_entity_refs", ["entity_id", "provider"])
    op.create_unique_constraint(
        "uq_external_entity_ref",
        "external_entity_refs",
        ["provider", "connected_account_id", "external_type", "external_id"],
    )

    op.create_table(
        "entity_relations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_entity_id", sa.String(36), sa.ForeignKey("entity_registry.id"), nullable=False),
        sa.Column("child_entity_id", sa.String(36), sa.ForeignKey("entity_registry.id"), nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("valid_from", UTC, nullable=True),
        sa.Column("valid_to", UTC, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_entity_relations_parent", "entity_relations", ["parent_entity_id"])
    op.create_index("ix_entity_relations_child", "entity_relations", ["child_entity_id"])
    op.create_index("ix_entity_relations_type", "entity_relations", ["relation_type"])
    op.create_unique_constraint("uq_entity_relation", "entity_relations", ["parent_entity_id", "child_entity_id", "relation_type"])

    op.create_table(
        "metric_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("metric_key", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("business_definition", sa.Text(), nullable=True),
        sa.Column("numerator", sa.String(255), nullable=True),
        sa.Column("denominator", sa.String(255), nullable=True),
        sa.Column("allowed_dimensions", JSONB, nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="PLATFORM"),
        sa.Column("timezone", sa.String(128), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("attribution_window", sa.String(64), nullable=True),
        sa.Column("measurement_basis", sa.String(64), nullable=False, server_default="PLATFORM_REPORTED"),
        sa.Column("freshness_sla_minutes", sa.Integer(), nullable=True),
        sa.Column("data_quality_status", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deprecation_policy", sa.String(255), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_metric_definitions_key", "metric_definitions", ["metric_key"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("roles", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="VIEWER"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_workspace_memberships_user", "workspace_memberships", ["user_id"])
    op.create_index("ix_workspace_memberships_workspace", "workspace_memberships", ["workspace_id"])
    op.create_unique_constraint("uq_workspace_membership", "workspace_memberships", ["user_id", "workspace_id"])

    op.create_table(
        "brand_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("membership_id", sa.String(36), sa.ForeignKey("workspace_memberships.id"), nullable=False),
        sa.Column("brand_id", sa.String(36), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("permission", sa.String(64), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_brand_grants_workspace", "brand_grants", ["workspace_id"])
    op.create_index("ix_brand_grants_membership", "brand_grants", ["membership_id"])
    op.create_index("ix_brand_grants_brand", "brand_grants", ["brand_id"])
    op.create_unique_constraint("uq_brand_grant", "brand_grants", ["membership_id", "brand_id", "permission"])

    op.create_table(
        "account_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("membership_id", sa.String(36), sa.ForeignKey("workspace_memberships.id"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("permission", sa.String(64), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_account_grants_workspace", "account_grants", ["workspace_id"])
    op.create_index("ix_account_grants_membership", "account_grants", ["membership_id"])
    op.create_index("ix_account_grants_account", "account_grants", ["account_id"])
    op.create_unique_constraint("uq_account_grant", "account_grants", ["membership_id", "account_id", "permission"])

    op.create_table(
        "provider_manifests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(64), nullable=True),
        sa.Column("auth_type", sa.String(64), nullable=False, server_default="OAUTH"),
        sa.Column("scopes", JSONB, nullable=True),
        sa.Column("capabilities", JSONB, nullable=True),
        sa.Column("rate_limit", JSONB, nullable=True),
        sa.Column("health_probe", JSONB, nullable=True),
        sa.Column("api_version", sa.String(64), nullable=True),
        sa.Column("read_only", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_provider_manifests_provider", "provider_manifests", ["provider"])
    op.create_index("ix_provider_manifests_platform", "provider_manifests", ["platform"])
    op.create_unique_constraint("uq_provider_manifest", "provider_manifests", ["provider", "platform"])

    op.create_table(
        "credential_refs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("connected_account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=True),
        sa.Column("secret_ref", sa.String(512), nullable=False),
        sa.Column("granted_scopes", JSONB, nullable=True),
        sa.Column("expires_at", UTC, nullable=True),
        sa.Column("purpose", sa.String(32), nullable=False, server_default="READ"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_credential_refs_workspace", "credential_refs", ["workspace_id"])
    op.create_index("ix_credential_refs_provider", "credential_refs", ["provider"])
    op.create_index("ix_credential_refs_account", "credential_refs", ["connected_account_id"])

    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("queue", sa.String(64), nullable=False, server_default="default"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_job_runs_workspace", "job_runs", ["workspace_id"])
    op.create_index("ix_job_runs_type", "job_runs", ["job_type"])
    op.create_index("ix_job_runs_queue", "job_runs", ["queue"])
    op.create_index("ix_job_runs_status", "job_runs", ["status"])
    op.create_index("ix_job_runs_trace", "job_runs", ["trace_id"])
    op.create_index("uq_job_run_idempotency", "job_runs", ["idempotency_key"], unique=True)

    op.create_table(
        "job_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_run_id", sa.String(36), sa.ForeignKey("job_runs.id"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="RUNNING"),
        sa.Column("started_at", UTC, nullable=False),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
    )
    op.create_index("ix_job_attempts_run", "job_attempts", ["job_run_id"])
    op.create_unique_constraint("uq_job_attempt", "job_attempts", ["job_run_id", "attempt_number"])

    op.create_table(
        "job_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_run_id", sa.String(36), sa.ForeignKey("job_runs.id"), nullable=False),
        sa.Column("attempt_id", sa.String(36), sa.ForeignKey("job_attempts.id"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_data", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_job_events_run", "job_events", ["job_run_id"])
    op.create_index("ix_job_events_attempt", "job_events", ["attempt_id"])
    op.create_index("ix_job_events_type", "job_events", ["event_type"])
    op.create_index("ix_job_events_created", "job_events", ["created_at"])

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.String(36), nullable=False),
        sa.Column("message_type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("dispatched_at", UTC, nullable=True),
    )
    op.create_index("ix_outbox_aggregate", "outbox_messages", ["aggregate_type", "aggregate_id"])
    op.create_index("ix_outbox_status", "outbox_messages", ["status"])

    # Existing table alterations
    op.add_column("recommendations", sa.Column("canonical_entity_id", sa.String(36), sa.ForeignKey("entity_registry.id"), nullable=True))
    op.add_column("recommendations", sa.Column("case_status", sa.String(32), nullable=False, server_default="DRAFT"))
    op.add_column("recommendations", sa.Column("simulated_impact", JSONB, nullable=True))
    op.add_column("recommendations", sa.Column("ai_explanation", sa.Text(), nullable=True))
    op.add_column("recommendations", sa.Column("decision_reason", sa.Text(), nullable=True))
    op.create_index("ix_recommendations_canonical_entity", "recommendations", ["canonical_entity_id"])
    op.create_index("ix_recommendations_case_status", "recommendations", ["case_status"])

    op.add_column("execution_intents", sa.Column("canonical_entity_id", sa.String(36), sa.ForeignKey("entity_registry.id"), nullable=True))
    op.add_column("execution_intents", sa.Column("action_package_hash", sa.String(64), nullable=True))
    op.add_column("execution_intents", sa.Column("credential_version", sa.String(64), nullable=True))
    op.add_column("execution_intents", sa.Column("metric_snapshot_id", sa.String(36), nullable=True))
    op.create_index("ix_execution_intents_canonical_entity", "execution_intents", ["canonical_entity_id"])

    op.add_column("fact_ad_performance_daily", sa.Column("measurement_basis", sa.String(64), nullable=False, server_default="PLATFORM_REPORTED"))


def downgrade() -> None:
    op.drop_column("fact_ad_performance_daily", "measurement_basis")
    op.drop_index("ix_execution_intents_canonical_entity", table_name="execution_intents")
    op.drop_column("execution_intents", "metric_snapshot_id")
    op.drop_column("execution_intents", "credential_version")
    op.drop_column("execution_intents", "action_package_hash")
    op.drop_column("execution_intents", "canonical_entity_id")
    op.drop_index("ix_recommendations_case_status", table_name="recommendations")
    op.drop_index("ix_recommendations_canonical_entity", table_name="recommendations")
    op.drop_column("recommendations", "decision_reason")
    op.drop_column("recommendations", "ai_explanation")
    op.drop_column("recommendations", "simulated_impact")
    op.drop_column("recommendations", "case_status")
    op.drop_column("recommendations", "canonical_entity_id")
    for table in (
        "outbox_messages",
        "job_events",
        "job_attempts",
        "job_runs",
        "credential_refs",
        "provider_manifests",
        "account_grants",
        "brand_grants",
        "workspace_memberships",
        "users",
        "metric_definitions",
        "entity_relations",
        "external_entity_refs",
        "entity_registry",
    ):
        op.drop_table(table)
