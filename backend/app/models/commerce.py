from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dim_products"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    external_product_id = Column(String(255), nullable=False)
    title = Column(String(1000), nullable=True)
    handle = Column(String(500), nullable=True)
    vendor = Column(String(255), nullable=True)
    product_type = Column(String(255), nullable=True)
    status = Column(String(64), nullable=True)
    source_created_at = Column(DateTime(timezone=True), nullable=True)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    raw_metadata = Column(JSON, nullable=True)

    data_source = relationship("DataSource")
    __table_args__ = (
        UniqueConstraint("data_source_id", "external_product_id", name="uq_product_external"),
    )


class ProductVariant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "dim_product_variants"

    product_id = Column(String(36), ForeignKey("dim_products.id"), nullable=False, index=True)
    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    external_variant_id = Column(String(255), nullable=False)
    external_product_id = Column(String(255), nullable=True)
    sku = Column(String(255), nullable=True)
    title = Column(String(1000), nullable=True)
    price = Column(Numeric(20, 8), nullable=True)
    compare_at_price = Column(Numeric(20, 8), nullable=True)
    inventory_item_id = Column(String(255), nullable=True)

    product = relationship("Product")
    __table_args__ = (
        UniqueConstraint("data_source_id", "external_variant_id", name="uq_product_variant_external"),
    )


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_orders"

    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    external_order_id = Column(String(255), nullable=False)
    order_name = Column(String(255), nullable=True)
    order_created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    order_updated_at = Column(DateTime(timezone=True), nullable=True)
    financial_status = Column(String(64), nullable=True)
    fulfillment_status = Column(String(64), nullable=True)
    currency = Column(String(8), nullable=True)
    subtotal_amount = Column(Numeric(20, 8), nullable=True)
    discount_amount = Column(Numeric(20, 8), nullable=True)
    shipping_amount = Column(Numeric(20, 8), nullable=True)
    tax_amount = Column(Numeric(20, 8), nullable=True)
    gross_amount = Column(Numeric(20, 8), nullable=True)
    current_total_amount = Column(Numeric(20, 8), nullable=True)
    refunded_amount = Column(Numeric(20, 8), nullable=True, default=0)
    net_revenue_amount = Column(Numeric(20, 8), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    source_name = Column(String(128), nullable=True)
    provider_customer_id_hash = Column(String(128), nullable=True)
    raw_metadata = Column(JSON, nullable=True)
    sync_job_id = Column(String(36), nullable=True)

    data_source = relationship("DataSource")
    items = relationship("OrderItem", back_populates="order")
    refunds = relationship("Refund", back_populates="order")
    attribution = relationship("OrderAttribution", back_populates="order", uselist=False)
    __table_args__ = (
        UniqueConstraint("data_source_id", "external_order_id", name="uq_order_external"),
    )


class OrderItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_order_items"

    order_id = Column(String(36), ForeignKey("fact_orders.id"), nullable=False, index=True)
    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    external_line_item_id = Column(String(255), nullable=False)
    product_id = Column(String(36), nullable=True)
    variant_id = Column(String(36), nullable=True)
    sku = Column(String(255), nullable=True)
    title = Column(String(1000), nullable=True)
    quantity = Column(Numeric(20, 8), nullable=True)
    unit_price = Column(Numeric(20, 8), nullable=True)
    line_discount = Column(Numeric(20, 8), nullable=True)
    line_total = Column(Numeric(20, 8), nullable=True)
    raw_metadata = Column(JSON, nullable=True)

    order = relationship("Order", back_populates="items")
    __table_args__ = (
        UniqueConstraint("data_source_id", "external_line_item_id", name="uq_order_item_external"),
    )


class Refund(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_refunds"

    order_id = Column(String(36), ForeignKey("fact_orders.id"), nullable=False, index=True)
    data_source_id = Column(String(36), ForeignKey("data_sources.id"), nullable=False, index=True)
    external_refund_id = Column(String(255), nullable=False)
    refund_created_at = Column(DateTime(timezone=True), nullable=True)
    refund_amount = Column(Numeric(20, 8), nullable=True)
    currency = Column(String(8), nullable=True)
    reason = Column(String(1000), nullable=True)
    raw_metadata = Column(JSON, nullable=True)

    order = relationship("Order", back_populates="refunds")
    __table_args__ = (
        UniqueConstraint("data_source_id", "external_refund_id", name="uq_refund_external"),
    )


class OrderAttribution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fact_order_attribution"

    order_id = Column(String(36), ForeignKey("fact_orders.id"), nullable=False, index=True, unique=True)
    journey_ready = Column(Boolean, nullable=False, default=False)
    days_to_conversion = Column(Numeric(20, 8), nullable=True)
    first_source = Column(String(255), nullable=True)
    first_landing_page = Column(String(2000), nullable=True)
    first_referrer_url = Column(String(2000), nullable=True)
    first_utm_source = Column(String(255), nullable=True)
    first_utm_medium = Column(String(255), nullable=True)
    first_utm_campaign = Column(String(255), nullable=True)
    first_utm_content = Column(String(255), nullable=True)
    first_utm_term = Column(String(255), nullable=True)
    last_source = Column(String(255), nullable=True)
    last_landing_page = Column(String(2000), nullable=True)
    last_referrer_url = Column(String(2000), nullable=True)
    last_utm_source = Column(String(255), nullable=True)
    last_utm_medium = Column(String(255), nullable=True)
    last_utm_campaign = Column(String(255), nullable=True)
    last_utm_content = Column(String(255), nullable=True)
    last_utm_term = Column(String(255), nullable=True)
    journey_state = Column(String(32), nullable=False, default="PENDING")
    fetched_at = Column(DateTime(timezone=True), nullable=True)
    raw_metadata = Column(JSON, nullable=True)

    order = relationship("Order", back_populates="attribution")
