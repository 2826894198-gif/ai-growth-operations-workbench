from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.etl.validators import parse_date, parse_dt, to_decimal

PLATFORM = "GOOGLE_ADS"
MICROS = Decimal("1000000")


def map_account(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "platform": PLATFORM,
        "external_account_id": raw.get("external_account_id"),
        "name": raw.get("name"),
        "currency": raw.get("currency"),
        "timezone": raw.get("timezone"),
        "status": "ACTIVE",
    }


def map_campaign(raw: Dict[str, Any], data_source_id: str, marketing_account_id: str) -> Dict[str, Any]:
    return {
        "data_source_id": data_source_id,
        "marketing_account_id": marketing_account_id,
        "platform": PLATFORM,
        "external_campaign_id": str(raw.get("external_id")),
        "name": raw.get("name"),
        "status": raw.get("status"),
        "objective": None,
        "channel_type": raw.get("channel_type"),
        "channel_sub_type": raw.get("channel_sub_type"),
        "start_at": parse_dt(raw.get("start_time")),
        "end_at": parse_dt(raw.get("end_time")),
        "raw_metadata": raw,
        "source_created_at": parse_dt(raw.get("start_time")),
        "source_updated_at": parse_dt(raw.get("updated_time")),
    }


def map_ad_group(raw: Dict[str, Any], campaign_id: str) -> Dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "platform": PLATFORM,
        "platform_group_type": "GOOGLE_ADGROUP",
        "external_group_id": str(raw.get("external_id")),
        "name": raw.get("name"),
        "status": raw.get("status"),
        "optimization_goal": None,
        "billing_event": None,
        "daily_budget": None,
        "lifetime_budget": None,
        "targeting_metadata": raw.get("targeting") or {},
        "source_created_at": None,
        "source_updated_at": None,
    }


def map_ad(raw: Dict[str, Any], data_source_id: str, campaign_id: str, ad_group_id: str) -> Dict[str, Any]:
    return {
        "data_source_id": data_source_id,
        "campaign_id": campaign_id,
        "ad_group_id": ad_group_id,
        "platform": PLATFORM,
        "external_ad_id": str(raw.get("external_id")),
        "name": raw.get("name"),
        "status": raw.get("status"),
        "creative_id": raw.get("creative_id"),
        "source_created_at": None,
        "source_updated_at": None,
        "raw_metadata": raw,
    }


def map_asset_group(raw: Dict[str, Any], data_source_id: str, campaign_id: Optional[str]) -> Dict[str, Any]:
    return {
        "data_source_id": data_source_id,
        "campaign_id": campaign_id,
        "platform": PLATFORM,
        "external_asset_group_id": str(raw.get("external_id")),
        "name": raw.get("name"),
        "status": raw.get("status"),
        "raw_metadata": raw,
    }


def map_keyword(raw: Dict[str, Any], data_source_id: str) -> Dict[str, Any]:
    return {
        "data_source_id": data_source_id,
        "criterion_id": str(raw.get("criterion_id")),
        "ad_group_id": raw.get("_ad_group_id"),
        "keyword_text": raw.get("keyword_text"),
        "match_type": raw.get("match_type"),
    }


def map_performance(
    row: Dict[str, Any],
    data_source_id: str,
    marketing_account_id: Optional[str],
    entity_id_map: Dict[Tuple[str, str], str],
    sync_job_id: Optional[str],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    entity_type = row["entity_type"]
    external_id = str(row["external_entity_id"])
    entity_id = entity_id_map.get((entity_type, external_id))
    cost_micros = row.get("cost_micros")
    spend = to_decimal(cost_micros) / MICROS if cost_micros is not None else None
    if spend is not None:
        spend = spend.quantize(Decimal("0.000001"))
    impressions = to_decimal(row.get("impressions"))
    clicks = to_decimal(row.get("clicks"))
    conversions = to_decimal(row.get("conversions"))
    conversion_value = to_decimal(row.get("conversion_value"))

    perf = {
        "data_source_id": data_source_id,
        "marketing_account_id": marketing_account_id,
        "platform": PLATFORM,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "external_entity_id": external_id,
        "date": parse_date(row["date"]),
        "currency": row.get("currency"),
        "impressions": impressions,
        "reach": None,
        "clicks": clicks,
        "link_clicks": clicks,
        "outbound_clicks": None,
        "spend_amount": spend,
        "platform_conversions": conversions,
        "platform_conversion_value": conversion_value,
        "platform_purchases": None,
        "platform_purchase_value": None,
        "cpm": to_decimal(row.get("cpm")),
        "cpc": to_decimal(row.get("cpc")),
        "ctr": to_decimal(row.get("ctr")),
        "frequency": None,
        "platform_reported_roas": None,
        "source_attribution_metadata": {"cost_micros": cost_micros},
        "sync_job_id": sync_job_id,
        "source_updated_at": None,
    }

    snapshot = {
        "data_source_id": data_source_id,
        "platform": PLATFORM,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "external_entity_id": external_id,
        "source_date": parse_date(row["date"]),
        "observed_at": row.get("observed_at"),
        "currency": row.get("currency"),
        "spend_amount": spend,
        "impressions": impressions,
        "clicks": clicks,
        "platform_purchases": None,
        "platform_conversion_value": conversion_value,
        "sync_job_id": sync_job_id,
    }

    keywords = []
    for keyword in row.get("keywords") or []:
        keywords.append(
            {
                "data_source_id": data_source_id,
                "date": parse_date(row["date"]),
                "campaign_id": entity_id if entity_type == "CAMPAIGN" else None,
                "ad_group_id": entity_id if entity_type == "AD_GROUP" else None,
                "criterion_id": str(keyword.get("criterion_id")),
                "keyword_text": keyword.get("keyword_text"),
                "match_type": keyword.get("match_type"),
                "impressions": impressions,
                "clicks": clicks,
                "cost": spend,
                "conversions": conversions,
                "conversion_value": conversion_value,
                "currency": row.get("currency"),
                "sync_job_id": sync_job_id,
            }
        )

    search_terms = []
    for term in row.get("search_terms") or []:
        search_terms.append(
            {
                "data_source_id": data_source_id,
                "date": parse_date(row["date"]),
                "campaign_id": entity_id if entity_type == "CAMPAIGN" else None,
                "ad_group_id": entity_id if entity_type == "AD_GROUP" else None,
                "search_term": term.get("search_term"),
                "impressions": impressions,
                "clicks": clicks,
                "cost": spend,
                "conversions": conversions,
                "conversion_value": conversion_value,
                "currency": row.get("currency"),
                "sync_job_id": sync_job_id,
            }
        )

    conversion_actions = []
    for action in row.get("conversion_actions") or []:
        conversion_actions.append(
            {
                "data_source_id": data_source_id,
                "date": parse_date(row["date"]),
                "campaign_id": entity_id if entity_type == "CAMPAIGN" else None,
                "ad_group_id": entity_id if entity_type == "AD_GROUP" else None,
                "conversion_action_id": str(action.get("conversion_action_id")),
                "conversion_action_name": action.get("conversion_action_name"),
                "conversions": to_decimal(action.get("conversions")) if action.get("conversions") is not None else conversions,
                "conversion_value": to_decimal(action.get("conversion_value")) if action.get("conversion_value") is not None else conversion_value,
                "currency": row.get("currency"),
                "sync_job_id": sync_job_id,
            }
        )
    return perf, snapshot, keywords, search_terms, conversion_actions
