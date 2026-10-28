"""Part 03: growth rule engine schema

Revision ID: 0003_part03_rule_engine
Revises: 0002_part02_data_platform
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_part03_rule_engine"
down_revision: Union[str, None] = "0002_part02_data_platform"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "business_target_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False, server_default="GLOBAL"),
        sa.Column("scope_id", sa.String(255), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("target_cpa", sa.Float(), nullable=True),
        sa.Column("target_roas", sa.Float(), nullable=True),
        sa.Column("break_even_roas", sa.Float(), nullable=True),
        sa.Column("target_aov", sa.Float(), nullable=True),
        sa.Column("gross_margin_rate", sa.Float(), nullable=True),
        sa.Column("max_daily_spend", sa.Float(), nullable=True),
        sa.Column("max_campaign_daily_spend", sa.Float(), nullable=True),
        sa.Column("refund_rate_warning", sa.Float(), nullable=True),
        sa.Column("refund_rate_critical", sa.Float(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )

    op.create_table(
        "rule_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_key", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column("scope_type", sa.String(32), nullable=True),
        sa.Column("scope_id", sa.String(255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("severity", sa.String(32), nullable=False, server_default="MEDIUM"),
        sa.Column("evaluation_level", sa.String(32), nullable=False, server_default="AD"),
        sa.Column("conditions", JSONB, nullable=True),
        sa.Column("guards", JSONB, nullable=True),
        sa.Column("action_template", JSONB, nullable=True),
        sa.Column("schedule_group", sa.String(32), nullable=False, server_default="DAILY"),
        sa.Column("required_capabilities", JSONB, nullable=True),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="1440"),
        sa.Column("minimum_confidence", sa.Float(), nullable=False, server_default="0.4"),
        sa.Column("auto_execution_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", UTC, nullable=True),
        sa.Column("valid_to", UTC, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("rule_key", "version", name="uq_rule_key_version"),
    )
    op.create_index("ix_rule_definitions_rule_key", "rule_definitions", ["rule_key"])

    op.create_table(
        "rule_parameters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_key", sa.String(128), nullable=False),
        sa.Column("parameter_key", sa.String(128), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False, server_default="GLOBAL"),
        sa.Column("scope_id", sa.String(255), nullable=True),
        sa.Column("value", JSONB, nullable=True),
        sa.Column("value_type", sa.String(32), nullable=False, server_default="number"),
        sa.Column("source", sa.String(32), nullable=False, server_default="SEED"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("valid_from", UTC, nullable=True),
        sa.Column("valid_to", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_rule_parameters_rule_key", "rule_parameters", ["rule_key"])

    op.create_table(
        "rule_evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope", sa.String(255), nullable=True),
        sa.Column("trigger_type", sa.String(32), nullable=False, server_default="SCHEDULED"),
        sa.Column("started_at", UTC, nullable=False),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("rules_evaluated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("entities_evaluated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("triggered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_decision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suppressed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("data_as_of", UTC, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="RUNNING"),
        sa.Column("created_at", UTC, nullable=False),
    )

    op.create_table(
        "rule_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("evaluation_run_id", sa.String(36), sa.ForeignKey("rule_evaluation_runs.id"), nullable=False),
        sa.Column("rule_key", sa.String(128), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("context_snapshot", JSONB, nullable=True),
        sa.Column("feature_snapshot", JSONB, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reason_codes", JSONB, nullable=True),
        sa.Column("evaluated_at", UTC, nullable=False),
    )
    op.create_index("ix_rule_evaluations_run", "rule_evaluations", ["evaluation_run_id"])
    op.create_index("ix_rule_evaluations_rule", "rule_evaluations", ["rule_key"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column("primary_action", sa.String(64), nullable=False),
        sa.Column("reason_group", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="MEDIUM"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_execution_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("supporting_rules", JSONB, nullable=True),
        sa.Column("suppressed_reasons", JSONB, nullable=True),
        sa.Column("suggested_change_pct", sa.Float(), nullable=True),
        sa.Column("current_budget", sa.Float(), nullable=True),
        sa.Column("proposed_budget", sa.Float(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.Column("resolved_at", UTC, nullable=True),
    )
    op.create_index("ix_recommendations_entity", "recommendations", ["entity_type", "entity_id"])
    op.create_index("ix_recommendations_action", "recommendations", ["primary_action"])
    op.create_index("ix_recommendations_status", "recommendations", ["status"])

    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recommendation_id", sa.String(36), sa.ForeignKey("recommendations.id"), nullable=False),
        sa.Column("operator_decision", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_recommendation_feedback_rec", "recommendation_feedback", ["recommendation_id"])

    op.create_table(
        "rule_conflict_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("priority_a", sa.String(64), nullable=False),
        sa.Column("priority_b", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )

    op.create_table(
        "active_experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column("scope_type", sa.String(64), nullable=False),
        sa.Column("scope_id", sa.String(255), nullable=False),
        sa.Column("experiment_type", sa.String(64), nullable=True),
        sa.Column("start_at", UTC, nullable=True),
        sa.Column("end_at", UTC, nullable=True),
        sa.Column("protected_metrics", JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )

    op.create_table(
        "creative_performance_labels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("creative_id", sa.String(255), nullable=False),
        sa.Column("label", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evaluated_at", UTC, nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
    )
    op.create_index("ix_creative_labels_creative", "creative_performance_labels", ["creative_id"])

    op.create_table(
        "campaign_strategy_labels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_source_id", sa.String(36), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("campaign_id", sa.String(255), nullable=False),
        sa.Column("strategy_label", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="MANUAL"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_campaign_strategy_labels_campaign", "campaign_strategy_labels", ["campaign_id"])

    op.create_table(
        "entity_change_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("change_type", sa.String(64), nullable=False),
        sa.Column("occurred_at", UTC, nullable=False),
        sa.Column("old_value", JSONB, nullable=True),
        sa.Column("new_value", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
    )
    op.create_index("ix_entity_change_events_entity", "entity_change_events", ["entity_id"])

    op.create_table(
        "rule_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("before", JSONB, nullable=True),
        sa.Column("after", JSONB, nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )


def downgrade() -> None:
    for table in (
        "rule_audit_logs",
        "entity_change_events",
        "campaign_strategy_labels",
        "creative_performance_labels",
        "active_experiments",
        "rule_conflict_policies",
        "recommendation_feedback",
        "recommendations",
        "rule_evaluations",
        "rule_evaluation_runs",
        "rule_parameters",
        "rule_definitions",
        "business_target_profiles",
    ):
        op.drop_table(table)
