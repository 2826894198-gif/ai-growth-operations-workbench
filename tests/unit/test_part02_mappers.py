from decimal import Decimal

from app.etl.mappers.google_mapper import map_performance as map_google_performance
from app.etl.mappers.meta_mapper import map_performance as map_meta_performance
from app.etl.mappers.shopify_mapper import map_commerce, map_journey
from app.etl.validators import parse_date, parse_dt, safe_divide, to_decimal


def test_meta_actions_preserve_action_type():
    row = {
        "date": "2026-08-01",
        "entity_type": "CAMPAIGN",
        "external_entity_id": "c1",
        "impressions": 1000,
        "clicks": 10,
        "spend": 5.0,
        "actions": [
            {"action_type": "link_click", "value": 10},
            {"action_type": "purchase", "value": 2},
            {"action_type": "add_to_cart", "value": 4},
        ],
        "action_values": [{"action_type": "purchase", "value": 120.0}],
        "cost_per_action_type": [{"action_type": "purchase", "value": 2.5}],
        "currency": "USD",
        "attribution_setting": "7d_click",
        "breakdowns": {},
    }
    perf, _, actions, breakdowns = map_meta_performance(row, "ds1", "acc1", {("CAMPAIGN", "c1"): "dim1"}, "job1")
    types = {a["action_type"] for a in actions}
    assert types == {"link_click", "purchase", "add_to_cart"}
    assert perf["platform"] == "META_ADS"
    assert perf["date"].isoformat() == "2026-08-01"
    assert breakdowns == []


def test_google_cost_micros_conversion_preserves_raw():
    row = {
        "date": "2026-08-01",
        "entity_type": "CAMPAIGN",
        "external_entity_id": "g1",
        "impressions": 100,
        "clicks": 5,
        "cost_micros": 1500000,
        "conversions": 1,
        "conversion_value": 50.0,
        "currency": "USD",
    }
    perf, _, keywords, search_terms, conversion_actions = map_google_performance(
        row, "ds1", "acc1", {("CAMPAIGN", "g1"): "dim1"}, "job1"
    )
    assert perf["spend_amount"] == Decimal("1.5")
    assert perf["source_attribution_metadata"]["cost_micros"] == 1500000
    assert keywords == [] and search_terms == [] and conversion_actions == []


def test_null_vs_zero_preserved():
    row = {
        "date": "2026-08-01",
        "entity_type": "AD",
        "external_entity_id": "a1",
        "impressions": 0,
        "clicks": 0,
        "spend": 0,
    }
    perf, _, _, _ = map_meta_performance(row, "ds1", "acc1", {}, "job1")
    assert perf["impressions"] == 0
    assert perf["spend_amount"] == 0
    assert perf["reach"] is None


def test_safe_division_never_infinity():
    assert safe_divide(Decimal(10), Decimal(0)) is None
    assert safe_divide(None, Decimal(2)) is None
    assert safe_divide(Decimal(10), Decimal(2)) == Decimal(5)


def test_to_decimal_empty_is_none():
    assert to_decimal(None) is None
    assert to_decimal("") is None
    assert to_decimal(0) == 0


def test_parse_helpers():
    assert parse_date("2026-08-01").isoformat() == "2026-08-01"
    assert parse_dt("2026-08-01T12:00:00Z") is not None
    assert parse_dt("2026-08-01") is not None


def test_shopify_net_revenue_considers_refunds():
    orders = [
        {
            "external_id": "o1",
            "created_at": "2026-08-01T10:00:00Z",
            "updated_at": "2026-08-01T11:00:00Z",
            "currency": "USD",
            "subtotal": 100.0,
            "shipping": 5.0,
            "tax": 8.0,
            "discount": 10.0,
            "total": 103.0,
        }
    ]
    refunds = [{"order_external_id": "o1", "refund_id": "r1", "created_at": "2026-08-02T10:00:00Z", "amount": 30.0}]
    mapped = map_commerce("ds1", orders, [], refunds, {}, {}, {}, "job1")
    order = mapped["orders"][0]
    assert order["gross_amount"] == Decimal(103)
    assert order["refunded_amount"] == Decimal(30)
    assert order["net_revenue_amount"] == Decimal(73)


def test_shopify_journey_maps_first_last():
    raw = {
        "ready": True,
        "days_to_conversion": 1.0,
        "first": {"source": "meta", "utm_source": "meta", "utm_campaign": "sale"},
        "last": {"source": "direct"},
    }
    mapped = map_journey(raw)
    assert mapped["journey_ready"] is True
    assert mapped["first_source"] == "meta"
    assert mapped["first_utm_campaign"] == "sale"
    assert mapped["last_source"] == "direct"
