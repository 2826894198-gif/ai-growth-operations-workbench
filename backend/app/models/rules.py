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


class BusinessTargetProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "business_target_profiles"

    workspace_id = Column(String(36), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    scope_type = Column(String(32), nullable=False, default="GLOBAL")
    scope_id = Column(String(255), nullable=True)
    currency = Column(String(8), nullable=True)
    target_cpa = Column(Float, nullable=True)
    target_roas = Column(Float, nullable=True)
    break_even_roas = Column(Float, nullable=True)
    target_aov = Column(Float, nullable=True)
    gross_margin_rate = Column(Float, nullable=True)
    max_daily_spend = Column(Float, nullable=True)
    max_campaign_daily_spend = Column(Float, nullable=True)
    refund_rate_warning = Column(Float, nullable=True)
    refund_rate_critical = Column(Float, nullable=True)


class RuleDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rule_definitions"

    rule_key = Column(String(128), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False)
    platform = Column(String(32), nullable=True)
    scope_type = Column(String(32), nullable=True)
    scope_id = Column(String(255), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="DRAFT")
    severity = Column(String(32), nullable=False, default="MEDIUM")
    evaluation_level = Column(String(32), nullable=False, default="AD")
    conditions = Column(JSON, nullable=True)
    guards = Column(JSON, nullable=True)
    action_template = Column(JSON, nullable=True)
    schedule_group = Column(String(32), nullable=False, default="DAILY")
    required_capabilities = Column(JSON, nullable=True)
    cooldown_minutes = Column(Integer, nullable=False, default=1440)
    minimum_confidence = Column(Float, nullable=False, default=0.4)
    auto_execution_eligible = Column(Boolean, nullable=False, default=False)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(128), nullable=True)

    __table_args__ = (
        UniqueConstraint("rule_key", "version", name="uq_rule_key_version"),
    )


class RuleParameter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rule_parameters"

    rule_key = Column(String(128), nullable=False, index=True)
    parameter_key = Column(String(128), nullable=False)
    scope_type = Column(String(32), nullable=False, default="GLOBAL")
    scope_id = Column(String(255), nullable=True)
    value = Column(JSON, nullable=True)
    value_type = Column(String(32), nullable=False, default="number")
    source = Column(String(32), nullable=False, default="SEED")
    confidence = Column(Float, nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)


class RuleEvaluationRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "rule_evaluation_runs"

    scope = Column(String(255), nullable=True)
    trigger_type = Column(String(32), nullable=False, default="SCHEDULED")
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    rules_evaluated = Column(Integer, nullable=False, default=0)
    entities_evaluated = Column(Integer, nullable=False, default=0)
    triggered = Column(Integer, nullable=False, default=0)
    no_decision = Column(Integer, nullable=False, default=0)
    suppressed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    data_as_of = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="RUNNING")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class RuleEvaluation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "rule_evaluations"

    evaluation_run_id = Column(String(36), ForeignKey("rule_evaluation_runs.id"), nullable=False, index=True)
    rule_key = Column(String(128), nullable=False, index=True)
    rule_version = Column(Integer, nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(255), nullable=False)
    result = Column(String(32), nullable=False)
    context_snapshot = Column(JSON, nullable=True)
    feature_snapshot = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    reason_codes = Column(JSON, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class Recommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "recommendations"

    canonical_entity_id = Column(String(36), ForeignKey("entity_registry.id"), nullable=True, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(255), nullable=False, index=True)
    platform = Column(String(32), nullable=True)
    primary_action = Column(String(64), nullable=False, index=True)
    reason_group = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), nullable=False, default="MEDIUM")
    confidence = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    case_status = Column(String(32), nullable=False, default="DRAFT", index=True)
    simulated_impact = Column(JSON, nullable=True)
    ai_explanation = Column(Text, nullable=True)
    decision_reason = Column(Text, nullable=True)
    approval_required = Column(Boolean, nullable=False, default=True)
    auto_execution_eligible = Column(Boolean, nullable=False, default=False)
    evidence = Column(JSON, nullable=True)
    supporting_rules = Column(JSON, nullable=True)
    suppressed_reasons = Column(JSON, nullable=True)
    suggested_change_pct = Column(Float, nullable=True)
    current_budget = Column(Float, nullable=True)
    proposed_budget = Column(Float, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class RecommendationFeedback(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "recommendation_feedback"

    recommendation_id = Column(String(36), ForeignKey("recommendations.id"), nullable=False, index=True)
    operator_decision = Column(String(64), nullable=False)
    reason = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class RuleConflictPolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rule_conflict_policies"

    priority_a = Column(String(64), nullable=False)
    priority_b = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    reason = Column(String(255), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)


class ActiveExperiment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "active_experiments"

    name = Column(String(255), nullable=False)
    platform = Column(String(32), nullable=True)
    scope_type = Column(String(64), nullable=False)
    scope_id = Column(String(255), nullable=False)
    experiment_type = Column(String(64), nullable=True)
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True)
    protected_metrics = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE")
    meta = Column("metadata", JSON, nullable=True)


class CreativePerformanceLabel(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "creative_performance_labels"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=True)
    platform = Column(String(32), nullable=False)
    creative_id = Column(String(255), nullable=False, index=True)
    label = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    meta = Column("metadata", JSON, nullable=True)


class CampaignStrategyLabel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaign_strategy_labels"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=True)
    platform = Column(String(32), nullable=False)
    campaign_id = Column(String(255), nullable=False, index=True)
    strategy_label = Column(String(64), nullable=False)
    source = Column(String(32), nullable=False, default="MANUAL")
    meta = Column("metadata", JSON, nullable=True)


class EntityChangeEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "entity_change_events"

    platform = Column(String(32), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(255), nullable=False, index=True)
    change_type = Column(String(64), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    meta = Column("metadata", JSON, nullable=True)


class RuleAuditLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "rule_audit_logs"

    actor = Column(String(128), nullable=True)
    action = Column(String(64), nullable=False)
    target = Column(String(255), nullable=True)
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    request_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
