from sqlalchemy import JSON, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MarketingAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dim_marketing_accounts"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    platform = Column(String(32), nullable=False)
    external_account_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    currency = Column(String(8), nullable=True)
    timezone = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE")

    data_source = relationship("DataSource")
    __table_args__ = (
        UniqueConstraint("data_source_id", "external_account_id", name="uq_marketing_account_external"),
    )


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dim_campaigns"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    marketing_account_id = Column(String(36), ForeignKey("dim_marketing_accounts.id"), nullable=False, index=True)
    platform = Column(String(32), nullable=False)
    external_campaign_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    status = Column(String(64), nullable=True)
    objective = Column(String(128), nullable=True)
    channel_type = Column(String(64), nullable=True)
    channel_sub_type = Column(String(64), nullable=True)
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True)
    raw_metadata = Column(JSON, nullable=True)
    source_created_at = Column(DateTime(timezone=True), nullable=True)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)

    data_source = relationship("DataSource")
    marketing_account = relationship("MarketingAccount")
    __table_args__ = (
        UniqueConstraint(
            "platform", "marketing_account_id", "external_campaign_id", name="uq_campaign_platform_external"
        ),
    )


class AdGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dim_ad_groups"

    campaign_id = Column(String(36), ForeignKey("dim_campaigns.id"), nullable=False, index=True)
    platform = Column(String(32), nullable=False)
    platform_group_type = Column(String(32), nullable=True, default="ADSET")
    external_group_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    status = Column(String(64), nullable=True)
    optimization_goal = Column(String(128), nullable=True)
    billing_event = Column(String(128), nullable=True)
    daily_budget = Column(Numeric(20, 8), nullable=True)
    lifetime_budget = Column(Numeric(20, 8), nullable=True)
    targeting_metadata = Column(JSON, nullable=True)
    source_created_at = Column(DateTime(timezone=True), nullable=True)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)

    campaign = relationship("Campaign")
    __table_args__ = (
        UniqueConstraint("campaign_id", "external_group_id", name="uq_ad_group_external"),
    )


class Ad(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dim_ads"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("dim_campaigns.id"), nullable=False, index=True)
    ad_group_id = Column(String(36), ForeignKey("dim_ad_groups.id"), nullable=True, index=True)
    platform = Column(String(32), nullable=False)
    external_ad_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    status = Column(String(64), nullable=True)
    creative_id = Column(String(255), nullable=True)
    source_created_at = Column(DateTime(timezone=True), nullable=True)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    raw_metadata = Column(JSON, nullable=True)

    campaign = relationship("Campaign")
    ad_group = relationship("AdGroup")
    __table_args__ = (
        UniqueConstraint("data_source_id", "external_ad_id", name="uq_ad_external"),
    )


class Creative(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dim_creatives"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    platform = Column(String(32), nullable=False)
    external_creative_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    title = Column(String(1000), nullable=True)
    body = Column(String(4000), nullable=True)
    image_url = Column(String(2000), nullable=True)
    thumbnail_url = Column(String(2000), nullable=True)
    video_id = Column(String(255), nullable=True)
    landing_page_url = Column(String(2000), nullable=True)
    cta_type = Column(String(128), nullable=True)
    raw_metadata = Column(JSON, nullable=True)

    data_source = relationship("DataSource")
    __table_args__ = (
        UniqueConstraint("data_source_id", "external_creative_id", name="uq_creative_external"),
    )


class AssetGroup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Asset Group (Performance Max) metadata - kept separate from Ad Groups."""

    __tablename__ = "dim_asset_groups"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    campaign_id = Column(String(36), ForeignKey("dim_campaigns.id"), nullable=True, index=True)
    platform = Column(String(32), nullable=False)
    external_asset_group_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    status = Column(String(64), nullable=True)
    raw_metadata = Column(JSON, nullable=True)

    campaign = relationship("Campaign")
    __table_args__ = (
        UniqueConstraint("data_source_id", "external_asset_group_id", name="uq_asset_group_external"),
    )
