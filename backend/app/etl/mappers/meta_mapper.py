from typing import Any, Dict, List, Optional, Tuple

from app.etl.validators import parse_date, parse_dt, to_decimal

PLATFORM = "META_ADS"


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
        "status": raw.get("effective_status") or raw.get("status"),
        "objective": raw.get("objective"),
        "channel_type": raw.get("buying_type"),
        "channel_sub_type": None,
        "start_at": parse_dt(raw.get("start_time")),
        "end_at": parse_dt(raw.get("stop_time")),
        "raw_metadata": raw,
        "source_created_at": parse_dt(raw.get("created_time")),
        "source_updated_at": parse_dt(raw.get("updated_time")),
    }


def map_ad_group(raw: Dict[str, Any], campaign_id: str) -> Dict[str, Any]:
    targeting = raw.get("targeting") or {}
    return {
        "campaign_id": campaign_id,
        "platform": PLATFORM,
        "platform_group_type": "META_ADSET",
        "external_group_id": str(raw.get("external_id")),
        "name": raw.get("name"),
        "status": raw.get("effective_status") or raw.get("status"),
        "optimization_goal": raw.get("optimization_goal"),
        "billing_event": raw.get("billing_event"),
        "daily_budget": to_decimal(raw.get("daily_budget")),
        "lifetime_budget": to_decimal(raw.get("lifetime_budget")),
        "targeting_metadata": targeting,
        "source_created_at": parse_dt(raw.get("start_time")),
        "source_updated_at": parse_dt(raw.get("end_time")),
    }


def map_ad(raw: Dict[str, Any], data_source_id: str, campaign_id: str, ad_group_id: str) -> Dict[str, Any]:
    return {
        "data_source_id": data_source_id,
        "campaign_id": campaign_id,
        "ad_group_id": ad_group_id,
        "platform": PLATFORM,
        "external_ad_id": str(raw.get("external_id")),
        "name": raw.get("name"),
        "status": raw.get("effective_status") or raw.get("status"),
        "creative_id": str(raw.get("creative_id")) if raw.get("creative_id") else None,
        "source_created_at": parse_dt(raw.get("created_time")),
        "source_updated_at": parse_dt(raw.get("updated_time")),
        "raw_metadata": raw,
    }


def map_creative(raw: Dict[str, Any], data_source_id: str) -> Dict[str, Any]:
    return {
        "data_source_id": data_source_id,
        "platform": PLATFORM,
        "external_creative_id": str(raw.get("external_id")),
        "name": raw.get("name"),
        "title": raw.get("title"),
        "body": raw.get("body"),
        "image_url": raw.get("image_url"),
        "thumbnail_url": raw.get("thumbnail_url"),
        "video_id": raw.get("video_id"),
        "landing_page_url": raw.get("landing_page_url"),
        "cta_type": raw.get("call_to_action"),
        "raw_metadata": raw,
    }


def map_meta_entities(
    data_source_id: str,
    accounts: List[Dict[str, Any]],
    campaigns: List[Dict[str, Any]],
    creatives: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "accounts": [map_account(a) for a in accounts],
        "campaigns": [
            map_campaign(c, data_source_id, "") for c in campaigns  # account id patched by pipeline
        ],
        "creatives": [map_creative(c, data_source_id) for c in creatives],
    }


def _action_value(actions: List[Dict[str, Any]], action_type: str) -> Optional[Any]:
    for action in actions or []:
        if action.get("action_type") == action_type:
            return action.get("value")
    return None


def map_performance(
    row: Dict[str, Any],
    data_source_id: str,
    marketing_account_id: Optional[str],
    entity_id_map: Dict[Tuple[str, str], str],
    sync_job_id: Optional[str],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    entity_type = row["entity_type"]
    external_id = str(row["external_entity_id"])
    entity_id = entity_id_map.get((entity_type, external_id))
    spend = to_decimal(row.get("spend"))
    impressions = to_decimal(row.get("impressions"))
    clicks = to_decimal(row.get("clicks"))
    purchases = to_decimal(_action_value(row.get("actions"), "purchase"))
    purchase_value = to_decimal(_action_value(row.get("action_values"), "purchase"))
    conversions = purchases
    conversion_value = purchase_value

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
        "reach": to_decimal(row.get("reach")),
        "clicks": clicks,
        "link_clicks": to_decimal(row.get("inline_link_clicks")),
        "outbound_clicks": to_decimal(row.get("outbound_clicks")),
        "spend_amount": spend,
        "platform_conversions": conversions,
        "platform_conversion_value": conversion_value,
        "platform_purchases": purchases,
        "platform_purchase_value": purchase_value,
        "cpm": to_decimal(row.get("cpm")),
        "cpc": to_decimal(row.get("cpc")),
        "ctr": to_decimal(row.get("ctr")),
        "frequency": to_decimal(row.get("frequency")),
        "platform_reported_roas": to_decimal(row.get("purchase_roas")),
        "source_attribution_metadata": {"attribution_setting": row.get("attribution_setting")},
        "sync_job_id": sync_job_id,
        "source_updated_at": row.get("updated_time"),
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
        "platform_purchases": purchases,
        "platform_conversion_value": conversion_value,
        "sync_job_id": sync_job_id,
    }

    actions = []
    for action in row.get("actions") or []:
        action_type = action.get("action_type")
        if not action_type:
            continue
        actions.append(
            {
                "data_source_id": data_source_id,
                "date": parse_date(row["date"]),
                "entity_type": entity_type,
                "entity_external_id": external_id,
                "action_type": action_type,
                "action_count": to_decimal(action.get("value")),
                "action_value": to_decimal(_action_value(row.get("action_values"), action_type)),
                "cost_per_action": to_decimal(
                    _action_value(row.get("cost_per_action_type"), action_type)
                ),
                "attribution_setting": row.get("attribution_setting"),
                "sync_job_id": sync_job_id,
            }
        )

    breakdowns = []
    for dimension, rows in (row.get("breakdowns") or {}).items():
        for item in rows:
            breakdowns.append(
                {
                    "data_source_id": data_source_id,
                    "date": parse_date(row["date"]),
                    "entity_type": entity_type,
                    "entity_external_id": external_id,
                    "breakdown_dimension": dimension,
                    "breakdown_value": str(item.get("breakdown_value")),
                    "impressions": to_decimal(item.get("impressions")),
                    "clicks": to_decimal(item.get("clicks")),
                    "spend_amount": to_decimal(item.get("spend")),
                    "platform_conversions": to_decimal(item.get("platform_conversions")),
                    "platform_conversion_value": to_decimal(item.get("platform_conversion_value")),
                    "sync_job_id": sync_job_id,
                }
            )
    return perf, snapshot, actions, breakdowns
