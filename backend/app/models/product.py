from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Workspace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspaces"

    name = Column(String(255), nullable=False)
    timezone = Column(String(128), nullable=False, default="America/New_York")
    reporting_currency = Column(String(8), nullable=False, default="USD")
    status = Column(String(32), nullable=False, default="ACTIVE")


class FeatureFlag(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "feature_flags"

    flag_key = Column(String(64), nullable=False, unique=True)
    enabled = Column(Boolean, nullable=False, default=False)
    rollout_pct = Column(Integer, nullable=False, default=100)
    meta = Column("metadata", JSON, nullable=True)


class Notification(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "notifications"

    user_id = Column(String(64), nullable=True, index=True)
    type = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), nullable=False, default="MEDIUM")
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    entity_type = Column(String(64), nullable=True)
    entity_id = Column(String(255), nullable=True)
    recommendation_id = Column(String(36), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class UserDashboardPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_dashboard_preferences"

    user_id = Column(String(64), nullable=False, unique=True)
    default_workspace_id = Column(String(36), nullable=True)
    default_date_range = Column(String(32), nullable=False, default="LAST_7_DAYS")
    default_comparison = Column(String(32), nullable=False, default="PREVIOUS_PERIOD")
    density = Column(String(16), nullable=False, default="COMPACT")
    theme = Column(String(16), nullable=False, default="DARK")
    table_columns = Column(JSON, nullable=True)
    saved_filters = Column(JSON, nullable=True)


class CreativeBrief(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "creative_briefs"

    title = Column(String(255), nullable=False)
    objective = Column(Text, nullable=True)
    audience = Column(Text, nullable=True)
    hypothesis = Column(Text, nullable=True)
    hook = Column(Text, nullable=True)
    first_3_seconds = Column(Text, nullable=True)
    scene_sequence = Column(JSON, nullable=True)
    product_actions = Column(JSON, nullable=True)
    proof = Column(JSON, nullable=True)
    cta = Column(String(255), nullable=True)
    audio_direction = Column(Text, nullable=True)
    duration = Column(String(32), nullable=True)
    aspect_ratio = Column(String(32), nullable=True)
    avoid = Column(JSON, nullable=True)
    measurement_plan = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    evidence_refs = Column(JSON, nullable=True)
    created_by_run_id = Column(String(36), nullable=True)


class Experiment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "experiments"

    name = Column(String(255), nullable=False)
    hypothesis = Column(Text, nullable=True)
    variable = Column(String(255), nullable=True)
    control = Column(Text, nullable=True)
    treatment = Column(Text, nullable=True)
    primary_metric = Column(String(128), nullable=True)
    guardrail_metrics = Column(JSON, nullable=True)
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="PLANNED", index=True)
    result = Column(JSON, nullable=True)
    learnings = Column(JSON, nullable=True)
    protected_by_rule = Column(Boolean, nullable=False, default=False)
    scope_type = Column(String(32), nullable=True)
    scope_id = Column(String(255), nullable=True)


class SavedView(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "saved_views"

    user_id = Column(String(64), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    filters = Column(JSON, nullable=True)
    columns = Column(JSON, nullable=True)
    route = Column(String(255), nullable=True)
