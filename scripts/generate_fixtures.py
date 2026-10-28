"""Generate entirely synthetic provider fixtures used by mock mode and tests.

Run from repo root:  python scripts/generate_fixtures.py
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures"


def _dt(day: date, hour: int = 12) -> str:
    return f"{day.isoformat()}T{hour:02d}:00:00+00:00"


def _amount(value: float) -> float:
    return round(value, 4)


def build_meta(days: int, rng: random.Random, scenario: str) -> dict:
    campaigns = [
        {
            "external_id": "238471111101",
            "name": "US Prospecting - Broad",
            "status": "ACTIVE",
            "objective": "OUTCOME_PURCHASES",
            "buying_type": "AUCTION",
            "start_time": _dt(date.today() - timedelta(days=60)),
            "stop_time": None,
            "created_time": _dt(date.today() - timedelta(days=60)),
            "updated_time": _dt(date.today() - timedelta(days=1)),
        },
        {
            "external_id": "238471111102",
            "name": "US Retargeting - CBO",
            "status": "ACTIVE",
            "objective": "OUTCOME_PURCHASES",
            "buying_type": "AUCTION",
            "start_time": _dt(date.today() - timedelta(days=30)),
            "stop_time": None,
            "created_time": _dt(date.today() - timedelta(days=30)),
            "updated_time": _dt(date.today() - timedelta(days=1)),
        },
    ]
    ad_groups = [
        {
            "external_id": "238471222201",
            "campaign_external_id": "238471111101",
            "name": "Prospecting - US - Women",
            "status": "ACTIVE",
            "optimization_goal": "PURCHASES",
            "billing_event": "IMPRESSIONS",
            "daily_budget": 120.0,
            "lifetime_budget": None,
            "start_time": _dt(date.today() - timedelta(days=60)),
            "end_time": None,
            "targeting": {
                "countries": ["US"],
                "age_min": 25,
                "age_max": 45,
                "genders": [1],
                "placements": ["instagram", "facebook_feed"],
            },
        },
        {
            "external_id": "238471222202",
            "campaign_external_id": "238471111101",
            "name": "Prospecting - US - Men",
            "status": "ACTIVE",
            "optimization_goal": "PURCHASES",
            "billing_event": "IMPRESSIONS",
            "daily_budget": 100.0,
            "lifetime_budget": None,
            "start_time": _dt(date.today() - timedelta(days=60)),
            "end_time": None,
            "targeting": {"countries": ["US"], "age_min": 18, "age_max": 65, "genders": [2], "placements": ["instagram"]},
        },
        {
            "external_id": "238471222203",
            "campaign_external_id": "238471111102",
            "name": "Retargeting - All",
            "status": "ACTIVE",
            "optimization_goal": "PURCHASES",
            "billing_event": "IMPRESSIONS",
            "daily_budget": 80.0,
            "lifetime_budget": None,
            "start_time": _dt(date.today() - timedelta(days=30)),
            "end_time": None,
            "targeting": {"countries": ["US"], "placements": ["facebook_feed", "instagram"]},
        },
    ]
    creatives = [
        {
            "external_id": "238471333301",
            "name": "Creative - Summer Sale A",
            "object_type": "VIDEO",
            "title": "Summer Sale - 30% Off",
            "body": "Limited time offer on all orders.",
            "thumbnail_url": "https://cdn.example.test/thumb-a.jpg",
            "image_url": None,
            "video_id": "video-aaa",
            "call_to_action": "SHOP_NOW",
            "landing_page_url": "https://shop.example.test/?utm_source=meta&utm_campaign=sale",
            "url_tags": "utm_source=meta&utm_campaign=sale",
        },
        {
            "external_id": "238471333302",
            "name": "Creative - Summer Sale B",
            "object_type": "IMAGE",
            "title": "New Collection",
            "body": "Discover the new collection.",
            "thumbnail_url": "https://cdn.example.test/thumb-b.jpg",
            "image_url": "https://cdn.example.test/img-b.jpg",
            "video_id": None,
            "call_to_action": "LEARN_MORE",
            "landing_page_url": "https://shop.example.test/?utm_source=meta&utm_campaign=collection",
            "url_tags": None,
        },
    ]
    ads = [
        {
            "external_id": "238471444401",
            "campaign_external_id": "238471111101",
            "ad_group_external_id": "238471222201",
            "name": "Ad - Summer Sale A - Women",
            "status": "ACTIVE",
            "creative_id": "238471333301",
            "created_time": _dt(date.today() - timedelta(days=60)),
            "updated_time": _dt(date.today() - timedelta(days=1)),
        },
        {
            "external_id": "238471444402",
            "campaign_external_id": "238471111101",
            "ad_group_external_id": "238471222202",
            "name": "Ad - Summer Sale B - Men",
            "status": "ACTIVE",
            "creative_id": "238471333302",
            "created_time": _dt(date.today() - timedelta(days=60)),
            "updated_time": _dt(date.today() - timedelta(days=1)),
        },
        {
            "external_id": "238471444403",
            "campaign_external_id": "238471111102",
            "ad_group_external_id": "238471222203",
            "name": "Ad - Retarget - A",
            "status": "ACTIVE",
            "creative_id": "238471333301",
            "created_time": _dt(date.today() - timedelta(days=30)),
            "updated_time": _dt(date.today() - timedelta(days=1)),
        },
    ]

    entity_map = [
        ("CAMPAIGN", "238471111101"),
        ("CAMPAIGN", "238471111102"),
        ("AD_GROUP", "238471222201"),
        ("AD_GROUP", "238471222202"),
        ("AD_GROUP", "238471222203"),
        ("AD", "238471444401"),
        ("AD", "238471444402"),
        ("AD", "238471444403"),
    ]
    performance = []
    for offset in range(days):
        day = date.today() - timedelta(days=days - 1 - offset)
        for entity_type, external_id in entity_map:
            spend = rng.uniform(120, 420) if scenario == "healthy_growth" else rng.uniform(80, 200)
            if scenario == "zero_purchase_burn":
                purchases = 0
                conv_value = 0.0
            else:
                purchases = int(rng.uniform(1, 5))
                conv_value = purchases * rng.uniform(55, 75)
            impressions = int(rng.uniform(18000, 52000))
            if scenario == "meta_creative_fatigue":
                impressions = int(rng.uniform(50000, 90000))
            clicks = int(impressions * rng.uniform(0.004, 0.011))
            if scenario == "meta_creative_fatigue":
                clicks = int(impressions * rng.uniform(0.0015, 0.003))
            actions = [
                {"action_type": "link_click", "value": clicks},
                {"action_type": "purchase", "value": purchases},
                {"action_type": "add_to_cart", "value": int(rng.uniform(1, 8))},
            ]
            performance.append(
                {
                    "date": day.isoformat(),
                    "entity_type": entity_type,
                    "external_entity_id": external_id,
                    "impressions": impressions,
                    "reach": int(impressions * rng.uniform(0.72, 0.9)),
                    "frequency": round(rng.uniform(1.1, 2.4), 3),
                    "clicks": clicks,
                    "inline_link_clicks": int(clicks * rng.uniform(0.7, 0.95)),
                    "outbound_clicks": int(clicks * rng.uniform(0.4, 0.7)),
                    "spend": _amount(spend),
                    "cpm": _amount(spend / impressions * 1000),
                    "cpc": _amount(spend / clicks) if clicks else None,
                    "ctr": round(clicks / impressions, 5),
                    "actions": actions,
                    "action_values": [{"action_type": "purchase", "value": _amount(conv_value)}],
                    "cost_per_action_type": [{"action_type": "purchase", "value": _amount(spend / purchases) if purchases else None}],
                    "purchase_roas": round(conv_value / spend, 3) if spend else None,
                    "currency": "USD",
                    "attribution_setting": "7d_click",
                    "breakdowns": {
                        "country": [
                            {
                                "breakdown_value": "US",
                                "impressions": impressions,
                                "clicks": clicks,
                                "spend": _amount(spend),
                                "platform_conversions": purchases,
                                "platform_conversion_value": _amount(conv_value),
                            }
                        ],
                        "age": [
                            {
                                "breakdown_value": "25-34",
                                "impressions": int(impressions * 0.4),
                                "clicks": int(clicks * 0.4),
                                "spend": _amount(spend * 0.4),
                                "platform_conversions": int(purchases * 0.4),
                                "platform_conversion_value": _amount(conv_value * 0.4),
                            }
                        ],
                    },
                }
            )
    return {
        "accounts": [{"external_account_id": "act_987654321", "name": "Brand Main US", "currency": "USD", "timezone": "America/New_York"}],
        "campaigns": campaigns,
        "ad_groups": ad_groups,
        "ads": ads,
        "creatives": creatives,
        "performance": performance,
    }


def build_google(days: int, rng: random.Random, scenario: str) -> dict:
    campaigns = [
        {"external_id": "7150000001", "name": "Search - Brand", "status": "ENABLED", "channel_type": "SEARCH", "channel_sub_type": "SEARCH_STANDARD", "start_time": _dt(date.today() - timedelta(days=90)), "end_time": None},
        {"external_id": "7150000002", "name": "PMax - Prospecting", "status": "ENABLED", "channel_type": "MULTI_CHANNEL", "channel_sub_type": "PERFORMANCE_MAX", "start_time": _dt(date.today() - timedelta(days=60)), "end_time": None},
    ]
    ad_groups = [
        {"external_id": "7151111111", "campaign_external_id": "7150000001", "name": "Brand - Exact", "status": "ENABLED", "type": "SEARCH_STANDARD"},
        {"external_id": "7151111112", "campaign_external_id": "7150000001", "name": "Brand - Phrase", "status": "ENABLED", "type": "SEARCH_STANDARD"},
    ]
    ads = [
        {"external_id": "7152222221", "campaign_external_id": "7150000001", "ad_group_external_id": "7151111111", "status": "ENABLED", "name": "RSNA Brand 1"},
        {"external_id": "7152222222", "campaign_external_id": "7150000001", "ad_group_external_id": "7151111112", "status": "ENABLED", "name": "RSNA Brand 2"},
    ]
    keywords = [
        {"criterion_id": "7153333331", "ad_group_external_id": "7151111111", "keyword_text": "vitamin c serum", "match_type": "EXACT"},
        {"criterion_id": "7153333332", "ad_group_external_id": "7151111112", "keyword_text": "best vitamin c serum", "match_type": "PHRASE"},
    ]
    search_terms = [
        {"campaign_external_id": "7150000001", "ad_group_external_id": "7151111111", "search_term": "vitamin c serum for face"},
        {"campaign_external_id": "7150000001", "ad_group_external_id": "7151111112", "search_term": "best vitamin c serum 2026"},
    ]
    conversion_actions = [
        {"id": "7154444441", "name": "Purchase"},
        {"id": "7154444442", "name": "Add to cart"},
    ]
    asset_groups = [
        {"external_id": "7155555551", "campaign_external_id": "7150000002", "name": "PMax - US Prospecting", "status": "ENABLED"},
    ]

    entities = [
        ("CAMPAIGN", "7150000001"),
        ("CAMPAIGN", "7150000002"),
        ("AD_GROUP", "7151111111"),
        ("AD_GROUP", "7151111112"),
        ("AD", "7152222221"),
        ("AD", "7152222222"),
        ("ASSET_GROUP", "7155555551"),
    ]
    performance = []
    for offset in range(days):
        day = date.today() - timedelta(days=days - 1 - offset)
        for entity_type, external_id in entities:
            clicks = int(rng.uniform(40, 260))
            cost_micros = int(rng.uniform(80, 320) * 1_000_000)
            if scenario == "google_high_cpc":
                clicks = int(rng.uniform(8, 40))
                cost_micros = int(rng.uniform(500, 1200) * 1_000_000)
            conversions = int(rng.uniform(0, 3))
            conversion_value = conversions * rng.uniform(60, 80)
            performance.append(
                {
                    "date": day.isoformat(),
                    "entity_type": entity_type,
                    "external_entity_id": external_id,
                    "impressions": int(rng.uniform(2000, 9000)),
                    "clicks": clicks,
                    "cost_micros": cost_micros,
                    "conversions": conversions,
                    "conversion_value": _amount(conversion_value),
                    "currency": "USD",
                }
            )
    return {
        "accounts": [{"external_account_id": "123-456-7890", "name": "Brand Google Account", "currency": "USD", "timezone": "America/New_York"}],
        "campaigns": campaigns,
        "ad_groups": ad_groups,
        "ads": ads,
        "creatives": [],
        "keywords": keywords,
        "search_terms": search_terms,
        "conversion_actions": conversion_actions,
        "asset_groups": asset_groups,
        "performance": performance,
    }


def build_shopify(days: int, rng: random.Random, scenario: str) -> dict:
    products = [
        {"external_id": "gid://shopify/Product/810000001", "title": "Vitamin C Serum 30ml", "handle": "vitamin-c-serum-30ml", "vendor": "Glow Lab", "product_type": "Skincare", "status": "ACTIVE", "created_at": _dt(date.today() - timedelta(days=120)), "updated_at": _dt(date.today() - timedelta(days=2))},
        {"external_id": "gid://shopify/Product/810000002", "title": "Hyaluronic Moisturizer", "handle": "hyaluronic-moisturizer", "vendor": "Glow Lab", "product_type": "Skincare", "status": "ACTIVE", "created_at": _dt(date.today() - timedelta(days=100)), "updated_at": _dt(date.today() - timedelta(days=2))},
    ]
    variants = [
        {"external_id": "gid://shopify/ProductVariant/820000001", "product_external_id": "gid://shopify/Product/810000001", "sku": "VC30", "title": "Vitamin C Serum 30ml / 30ml", "price": 59.0, "compare_at_price": 79.0, "inventory_item_id": "gid://shopify/InventoryItem/830000001"},
        {"external_id": "gid://shopify/ProductVariant/820000002", "product_external_id": "gid://shopify/Product/810000002", "sku": "HM50", "title": "Hyaluronic Moisturizer / 50ml", "price": 49.0, "compare_at_price": None, "inventory_item_id": "gid://shopify/InventoryItem/830000002"},
    ]
    orders = []
    order_items = []
    refunds = []
    journeys = []
    for offset in range(days):
        day = date.today() - timedelta(days=days - 1 - offset)
        for order_no in range(2):
            order_id = f"gid://shopify/Order/{590000000 + offset * 10 + order_no}"
            item_count = rng.randint(1, 3)
            items = []
            gross = 0.0
            for i in range(item_count):
                variant = variants[i % len(variants)]
                quantity = rng.randint(1, 2)
                unit_price = variant["price"]
                line_total = round(unit_price * quantity, 2)
                gross += line_total
                items.append(
                    {
                        "line_item_id": f"gid://shopify/LineItem/{700000000 + offset * 100 + order_no * 10 + i}",
                        "product_external_id": variant["product_external_id"],
                        "variant_external_id": variant["external_id"],
                        "sku": variant["sku"],
                        "title": variant["title"],
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "line_discount": 0.0,
                        "line_total": line_total,
                    }
                )
            shipping = round(5.99 + gross * 0.02, 2)
            tax = round(gross * 0.08, 2)
            discount = round(gross * 0.1, 2)
            total = round(gross - discount + shipping + tax, 2)
            refunded = 0.0
            if scenario == "shopify_refund_spike" and offset >= days - 2 and order_no == 0:
                refunded = round(total * rng.uniform(0.5, 1.0), 2)
                refunds.append(
                    {
                        "order_external_id": order_id,
                        "refund_id": f"gid://shopify/Refund/{880000000 + offset * 10 + order_no}",
                        "created_at": _dt(day, 20),
                        "amount": refunded,
                        "reason": "customer_request",
                    }
                )
            orders.append(
                {
                    "external_id": order_id,
                    "name": f"#10{offset + 1}{order_no + 1}",
                    "created_at": _dt(day, 9 + order_no * 3),
                    "updated_at": _dt(day, 18 + order_no),
                    "financial_status": "PAID",
                    "fulfillment_status": "FULFILLED",
                    "currency": "USD",
                    "subtotal": round(gross - discount, 2),
                    "shipping": shipping,
                    "tax": tax,
                    "discount": discount,
                    "total": total,
                    "cancelled_at": None,
                    "source_name": "web",
                    "customer_id_hash": "a1b2c3d4e5f6",
                }
            )
            for item in items:
                order_items.append({"order_external_id": order_id, **item})
            journeys.append(
                {
                    "order_external_id": order_id,
                    "ready": True,
                    "days_to_conversion": 0.0 if order_no == 0 else 1.0,
                    "first": {
                        "source": "meta",
                        "landing_page": "https://shop.example.test/?utm_source=meta&utm_campaign=sale",
                        "referrer_url": "https://www.facebook.com/",
                        "utm_source": "meta",
                        "utm_medium": "paid",
                        "utm_campaign": "sale",
                        "utm_content": None,
                        "utm_term": None,
                    },
                    "last": {
                        "source": "direct",
                        "landing_page": "https://shop.example.test/collections/all",
                        "referrer_url": None,
                        "utm_source": None,
                        "utm_medium": None,
                        "utm_campaign": None,
                        "utm_content": None,
                        "utm_term": None,
                    },
                }
            )
    return {
        "accounts": [{"external_account_id": "shop.example.test", "name": "Example Store", "currency": "USD", "timezone": "America/New_York"}],
        "products": products,
        "variants": variants,
        "orders": orders,
        "order_items": order_items,
        "refunds": refunds,
        "journeys": journeys,
    }


def main() -> None:
    base = date.today()
    scenarios = {
        "meta": {
            "healthy_growth": ("healthy_growth", "zero_purchase_burn", "meta_creative_fatigue", "api_rate_limit", "schema_drift"),
        },
        "google": {
            "healthy_growth": ("healthy_growth", "google_high_cpc", "api_rate_limit", "schema_drift"),
        },
        "shopify": {
            "healthy_growth": ("healthy_growth", "shopify_refund_spike"),
        },
    }
    for provider_dir, mapping in scenarios.items():
        for _base_scenario, names in mapping.items():
            for name in names:
                rng = random.Random(f"{provider_dir}:{name}:{base.isoformat()}")
                if provider_dir == "meta":
                    data = build_meta(3, rng, name)
                elif provider_dir == "google":
                    data = build_google(3, rng, name)
                else:
                    data = build_shopify(3, rng, name)
                data["scenario"] = name
                target = FIXTURE_ROOT / provider_dir / f"{name}.json"
                target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
