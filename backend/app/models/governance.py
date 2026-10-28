"""PART 06-01 optimization pass — canonical entity, metric semantics, RBAC,
provider control plane and job registry (architecture review P0/P1)."""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class EntityRegistry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Canonical business entity — the only ID rules/recommendations/execution carry."""

    __tablename__ = "entity_registry"

    workspace_id = Column(String(36), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=True, index=True)
    entity_type = Column(String(64), nullable=False, index=True)  # CAMPAIGN/AD_SET/AD/CONTENT_ASSET/PUBLICATION/CONNECTED_ACCOUNT/...
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    display_name = Column(String(512), nullable=True)
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "entity_type", "display_name", name="uq_entity_registry_scope"),
        Index("ix_entity_registry_workspace_type", "workspace_id", "entity_type"),
    )


class ExternalEntityRef(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Resolve a canonical entity to a provider-native ID under a connected account."""

    __tablename__ = "external_entity_refs"

    entity_id = Column(String(36), ForeignKey("entity_registry.id"), nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    connected_account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=True, index=True)
    external_type = Column(String(64), nullable=False)
    external_id = Column(String(255), nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "connected_account_id",
            "external_type",
            "external_id",
            name="uq_external_entity_ref",
        ),
        Index("ix_external_ref_entity_provider", "entity_id", "provider"),
    )


class EntityRelation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "entity_relations"

    parent_entity_id = Column(String(36), ForeignKey("entity_registry.id"), nullable=False, index=True)
    child_entity_id = Column(String(36), ForeignKey("entity_registry.id"), nullable=False, index=True)
    relation_type = Column(String(64), nullable=False, index=True)  # HAS_CHILD/CONTAINS/PROMOTES/ATTRIBUTES_TO
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("parent_entity_id", "child_entity_id", "relation_type", name="uq_entity_relation"),
    )


class MetricDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Metrics-as-code: one definition consumed by API, rules, AI and frontend."""

    __tablename__ = "metric_definitions"

    metric_key = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=False)
    business_definition = Column(Text, nullable=True)
    numerator = Column(String(255), nullable=True)
    denominator = Column(String(255), nullable=True)
    allowed_dimensions = Column(JSON, nullable=True)
    source = Column(String(64), nullable=False, default="PLATFORM")
    timezone = Column(String(128), nullable=True)
    currency = Column(String(8), nullable=True)
    attribution_window = Column(String(64), nullable=True)
    measurement_basis = Column(String(64), nullable=False, default="PLATFORM_REPORTED")  # PLATFORM_REPORTED/FIRST_PARTY/MODELED
    freshness_sla_minutes = Column(Integer, nullable=True)
    data_quality_status = Column(String(32), nullable=False, default="UNKNOWN")
    owner = Column(String(128), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    deprecation_policy = Column(String(255), nullable=True)
    meta = Column("metadata", JSON, nullable=True)


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE")
    roles = Column(JSON, nullable=True)  # GLOBAL roles: ADMIN/OPERATOR/ANALYST/VIEWER


class WorkspaceMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspace_memberships"

    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    role = Column(String(32), nullable=False, default="VIEWER")  # VIEWER/ANALYST/OPERATOR/ADMIN
    status = Column(String(32), nullable=False, default="ACTIVE")

    __table_args__ = (UniqueConstraint("user_id", "workspace_id", name="uq_workspace_membership"),)


class BrandGrant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "brand_grants"

    workspace_id = Column(String(36), nullable=False, index=True)
    membership_id = Column(String(36), ForeignKey("workspace_memberships.id"), nullable=False, index=True)
    brand_id = Column(String(36), ForeignKey("brands.id"), nullable=False, index=True)
    permission = Column(String(64), nullable=False)  # READ/ANALYZE/APPROVE/EXECUTE/ADMIN

    __table_args__ = (UniqueConstraint("membership_id", "brand_id", "permission", name="uq_brand_grant"),)


class AccountGrant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "account_grants"

    workspace_id = Column(String(36), nullable=False, index=True)
    membership_id = Column(String(36), ForeignKey("workspace_memberships.id"), nullable=False, index=True)
    account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=False, index=True)
    permission = Column(String(64), nullable=False)

    __table_args__ = (UniqueConstraint("membership_id", "account_id", "permission", name="uq_account_grant"),)


class ProviderManifest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Provider control plane manifest (E101 + review 4.4)."""

    __tablename__ = "provider_manifests"

    provider = Column(String(64), nullable=False, index=True)
    platform = Column(String(64), nullable=True, index=True)
    auth_type = Column(String(64), nullable=False, default="OAUTH")
    scopes = Column(JSON, nullable=True)
    capabilities = Column(JSON, nullable=True)
    rate_limit = Column(JSON, nullable=True)
    health_probe = Column(JSON, nullable=True)
    api_version = Column(String(64), nullable=True)
    read_only = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="DRAFT")  # DRAFT/CONFIGURED/PRODUCTION_READY
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (UniqueConstraint("provider", "platform", name="uq_provider_manifest"),)


