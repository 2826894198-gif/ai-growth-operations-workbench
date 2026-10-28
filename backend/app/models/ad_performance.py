from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class AdPerformanceDaily(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_ad_performance_daily"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    marketing_account_id = Column(String(36), ForeignKey("dim_marketing_accounts.id"), nullable=True)
    platform = Column(String(32), nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(String(36), nullable=True)
    external_entity_id = Column(String(255), nullable=False)
    date = Column(Date, nullable=False, index=True)
    currency = Column(String(8), nullable=True)
    impressions = Column(Numeric(20, 8), nullable=True)
    reach = Column(Numeric(20, 8), nullable=True)
    clicks = Column(Numeric(20, 8), nullable=True)
    link_clicks = Column(Numeric(20, 8), nullable=True)
    outbound_clicks = Column(Numeric(20, 8), nullable=True)
    spend_amount = Column(Numeric(20, 8), nullable=True)
    platform_conversions = Column(Numeric(20, 8), nullable=True)
    platform_conversion_value = Column(Numeric(20, 8), nullable=True)
    platform_purchases = Column(Numeric(20, 8), nullable=True)
    platform_purchase_value = Column(Numeric(20, 8), nullable=True)
    cpm = Column(Numeric(20, 8), nullable=True)
    cpc = Column(Numeric(20, 8), nullable=True)
    ctr = Column(Numeric(20, 8), nullable=True)
    frequency = Column(Numeric(20, 8), nullable=True)
    platform_reported_roas = Column(Numeric(20, 8), nullable=True)
    source_attribution_metadata = Column(JSON, nullable=True)
    sync_job_id = Column(String(36), nullable=True, index=True)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "data_source_id", "entity_type", "external_entity_id", "date", name="uq_perf_daily_grain"
        ),
        Index("ix_perf_platform_date", "platform", "date"),
        Index("ix_perf_entity_date", "entity_type", "entity_id", "date"),
        Index("ix_perf_source_date", "data_source_id", "date"),
    )


class AdPerformanceSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "fact_ad_performance_snapshots"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    platform = Column(String(32), nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(String(36), nullable=True)
    external_entity_id = Column(String(255), nullable=False)
    source_date = Column(Date, nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    currency = Column(String(8), nullable=True)
    spend_amount = Column(Numeric(20, 8), nullable=True)
    impressions = Column(Numeric(20, 8), nullable=True)
    clicks = Column(Numeric(20, 8), nullable=True)
    platform_purchases = Column(Numeric(20, 8), nullable=True)
    platform_conversion_value = Column(Numeric(20, 8), nullable=True)
    sync_job_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "data_source_id", "entity_type", "external_entity_id", "source_date", "observed_at",
            name="uq_snapshot_grain",
        ),
    )


class MetaActionDaily(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_meta_actions_daily"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_external_id = Column(String(255), nullable=False)
    action_type = Column(String(128), nullable=False)
    action_count = Column(Numeric(20, 8), nullable=True)
    action_value = Column(Numeric(20, 8), nullable=True)
    cost_per_action = Column(Numeric(20, 8), nullable=True)
    attribution_setting = Column(String(64), nullable=True)
    sync_job_id = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "data_source_id", "entity_type", "entity_external_id", "date", "action_type", "attribution_setting",
            name="uq_meta_action_grain",
        ),
    )


class MetaBreakdownDaily(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_meta_breakdowns_daily"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_external_id = Column(String(255), nullable=False)
    breakdown_dimension = Column(String(64), nullable=False)
    breakdown_value = Column(String(255), nullable=False)
    impressions = Column(Numeric(20, 8), nullable=True)
    clicks = Column(Numeric(20, 8), nullable=True)
    spend_amount = Column(Numeric(20, 8), nullable=True)
    platform_conversions = Column(Numeric(20, 8), nullable=True)
    platform_conversion_value = Column(Numeric(20, 8), nullable=True)
    sync_job_id = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "data_source_id", "entity_type", "entity_external_id", "date", "breakdown_dimension", "breakdown_value",
            name="uq_meta_breakdown_grain",
        ),
    )


class GoogleKeywordDaily(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_google_keywords_daily"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    campaign_id = Column(String(36), nullable=True)
    ad_group_id = Column(String(36), nullable=True)
    criterion_id = Column(String(255), nullable=False)
    keyword_text = Column(String(1000), nullable=True)
    match_type = Column(String(64), nullable=True)
    impressions = Column(Numeric(20, 8), nullable=True)
    clicks = Column(Numeric(20, 8), nullable=True)
    cost = Column(Numeric(20, 8), nullable=True)
    conversions = Column(Numeric(20, 8), nullable=True)
    conversion_value = Column(Numeric(20, 8), nullable=True)
    currency = Column(String(8), nullable=True)
    sync_job_id = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("data_source_id", "criterion_id", "date", name="uq_google_keyword_grain"),
    )


class GoogleSearchTermDaily(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_google_search_terms_daily"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    campaign_id = Column(String(36), nullable=True)
    ad_group_id = Column(String(36), nullable=True)
    search_term = Column(String(1000), nullable=False)
    impressions = Column(Numeric(20, 8), nullable=True)
    clicks = Column(Numeric(20, 8), nullable=True)
    cost = Column(Numeric(20, 8), nullable=True)
    conversions = Column(Numeric(20, 8), nullable=True)
    conversion_value = Column(Numeric(20, 8), nullable=True)
    currency = Column(String(8), nullable=True)
    sync_job_id = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint("data_source_id", "ad_group_id", "search_term", "date", name="uq_google_search_term_grain"),
    )


class GoogleConversionActionDaily(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_google_conversion_actions_daily"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    campaign_id = Column(String(36), nullable=True)
    ad_group_id = Column(String(36), nullable=True)
    conversion_action_id = Column(String(255), nullable=False)
    conversion_action_name = Column(String(512), nullable=True)
    conversions = Column(Numeric(20, 8), nullable=True)
    conversion_value = Column(Numeric(20, 8), nullable=True)
    currency = Column(String(8), nullable=True)
    sync_job_id = Column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "data_source_id", "ad_group_id", "conversion_action_id", "date", name="uq_google_conv_action_grain"
        ),
    )
