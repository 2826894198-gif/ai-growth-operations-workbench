"""Part 04: multi-agent AI intelligence schema

Revision ID: 0004_part04_ai_intelligence
Revises: 0003_part03_rule_engine
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_part04_ai_intelligence"
down_revision: Union[str, None] = "0003_part03_rule_engine"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
UTC = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "ai_agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thread_id", sa.String(64), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("orchestrator_version", sa.String(32), nullable=True),
        sa.Column("input_ref", sa.String(512), nullable=True),
        sa.Column("output_ref", sa.String(512), nullable=True),
        sa.Column("total_model_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_ai_agent_runs_thread", "ai_agent_runs", ["thread_id"])
    op.create_index("ix_ai_agent_runs_task", "ai_agent_runs", ["task_type"])
    op.create_index("ix_ai_agent_runs_status", "ai_agent_runs", ["status"])

    op.create_table(
        "ai_agent_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("ai_agent_runs.id"), nullable=False),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("step_type", sa.String(32), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("model_provider", sa.String(64), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("input_ref", sa.String(512), nullable=True),
        sa.Column("output_ref", sa.String(512), nullable=True),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_usage", JSONB, nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="RUNNING"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_ai_agent_steps_run", "ai_agent_steps", ["run_id"])

    op.create_table(
        "ai_prompts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prompt_key", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("developer_prompt_template", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("model_constraints", JSONB, nullable=True),
        sa.Column("output_schema_version", sa.String(32), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.UniqueConstraint("prompt_key", "version", name="uq_ai_prompt_key_version"),
    )
    op.create_index("ix_ai_prompts_key", "ai_prompts", ["prompt_key"])

    op.create_table(
        "ai_business_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("memory_type", sa.String(64), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False, server_default="GLOBAL"),
        sa.Column("scope_id", sa.String(255), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("structured_payload", JSONB, nullable=True),
        sa.Column("evidence_refs", JSONB, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("valid_from", UTC, nullable=True),
        sa.Column("review_after", UTC, nullable=True),
        sa.Column("expires_at", UTC, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PROPOSED"),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_ai_business_memories_status", "ai_business_memories", ["status"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("version", sa.String(32), nullable=False, server_default="1"),
        sa.Column("source_uri", sa.String(512), nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("trust_level", sa.String(32), nullable=False, server_default="DATA"),
        sa.Column("effective_from", UTC, nullable=True),
        sa.Column("effective_to", UTC, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_knowledge_documents_type", "knowledge_documents", ["document_type"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("embedding", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_knowledge_chunks_document", "knowledge_chunks", ["document_id"])

    op.create_table(
        "creative_ai_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("creative_id", sa.String(255), nullable=False),
        sa.Column("analysis_version", sa.String(32), nullable=False, server_default="1"),
        sa.Column("model_provider", sa.String(64), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=True),
        sa.Column("creative_dna", JSONB, nullable=True),
        sa.Column("scene_timeline", JSONB, nullable=True),
        sa.Column("hook_analysis", JSONB, nullable=True),
        sa.Column("audio_analysis", JSONB, nullable=True),
        sa.Column("analysis_mode", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_asset_hash", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("blind", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
    )
    op.create_index("ix_creative_ai_analyses_creative", "creative_ai_analyses", ["creative_id"])

    op.create_table(
        "ai_model_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("ai_agent_runs.id"), nullable=True),
        sa.Column("step_id", sa.String(36), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("media_usage", JSONB, nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_ai_model_usage_run", "ai_model_usage", ["run_id"])

    op.create_table(
        "ai_eval_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("eval_suite", sa.String(64), nullable=False),
        sa.Column("candidate_agent_version", sa.String(64), nullable=True),
        sa.Column("baseline_agent_version", sa.String(64), nullable=True),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("aggregate_scores", JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="RUNNING"),
        sa.Column("created_at", UTC, nullable=False),
    )

    op.create_table(
        "ai_eval_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("eval_run_id", sa.String(36), sa.ForeignKey("ai_eval_runs.id"), nullable=False),
        sa.Column("case_id", sa.String(128), nullable=False),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("schema_score", sa.Float(), nullable=True),
        sa.Column("grounding_score", sa.Float(), nullable=True),
        sa.Column("numeric_score", sa.Float(), nullable=True),
        sa.Column("tool_score", sa.Float(), nullable=True),
        sa.Column("permission_score", sa.Float(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("critical_failure", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_ai_eval_results_run", "ai_eval_results", ["eval_run_id"])

    op.create_table(
        "ai_tool_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("ai_agent_runs.id"), nullable=True),
        sa.Column("step_id", sa.String(36), nullable=True),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("input_hash", sa.String(128), nullable=True),
        sa.Column("safe_input_summary", sa.Text(), nullable=True),
        sa.Column("output_ref", sa.String(512), nullable=True),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error_code", sa.String(128), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
    )
    op.create_index("ix_ai_tool_audits_run", "ai_tool_audits", ["run_id"])


def downgrade() -> None:
    for table in (
        "ai_tool_audits",
        "ai_eval_results",
        "ai_eval_runs",
        "ai_model_usage",
        "creative_ai_analyses",
        "knowledge_chunks",
        "knowledge_documents",
        "ai_business_memories",
        "ai_prompts",
        "ai_agent_steps",
        "ai_agent_runs",
    ):
        op.drop_table(table)
