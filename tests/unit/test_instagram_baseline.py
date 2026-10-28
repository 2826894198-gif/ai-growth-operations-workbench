from datetime import date, timedelta

import pytest

from app.services.instagram.baseline import (
    BaselineObservation,
    BaselineStatus,
    build_account_baseline,
    build_content_baseline,
    relative_baseline_score,
    summarize_baseline,
)


def test_baseline_is_calibrating_below_minimum_sample_size():
    result = summarize_baseline(range(9), minimum_sample_size=10)

    assert result.status is BaselineStatus.CALIBRATING
    assert result.sample_size == 9
    assert result.p50 is None
    assert result.mad is None


def test_baseline_exposes_percentiles_and_mad():
    result = summarize_baseline(range(1, 11), minimum_sample_size=10)

    assert result.status is BaselineStatus.READY
    assert result.sample_size == 10
    assert result.p25 == pytest.approx(3.25)
    assert result.p50 == pytest.approx(5.5)
    assert result.p75 == pytest.approx(7.75)
    assert result.p90 == pytest.approx(9.1)
    assert result.mad == pytest.approx(2.5)


def test_content_baseline_filters_window_and_media_type_and_caps_samples():
    as_of = date(2026, 8, 1)
    observations = [
        BaselineObservation(
            reference=f"reel-{index}",
            observed_at=as_of - timedelta(days=index),
            value=float(index),
            media_type="REELS",
        )
        for index in range(1, 14)
    ]
    observations.extend(
        [
            BaselineObservation("old-reel", as_of - timedelta(days=91), 100, "REELS"),
            BaselineObservation("carousel-1", as_of - timedelta(days=1), 100, "CAROUSEL_ALBUM"),
        ]
    )

    result = build_content_baseline(
        observations,
        media_type="REELS",
        as_of=as_of,
        max_samples=10,
        minimum_sample_size=10,
    )

    assert result.status is BaselineStatus.READY
    assert result.sample_size == 10
    assert "old-reel" not in result.observation_refs
    assert "carousel-1" not in result.observation_refs


def test_account_baseline_counts_distinct_snapshot_days():
    as_of = date(2026, 8, 1)
    observations = [
        BaselineObservation(
            reference=f"account-{index}",
            observed_at=as_of - timedelta(days=index),
            value=100 + index,
        )
        for index in range(1, 22)
    ]
    observations.append(BaselineObservation("duplicate-day", as_of - timedelta(days=1), 999))

    result = build_account_baseline(observations, as_of=as_of, minimum_sample_size=21)

    assert result.status is BaselineStatus.READY
    assert result.sample_size == 21
    assert "duplicate-day" not in result.observation_refs


def test_relative_baseline_score_matches_spec_and_supports_negative_direction():
    assert relative_baseline_score(100, 100) == pytest.approx(70)
    assert relative_baseline_score(200, 100) == pytest.approx(90)
    assert relative_baseline_score(50, 100) == pytest.approx(50)
    assert relative_baseline_score(50, 100, direction="DOWN") == pytest.approx(90)
    assert relative_baseline_score(None, 100) is None