class CredentialRef(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Credential reference — never stores raw secrets; binds to workspace/account."""

    __tablename__ = "credential_refs"

    workspace_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    connected_account_id = Column(String(36), ForeignKey("connected_accounts.id"), nullable=True, index=True)
    secret_ref = Column(String(512), nullable=False)
    granted_scopes = Column(JSON, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    purpose = Column(String(32), nullable=False, default="READ")  # READ/WRITE
    status = Column(String(32), nullable=False, default="ACTIVE")
    meta = Column("metadata", JSON, nullable=True)


class JobRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "job_runs"

    workspace_id = Column(String(36), nullable=True, index=True)
    job_type = Column(String(64), nullable=False, index=True)  # sync/compute/ai/execution/browser
    queue = Column(String(64), nullable=False, default="default")
    idempotency_key = Column(String(128), nullable=False, unique=True, index=True)
    trace_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    payload = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    max_attempts = Column(Integer, nullable=False, default=3)
    meta = Column("metadata", JSON, nullable=True)


class JobAttempt(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_attempts"

    job_run_id = Column(String(36), ForeignKey("job_runs.id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="RUNNING")
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    meta = Column("metadata", JSON, nullable=True)

    __table_args__ = (UniqueConstraint("job_run_id", "attempt_number", name="uq_job_attempt"),)


class JobEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "job_events"

    job_run_id = Column(String(36), ForeignKey("job_runs.id"), nullable=False, index=True)
    attempt_id = Column(String(36), ForeignKey("job_attempts.id"), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    event_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class OutboxMessage(Base, UUIDPrimaryKeyMixin):
    """Transactional outbox — DB commit then reliable queue dispatch."""

    __tablename__ = "outbox_messages"

    aggregate_type = Column(String(64), nullable=False, index=True)
    aggregate_id = Column(String(36), nullable=False, index=True)
    message_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING/DISPATCHED/FAILED
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    dispatched_at = Column(DateTime(timezone=True), nullable=True)


class OAuthTransaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single-use, expiring OAuth authorization transaction (PART 07 §31-§34)."""

    __tablename__ = "oauth_transactions"

    workspace_id = Column(String(36), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)
    state_hash = Column(String(128), nullable=False, unique=True, index=True)
    pkce_verifier_reference = Column(String(512), nullable=True)
    redirect_uri = Column(String(512), nullable=False)
    initiated_by = Column(String(128), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING/COMPLETED/EXPIRED/REVOKED


class BrowserNode(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Browser node identity + allowlist + heartbeat (PART 07 §19-§21)."""

    __tablename__ = "browser_nodes"

    name = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="OFFLINE", index=True)  # ONLINE/DEGRADED/OFFLINE/REVOKED
    allowed_workspace_ids = Column(JSON, nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(String(64), nullable=True)
    credential_reference = Column(String(512), nullable=True)
    meta = Column("metadata", JSON, nullable=True)


class Release(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Deployment release record (PART 07 §155)."""

    __tablename__ = "releases"

    version = Column(String(64), nullable=False, index=True)
    git_sha = Column(String(64), nullable=False)
    image_digests = Column(JSON, nullable=True)
    db_revision = Column(String(64), nullable=True)
    deployed_by = Column(String(128), nullable=True)
    deployed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    environment = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="PENDING")  # PENDING/HEALTHY/ROLLED_BACK/FAILED
    rollback_from = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)


class RetentionPolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Retention governance (PART 07 §210-§215)."""

    __tablename__ = "retention_policies"

    category = Column(String(64), nullable=False, unique=True, index=True)
    description = Column(String(512), nullable=True)
    retention_days = Column(Integer, nullable=False)
    archive_after_days = Column(Integer, nullable=True)
    action = Column(String(32), nullable=False, default="DELETE")  # DELETE/ARCHIVE/ANONYMIZE
    pii = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
