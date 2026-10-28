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


class ExecutionApproval(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Specific, single-use, expiring approval bound to one frozen action."""

    __tablename__ = "execution_approvals"

    workspace_id = Column(String(36), nullable=True)
    recommendation_id = Column(String(36), ForeignKey("recommendations.id"), nullable=False, index=True)
    approved_by = Column(String(128), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    provider = Column(String(32), nullable=False, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(255), nullable=False, index=True)
    external_entity_id = Column(String(255), nullable=True)
    approved_change = Column(JSON, nullable=False)
    expected_before_state = Column(JSON, nullable=True)
    expected_before_hash = Column(String(64), nullable=True)
    risk_level = Column(String(32), nullable=False, default="MEDIUM")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING/APPROVED/REJECTED/EXPIRED/REVOKED/CONSUMED
    approval_hash = Column(String(64), nullable=False, index=True)
    revocation_reason = Column(String(255), nullable=True)
    revoked_by = Column(String(128), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    consumed_by_intent_id = Column(String(36), nullable=True)


class ExecutionIntent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Frozen, auditable intended provider mutation produced from an approval."""

    __tablename__ = "execution_intents"

    workspace_id = Column(String(36), nullable=True)
    canonical_entity_id = Column(String(36), ForeignKey("entity_registry.id"), nullable=True, index=True)
    recommendation_id = Column(String(36), ForeignKey("recommendations.id"), nullable=False, index=True)
    approval_id = Column(String(36), ForeignKey("execution_approvals.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    account_id = Column(String(255), nullable=True)
    action_type = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(255), nullable=False, index=True)
    external_entity_id = Column(String(255), nullable=True)
    requested_change = Column(JSON, nullable=False)
    expected_before_state = Column(JSON, nullable=True)
    expected_before_hash = Column(String(64), nullable=True)
    risk_level = Column(String(32), nullable=False, default="MEDIUM")
    blast_radius = Column(String(32), nullable=True)
    approval_required = Column(Boolean, nullable=False, default=True)
    approval_expires_at = Column(DateTime(timezone=True), nullable=True)
    execution_policy_version = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    action_package_hash = Column(String(64), nullable=True)
    credential_version = Column(String(64), nullable=True)
    metric_snapshot_id = Column(String(36), nullable=True)
    execution_group_id = Column(String(36), nullable=True)
    shadow_only = Column(Boolean, nullable=False, default=False)
    superseded_by_recommendation_id = Column(String(36), nullable=True)


class ExecutionJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One execution attempt of one frozen intent."""

    __tablename__ = "execution_jobs"

    intent_id = Column(String(36), ForeignKey("execution_intents.id"), nullable=False, index=True)
    approval_id = Column(String(36), ForeignKey("execution_approvals.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(255), nullable=False, index=True)
    external_entity_id = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="QUEUED", index=True)
    attempt = Column(Integer, nullable=False, default=0)
    provider_request_id = Column(String(255), nullable=True)
    provider_resource_name = Column(String(255), nullable=True)
    before_state = Column(JSON, nullable=True)
    requested_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    revalidation_result = Column(String(32), nullable=True)
    provider_validation_result = Column(String(32), nullable=True)
    verification_result = Column(String(32), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    shadow_only = Column(Boolean, nullable=False, default=False)


class ExecutionEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "execution_events"

    execution_id = Column(String(36), index=True)  # intent or job id
    job_id = Column(String(36), ForeignKey("execution_jobs.id"), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    event_data = Column(JSON, nullable=True)
    actor = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class ExecutionAudit(Base, UUIDPrimaryKeyMixin):
    """Append-only execution audit trail with redacted provider payloads."""

    __tablename__ = "execution_audits"

    workspace_id = Column(String(36), nullable=True)
    recommendation_id = Column(String(36), nullable=True, index=True)
    approval_id = Column(String(36), nullable=True, index=True)
    intent_id = Column(String(36), nullable=True, index=True)
    job_id = Column(String(36), nullable=True, index=True)
    policy_version = Column(Integer, nullable=True)
    provider = Column(String(32), nullable=True, index=True)
    action_type = Column(String(64), nullable=True, index=True)
    entity_id = Column(String(255), nullable=True, index=True)
    revalidation = Column(JSON, nullable=True)
    before_state = Column(JSON, nullable=True)
    provider_request = Column(JSON, nullable=True)
    provider_response = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    verification = Column(JSON, nullable=True)
    compensation = Column(JSON, nullable=True)
    actor = Column(String(128), nullable=True)
    event = Column(String(64), nullable=False, default="EXECUTION_AUDIT")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class ExecutionPolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "execution_policies"

    workspace_id = Column(String(36), nullable=True)
    name = Column(String(255), nullable=False)
    provider = Column(String(32), nullable=False, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    mode = Column(String(32), nullable=False, default="manual")
    max_risk_level = Column(String(32), nullable=False, default="HIGH")
    min_confidence = Column(Float, nullable=False, default=0.60)
    max_change_pct = Column(Float, nullable=True)
    max_actions_per_hour = Column(Integer, nullable=False, default=10)
    max_actions_per_day = Column(Integer, nullable=False, default=30)
    max_total_budget_change_pct_per_day = Column(Float, nullable=False, default=30.0)
    allowed_scope = Column(JSON, nullable=True)  # {"entity_ids": [...], "campaign_ids": [...], "all": false}
    require_fresh_data_minutes = Column(Integer, nullable=False, default=60)
    cooldown_minutes = Column(Integer, nullable=False, default=1440)
    max_affected_campaigns = Column(Integer, nullable=False, default=1)
    auto_execution_eligible = Column(Boolean, nullable=False, default=False)
    standing_approval = Column(Boolean, nullable=False, default=False)
    canary_scope = Column(JSON, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(128), nullable=True)
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", "action_type", "version", name="uq_execution_policy_version"),
    )


class ExecutionKillSwitch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "execution_kill_switches"

    scope_type = Column(String(32), nullable=False, index=True)  # GLOBAL/PROVIDER/ACCOUNT/ACTION/ENTITY
    scope_id = Column(String(255), nullable=True, index=True)
    enabled = Column(Boolean, nullable=False, default=False)
    reason = Column(String(255), nullable=True)
    activated_by = Column(String(128), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_by = Column(String(128), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)


class ExecutionCompensation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "execution_compensations"

    execution_job_id = Column(String(36), ForeignKey("execution_jobs.id"), nullable=False, index=True)
    compensation_type = Column(String(64), nullable=False)
    provider = Column(String(32), nullable=False)
    action_type = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(255), nullable=False)
    before_state = Column(JSON, nullable=True)
    target_state = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING")  # PENDING/APPROVED/REJECTED/RUNNING/SUCCEEDED/FAILED
    approved_by = Column(String(128), nullable=True)
    provider_request_id = Column(String(255), nullable=True)
    provider_resource_name = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)


class ExecutionOutcome(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "execution_outcomes"

    execution_job_id = Column(String(36), ForeignKey("execution_jobs.id"), nullable=False, index=True)
    intent_id = Column(String(36), nullable=True, index=True)
    observation_start = Column(DateTime(timezone=True), nullable=True)
    observation_end = Column(DateTime(timezone=True), nullable=True)
    before_metrics = Column(JSON, nullable=True)
    after_metrics = Column(JSON, nullable=True)
    expected_signal = Column(JSON, nullable=True)
    observed_signal = Column(JSON, nullable=True)
    outcome_label = Column(String(32), nullable=False, default="INSUFFICIENT_DATA")
    notes = Column(Text, nullable=True)
