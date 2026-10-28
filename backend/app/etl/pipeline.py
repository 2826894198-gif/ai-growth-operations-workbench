import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl import mappers
from app.etl.validators import (
    dq_impressions_lt_clicks,
    dq_negative_spend,
    dq_order_total_invalid,
    dq_refund_gt_order,
    dq_unknown_currency,
    parse_date,
    parse_dt,
    to_decimal,
)
from app.ingestion.idempotency import upsert_by
from app.models.ad_performance import (
    AdPerformanceDaily,
    AdPerformanceSnapshot,
    GoogleConversionActionDaily,
    GoogleKeywordDaily,
    GoogleSearchTermDaily,
    MetaActionDaily,
    MetaBreakdownDaily,
)
from app.models.commerce import Order, OrderAttribution, OrderItem, Product, ProductVariant, Refund
from app.models.data_quality import DataQualityIssue
from app.models.marketing import Ad, AdGroup, AssetGroup, Campaign, Creative

logger = logging.getLogger(__name__)


@dataclass
class EtlCounts:
    records_received: int = 0
    inserted: int = 0
    updated: int = 0
    failed: int = 0
    dq_issues: List[Dict[str, Any]] = field(default_factory=list)

    def add(self, inserted: bool) -> None:
        self.records_received += 1
        if inserted:
            self.inserted += 1
        else:
            self.updated += 1


