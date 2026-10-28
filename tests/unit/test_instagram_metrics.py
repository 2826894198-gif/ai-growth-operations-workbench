import json
from pathlib import Path

from app.instagram.contracts import InstagramAvailability
from app.services.instagram.metrics import (
    engagement_metrics,
    follower_growth_metrics,
    profile_link_tap_rate,
    replay_metrics,
    safe_divide,
    watch_ratio,
)

FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "instagram" / "growth_intelligence_v1.json"


def fixture_payload():
    return json.loads(FIXTURE_PATH.read_text())


def test_safe_divide_rejects_missing_and_non_positive_denominator():
    assert safe_divide(10, 2) == 5
    assert safe_divide(10, 0) is None
    assert safe_divide(10, None) is None
    assert safe_divide(None, 2) is None


def test_engagement_uses_only_available_components_and_reach_denominator():
    snapshot = fixture_payload()["account_snapshots"][0]
    result = engagement_metrics(snapshot["metrics"], snapshot["metric_availability"])

    assert result["engagement_count"].value == 8300
    assert result["engagement_completeness"].value == 1
    assert result["engagement_rate_by_reach"].value == 8300 / 42000

    partial = engagement_metrics(
        {"likes": 10, "comments": None, "shares": None, "saved": None, "reach": 100},
        {
            "likes": "available",
            "comments": "unsupported",
            "shares": "unsupported",
            "saved": "unsupported",
            "reach": "available",
        },
    )
    assert partial["engagement_count"].value == 10
    assert partial["engagement_completeness"].value == 0.25


def test_profile_link_rate_records_website_click_fallback():
    snapshot = fixture_payload()["account_snapshots"][0]
    result = profile_link_tap_rate(snapshot["metrics"], snapshot["metric_availability"])

    assert result.value == 312 / 2100
    assert result.source_metric == "website_clicks"
    assert result.note == "website_clicks_fallback"


def test_follower_growth_is_delta_and_rate_against_previous_count():
    payload = fixture_payload()
    current = payload["account_snapshots"][0]
    previous = payload["account_snapshots"][1]
    result = follower_growth_metrics(
        current["metrics"],
        current["metric_availability"],
        previous["metrics"],
        previous["metric_availability"],
    )

    assert result["follower_delta"].value == 660
    assert result["follower_growth_rate"].value == 660 / 11840


def test_watch_ratio_is_clamped_and_requires_duration():
    snapshot = fixture_payload()["media_snapshots"][0]
    result = watch_ratio(snapshot["metrics"], snapshot["metric_availability"])
    assert result.value == 11.4 / 18

    clamped = watch_ratio(
        {"average_watch_time": 30, "duration": 10},
        {"average_watch_time": "available", "duration": "available"},
    )
    assert clamped.value == 1

    unavailable = watch_ratio(
        {"average_watch_time": 10, "duration": None},
        {"average_watch_time": "available", "duration": "unsupported"},
    )
    assert unavailable.value is None
    assert unavailable.availability is InstagramAvailability.UNSUPPORTED


def test_replay_rate_does_not_turn_missing_denominator_into_zero():
    fixture_snapshot = fixture_payload()["media_snapshots"][0]
    fixture_result = replay_metrics(
        fixture_snapshot["metrics"], fixture_snapshot["metric_availability"]
    )
    assert fixture_result["replays"].value is None
    assert fixture_result["replay_rate"].value is None
    assert fixture_result["replay_rate"].availability is InstagramAvailability.UNSUPPORTED

    raw_count_only = replay_metrics(
        {"replays": 10, "plays": None},
        {"replays": "available", "plays": "unsupported"},
    )
    assert raw_count_only["replays"].value == 10
    assert raw_count_only["replay_rate"].value is None
