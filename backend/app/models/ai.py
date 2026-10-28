from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class AIAgentRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_agent_runs"

    thread_id = Column(String(64), nullable=False, index=True)
    task_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="QUEUED", index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    orchestrator_version = Column(String(32), nullable=True)
    input_ref = Column(String(512), nullable=True)
    output_ref = Column(String(512), nullable=True)
    total_model_calls = Column(Integer, nullable=False, default=0)
    total_tool_calls = Column(Integer, nullable=False, default=0)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    error_code = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    meta = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AIAgentStep(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_agent_steps"

    run_id = Column(String(36), ForeignKey("ai_agent_runs.id"), nullable=False, index=True)
    agent_type = Column(String(64), nullable=False)
    step_type = Column(String(32), nullable=False)
    prompt_version = Column(String(32), nullable=True)
    model_provider = Column(String(64), nullable=True)
    model_name = Column(String(128), nullable=True)
    input_ref = Column(String(512), nullable=True)
    output_ref = Column(String(512), nullable=True)
    tool_calls = Column(Integer, nullable=False, default=0)
    token_usage = Column(JSON, nullable=True)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default="RUNNING")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AIPrompt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_prompts"

    prompt_key = Column(String(128), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    agent_type = Column(String(64), nullable=False)
    system_prompt = Column(Text, nullable=False)
    developer_prompt_template = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE")
    model_constraints = Column(JSON, nullable=True)
    output_schema_version = Column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("prompt_key", "version", name="uq_ai_prompt_key_version"),
    )


class AIBusinessMemory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_business_memories"

    memory_type = Column(String(64), nullable=False)
    scope_type = Column(String(32), nullable=False, default="GLOBAL")
    scope_id = Column(String(255), nullable=True)
    statement = Column(Text, nullable=False)
    structured_payload = Column(JSON, nullable=True)
    evidence_refs = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    review_after = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="PROPOSED", index=True)
    created_by_run_id = Column(String(36), nullable=True)
    approved_by = Column(String(128), nullable=True)


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_documents"

    document_type = Column(String(64), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    version = Column(String(32), nullable=False, default="1")
    source_uri = Column(String(512), nullable=True)
    content_hash = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="DRAFT")
    trust_level = Column(String(32), nullable=False, default="DATA")
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    meta = Column("metadata", JSON, nullable=True)


class KnowledgeChunk(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "knowledge_chunks"

    document_id = Column(String(36), ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False)
    meta = Column("metadata", JSON, nullable=True)
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class CreativeAIAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "creative_ai_analyses"

    creative_id = Column(String(255), nullable=False, index=True)
    analysis_version = Column(String(32), nullable=False, default="1")
    model_provider = Column(String(64), nullable=True)
    model_name = Column(String(128), nullable=True)
    creative_dna = Column(JSON, nullable=True)
    scene_timeline = Column(JSON, nullable=True)
    hook_analysis = Column(JSON, nullable=True)
    audio_analysis = Column(JSON, nullable=True)
    analysis_mode = Column(String(32), nullable=True)
    confidence = Column(Float, nullable=True)
    source_asset_hash = Column(String(128), nullable=True)
    prompt_version = Column(String(32), nullable=True)
    blind = Column(Boolean, nullable=False, default=False)


class AIModelUsage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_model_usage"

    run_id = Column(String(36), ForeignKey("ai_agent_runs.id"), nullable=True, index=True)
    step_id = Column(String(36), nullable=True)
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cached_tokens = Column(Integer, nullable=False, default=0)
    media_usage = Column(JSON, nullable=True)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    currency = Column(String(8), nullable=False, default="USD")
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AIEvalRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_eval_runs"

    eval_suite = Column(String(64), nullable=False)
    candidate_agent_version = Column(String(64), nullable=True)
    baseline_agent_version = Column(String(64), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    total_cases = Column(Integer, nullable=False, default=0)
    passed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    aggregate_scores = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="RUNNING")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AIEvalResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_eval_results"

    eval_run_id = Column(String(36), ForeignKey("ai_eval_runs.id"), nullable=False, index=True)
    case_id = Column(String(128), nullable=False)
    agent_type = Column(String(64), nullable=False)
    schema_score = Column(Float, nullable=True)
    grounding_score = Column(Float, nullable=True)
    numeric_score = Column(Float, nullable=True)
    tool_score = Column(Float, nullable=True)
    permission_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    critical_failure = Column(Boolean, nullable=False, default=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AIToolAudit(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_tool_audits"

    run_id = Column(String(36), ForeignKey("ai_agent_runs.id"), nullable=True, index=True)
    step_id = Column(String(36), nullable=True)
    agent_type = Column(String(64), nullable=False)
    tool_name = Column(String(128), nullable=False)
    risk_level = Column(String(32), nullable=False)
    input_hash = Column(String(128), nullable=True)
    safe_input_summary = Column(Text, nullable=True)
    output_ref = Column(String(512), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_code = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