async def _record_dq(db: AsyncSession, data_source_id: str, issue: Dict[str, Any]) -> None:
    if issue is None:
        return
    existing = (
        await db.execute(
            select(DataQualityIssue).where(
                DataQualityIssue.data_source_id == data_source_id,
                DataQualityIssue.rule_code == issue["rule_code"],
                DataQualityIssue.entity_type == issue.get("entity_type"),
                DataQualityIssue.entity_id == issue.get("entity_id"),
                DataQualityIssue.date == issue.get("date"),
                DataQualityIssue.status == "OPEN",
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            DataQualityIssue(
                data_source_id=data_source_id,
                rule_code=issue["rule_code"],
                severity=issue["severity"],
                entity_type=issue.get("entity_type"),
                entity_id=issue.get("entity_id"),
                date=issue.get("date"),
                message=issue.get("message"),
                context=issue.get("context"),
                status="OPEN",
            )
        )


async def _resolve_account_id(
    db: AsyncSession, data_source_id: str, accounts: List[Dict[str, Any]], counts: EtlCounts, platform: str
) -> Optional[str]:
    if accounts:
        from app.models.marketing import MarketingAccount

        values = (
            mappers.meta_mapper.map_account(accounts[0])
            if platform == "META_ADS"
            else mappers.google_mapper.map_account(accounts[0])
        )
        inserted, account = await upsert_by(
            db, MarketingAccount, ["data_source_id", "external_account_id"],
            {**values, "data_source_id": data_source_id},
        )
        counts.add(inserted)
        return str(account.id)
    from app.models.marketing import MarketingAccount

    account = (
        await db.execute(
            select(MarketingAccount).where(MarketingAccount.data_source_id == data_source_id).limit(1)
        )
    ).scalar_one_or_none()
    return str(account.id) if account else None


async def run_meta_pipeline(
    db: AsyncSession,
    data_source_id: str,
    *,
    accounts: List[Dict[str, Any]],
    campaigns: List[Dict[str, Any]],
    ad_groups: List[Dict[str, Any]],
    ads: List[Dict[str, Any]],
    creatives: List[Dict[str, Any]],
    performance: List[Dict[str, Any]],
    sync_job_id: str,
) -> EtlCounts:
    counts = EtlCounts(records_received=sum(len(x) for x in (accounts, campaigns, ad_groups, ads, creatives, performance)))
    account_id = await _resolve_account_id(db, data_source_id, accounts, counts, "META_ADS")

    campaign_map: Dict[str, str] = {}
    for raw in campaigns:
        values = mappers.meta_mapper.map_campaign(raw, data_source_id, account_id)
        inserted, obj = await upsert_by(
            db,
            Campaign,
            ["platform", "marketing_account_id", "external_campaign_id"],
            values,
        )
        counts.add(inserted)
        campaign_map[str(raw.get("external_id"))] = obj.id

    ad_group_map: Dict[str, str] = {}
    for raw in ad_groups:
        campaign_id = campaign_map.get(str(raw.get("campaign_external_id")))
        if campaign_id is None:
            counts.failed += 1
            continue
        values = mappers.meta_mapper.map_ad_group(raw, campaign_id)
        inserted, obj = await upsert_by(db, AdGroup, ["campaign_id", "external_group_id"], values)
        counts.add(inserted)
        ad_group_map[str(raw.get("external_id"))] = obj.id

    ad_map: Dict[str, str] = {}
    for raw in ads:
        campaign_id = campaign_map.get(str(raw.get("campaign_external_id")))
        ad_group_id = ad_group_map.get(str(raw.get("ad_group_external_id")))
        if campaign_id is None:
            counts.failed += 1
            continue
        values = mappers.meta_mapper.map_ad(raw, data_source_id, campaign_id, ad_group_id)
        inserted, obj = await upsert_by(db, Ad, ["data_source_id", "external_ad_id"], values)
        counts.add(inserted)
        ad_map[str(raw.get("external_id"))] = obj.id

    for raw in creatives:
        values = mappers.meta_mapper.map_creative(raw, data_source_id)
        inserted, _ = await upsert_by(db, Creative, ["data_source_id", "external_creative_id"], values)
        counts.add(inserted)

    entity_id_map: Dict[tuple, str] = {}
    entity_id_map.update({("CAMPAIGN", k): v for k, v in campaign_map.items()})
    entity_id_map.update({("AD_GROUP", k): v for k, v in ad_group_map.items()})
    entity_id_map.update({("AD", k): v for k, v in ad_map.items()})

    for row in performance:
        row = {**row, "observed_at": datetime.now(timezone.utc)}
        perf, snapshot, actions, breakdowns = mappers.meta_mapper.map_performance(
            row, data_source_id, account_id, entity_id_map, sync_job_id
        )
        issue = dq_negative_spend(perf["spend_amount"], perf["external_entity_id"])
        if issue:
            counts.dq_issues.append(issue)
            await _record_dq(db, data_source_id, {**issue, "entity_type": perf["entity_type"], "entity_id": perf["external_entity_id"], "date": perf["date"]})
        issue = dq_impressions_lt_clicks(perf["impressions"], perf["clicks"], perf["external_entity_id"])
        if issue:
            counts.dq_issues.append(issue)
            await _record_dq(db, data_source_id, {**issue, "entity_type": perf["entity_type"], "entity_id": perf["external_entity_id"], "date": perf["date"]})
        issue = dq_unknown_currency(perf["currency"], perf["external_entity_id"])
        if issue:
            await _record_dq(db, data_source_id, {**issue, "entity_type": perf["entity_type"], "entity_id": perf["external_entity_id"], "date": perf["date"]})
        inserted, _ = await upsert_by(
            db,
            AdPerformanceDaily,
            ["data_source_id", "entity_type", "external_entity_id", "date"],
            perf,
        )
        counts.add(inserted)
        inserted, _ = await upsert_by(
            db,
            AdPerformanceSnapshot,
            ["data_source_id", "entity_type", "external_entity_id", "source_date", "observed_at"],
            snapshot,
        )
        counts.add(inserted)
        for action in actions:
            inserted, _ = await upsert_by(
                db,
                MetaActionDaily,
                ["data_source_id", "entity_type", "entity_external_id", "date", "action_type", "attribution_setting"],
                action,
            )
            counts.add(inserted)
        for breakdown in breakdowns:
            inserted, _ = await upsert_by(
                db,
                MetaBreakdownDaily,
                ["data_source_id", "entity_type", "entity_external_id", "date", "breakdown_dimension", "breakdown_value"],
                breakdown,
            )
            counts.add(inserted)
    return counts


async def run_google_pipeline(
    db: AsyncSession,
    data_source_id: str,
    *,
    accounts: List[Dict[str, Any]],
    campaigns: List[Dict[str, Any]],
    ad_groups: List[Dict[str, Any]],
    ads: List[Dict[str, Any]],
    asset_groups: List[Dict[str, Any]],
    keywords: List[Dict[str, Any]],
    search_terms: List[Dict[str, Any]],
    conversion_actions: List[Dict[str, Any]],
    performance: List[Dict[str, Any]],
    sync_job_id: str,
) -> EtlCounts:
    counts = EtlCounts(
        records_received=sum(
            len(x) for x in (accounts, campaigns, ad_groups, ads, asset_groups, keywords, search_terms, conversion_actions, performance)
        )
    )
    account_id = await _resolve_account_id(db, data_source_id, accounts, counts, "GOOGLE_ADS")

    campaign_map: Dict[str, str] = {}
    for raw in campaigns:
        values = mappers.google_mapper.map_campaign(raw, data_source_id, account_id)
        inserted, obj = await upsert_by(db, Campaign, ["platform", "marketing_account_id", "external_campaign_id"], values)
        counts.add(inserted)
        campaign_map[str(raw.get("external_id"))] = obj.id

    ad_group_map: Dict[str, str] = {}
    for raw in ad_groups:
        campaign_id = campaign_map.get(str(raw.get("campaign_external_id")))
        if campaign_id is None:
            counts.failed += 1
            continue
        values = mappers.google_mapper.map_ad_group(raw, campaign_id)
        inserted, obj = await upsert_by(db, AdGroup, ["campaign_id", "external_group_id"], values)
        counts.add(inserted)
        ad_group_map[str(raw.get("external_id"))] = obj.id

    ad_map: Dict[str, str] = {}
    for raw in ads:
        campaign_id = campaign_map.get(str(raw.get("campaign_external_id")))
        ad_group_id = ad_group_map.get(str(raw.get("ad_group_external_id")))
        if campaign_id is None:
            counts.failed += 1
            continue
        values = mappers.google_mapper.map_ad(raw, data_source_id, campaign_id, ad_group_id)
        inserted, obj = await upsert_by(db, Ad, ["data_source_id", "external_ad_id"], values)
        counts.add(inserted)
        ad_map[str(raw.get("external_id"))] = obj.id

    asset_group_map: Dict[str, str] = {}
    for raw in asset_groups:
        campaign_id = campaign_map.get(str(raw.get("campaign_external_id")))
        values = mappers.google_mapper.map_asset_group(raw, data_source_id, campaign_id)
        inserted, obj = await upsert_by(db, AssetGroup, ["data_source_id", "external_asset_group_id"], values)
        counts.add(inserted)
        asset_group_map[str(raw.get("external_id"))] = obj.id

    entity_id_map: Dict[tuple, str] = {}
    entity_id_map.update({("CAMPAIGN", k): v for k, v in campaign_map.items()})
    entity_id_map.update({("AD_GROUP", k): v for k, v in ad_group_map.items()})
    entity_id_map.update({("AD", k): v for k, v in ad_map.items()})
    entity_id_map.update({("ASSET_GROUP", k): v for k, v in asset_group_map.items()})

    for row in performance:
        row = {**row, "observed_at": datetime.now(timezone.utc)}
        perf, snapshot, kw_rows, st_rows, ca_rows = mappers.google_mapper.map_performance(
            row, data_source_id, account_id, entity_id_map, sync_job_id
        )
        issue = dq_negative_spend(perf["spend_amount"], perf["external_entity_id"])
        if issue:
            await _record_dq(db, data_source_id, {**issue, "entity_type": perf["entity_type"], "entity_id": perf["external_entity_id"], "date": perf["date"]})
        issue = dq_impressions_lt_clicks(perf["impressions"], perf["clicks"], perf["external_entity_id"])
        if issue:
            await _record_dq(db, data_source_id, {**issue, "entity_type": perf["entity_type"], "entity_id": perf["external_entity_id"], "date": perf["date"]})
        inserted, _ = await upsert_by(
            db, AdPerformanceDaily, ["data_source_id", "entity_type", "external_entity_id", "date"], perf
        )
        counts.add(inserted)
        inserted, _ = await upsert_by(
            db, AdPerformanceSnapshot,
            ["data_source_id", "entity_type", "external_entity_id", "source_date", "observed_at"],
            snapshot,
        )
        counts.add(inserted)
        for kw in kw_rows:
            inserted, _ = await upsert_by(db, GoogleKeywordDaily, ["data_source_id", "criterion_id", "date"], kw)
            counts.add(inserted)
        for st in st_rows:
            inserted, _ = await upsert_by(
                db, GoogleSearchTermDaily, ["data_source_id", "ad_group_id", "search_term", "date"], st
            )
            counts.add(inserted)
        for ca in ca_rows:
            inserted, _ = await upsert_by(
                db, GoogleConversionActionDaily,
                ["data_source_id", "ad_group_id", "conversion_action_id", "date"], ca,
            )
            counts.add(inserted)
    return counts


async def run_shopify_pipeline(
    db: AsyncSession,
    data_source_id: str,
    *,
    products: List[Dict[str, Any]],
    variants: List[Dict[str, Any]],
    orders: List[Dict[str, Any]],
    order_items: List[Dict[str, Any]],
    refunds: List[Dict[str, Any]],
    journeys: List[Dict[str, Any]],
    sync_job_id: str,
) -> EtlCounts:
    counts = EtlCounts(
        records_received=sum(len(x) for x in (products, variants, orders, order_items, refunds, journeys))
    )
    product_map: Dict[str, str] = {}
    for raw in products:
        values = mappers.shopify_mapper.map_product(raw, data_source_id)
        inserted, obj = await upsert_by(db, Product, ["data_source_id", "external_product_id"], values)
        counts.add(inserted)
        product_map[str(raw.get("external_id"))] = obj.id

    variant_map: Dict[str, str] = {}
    for raw in variants:
        product_id = product_map.get(str(raw.get("product_external_id")))
        if product_id is None:
            counts.failed += 1
            continue
        values = mappers.shopify_mapper.map_variant(raw, data_source_id, product_id)
        inserted, obj = await upsert_by(db, ProductVariant, ["data_source_id", "external_variant_id"], values)
        counts.add(inserted)
        variant_map[str(raw.get("external_id"))] = obj.id

    order_map: Dict[str, str] = {}
    for raw in orders:
        values = mappers.shopify_mapper.map_commerce(data_source_id, [raw], [], [], {}, {}, {}, sync_job_id)["orders"][0]
        inserted, obj = await upsert_by(db, Order, ["data_source_id", "external_order_id"], values)
        counts.add(inserted)
        order_map[str(raw.get("external_id"))] = obj.id
        gross = values.get("gross_amount")
        refunded = values.get("refunded_amount")
        issue = dq_refund_gt_order(refunded, gross, str(raw.get("external_id")))
        if issue:
            await _record_dq(db, data_source_id, {**issue, "entity_type": "ORDER", "entity_id": str(raw.get("external_id")), "date": parse_date(raw.get("created_at"))})
        issue = dq_order_total_invalid(
            values.get("gross_amount"), values.get("subtotal_amount"), values.get("shipping_amount"),
            values.get("tax_amount"), values.get("discount_amount"), str(raw.get("external_id")),
        )
        if issue:
            await _record_dq(db, data_source_id, {**issue, "entity_type": "ORDER", "entity_id": str(raw.get("external_id")), "date": parse_date(raw.get("created_at"))})

    for raw in order_items:
        order_id = order_map.get(raw.get("order_external_id"))
        if order_id is None:
            counts.failed += 1
            continue
        values = {
            "order_id": order_id,
            "data_source_id": data_source_id,
            "external_line_item_id": str(raw.get("line_item_id")),
            "product_id": product_map.get(str(raw.get("product_external_id"))),
            "variant_id": variant_map.get(str(raw.get("variant_external_id"))),
            "sku": raw.get("sku"),
            "title": raw.get("title"),
            "quantity": to_decimal(raw.get("quantity")),
            "unit_price": to_decimal(raw.get("unit_price")),
            "line_discount": to_decimal(raw.get("line_discount")),
            "line_total": to_decimal(raw.get("line_total")),
            "raw_metadata": raw,
        }
        inserted, _ = await upsert_by(db, OrderItem, ["data_source_id", "external_line_item_id"], values)
        counts.add(inserted)

    for raw in refunds:
        order_id = order_map.get(raw.get("order_external_id"))
        if order_id is None:
            counts.failed += 1
            continue
        values = {
            "order_id": order_id,
            "data_source_id": data_source_id,
            "external_refund_id": str(raw.get("refund_id")),
            "refund_created_at": parse_dt(raw.get("created_at")),
            "refund_amount": to_decimal(raw.get("amount")),
            "currency": raw.get("currency", "USD"),
            "reason": raw.get("reason"),
            "raw_metadata": raw,
        }
        inserted, _ = await upsert_by(db, Refund, ["data_source_id", "external_refund_id"], values)
        counts.add(inserted)

    for raw in journeys:
        order_id = order_map.get(raw.get("order_external_id"))
        if order_id is None:
            continue
        values = mappers.shopify_mapper.map_journey(raw)
        inserted, _ = await upsert_by(db, OrderAttribution, ["order_id"], {**values, "order_id": order_id})
        counts.add(inserted)
    return counts
