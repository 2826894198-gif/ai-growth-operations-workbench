from datetime import datetime, timedelta, timezone

import pytest

from app.services.instagram.health import (
    HEALTH_DIMENSION_WEIGHTS,
    calculate_internal_growth_health,
    freshness_factor,
    sample_factor,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_missing_dimensions_reallocate_weight_instead_of_zero_filling():
    result = calculate_internal_growth_health(
        {
            "content_quality": 80,
            "growth": 60,
            "engagement": None,
            "audience_fit": None,
            "conversion_intent": 70,
        },
        content_sample_size=20,
        account_snapshot_days=30,
        last_sync_at=NOW,
        now=NOW,
    )

    expected = (80 * 0.30 + 60 * 0.20 + 70 * 0.20) / (0.30 + 0.20 + 0.20)
    assert result.score == pytest.approx(expected)
    assert result.missing_dimensions == ("engagement", "audience_fit")
    assert sum(result.effective_weights.values()) == pytest.approx(1)
    assert result.data_coverage == pytest.approx(0.70)


def test_cold_start_does_not_emit_pseudo_precise_health_score():
    result = calculate_internal_growth_health(
        {dimension: 80 for dimension in HEALTH_DIMENSION_WEIGHTS},
        content_sample_size=9,
        account_snapshot_days=21,
        last_sync_at=NOW,
        now=NOW,
    )

    assert result.score is None
    assert result.status == "CALIBRATING"
    assert result.confidence_level == "CALIBRATING"


def test_confidence_is_coverage_times_sample_times_freshness():
    result = calculate_internal_growth_health(
        {"content_quality": 80, "growth": 70},
        content_sample_size=20,
        account_snapshot_days=21,
        last_sync_at=NOW - timedelta(hours=6),
        now=NOW,
    )

    expected = 0.50 * 1.0 * 0.75
    assert result.confidence == pytest.approx(expected)
    assert result.confidence_level == "LOW"


def test_sample_and_freshness_factors_are_bounded():
    assert sample_factor(
        content_sample_size=100,
        account_snapshot_days=100,
    ) == 1
    assert sample_factor(
        content_sample_size=0,
        account_snapshot_days=100,
    ) == 0
    assert freshness_factor(None, now=NOW) == 0
    assert freshness_factor(NOW - timedelta(hours=48), now=NOW) == 0
    assert freshness_factor(NOW - timedelta(hours=12), now=NOW) == pytest.approx(0.5)
