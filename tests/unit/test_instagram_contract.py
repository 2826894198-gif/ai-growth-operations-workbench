import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from app.instagram.contracts import (
    InstagramAccountSnapshotContract,
    InstagramAvailability,
    InstagramDataLayer,
    InstagramDemoFixture,
    InstagramDerivedMetricContract,
    InstagramMetricCell,
    InstagramMetricLevel,
)
from app.models import Base
from pydantic import ValidationError

FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "instagram" / "growth_intelligence_v1.json"


def load_fixture() -> InstagramDemoFixture:
    return InstagramDemoFixture.model_validate(json.loads(FIXTURE_PATH.read_text()))


def test_demo_fixture_is_deterministic_and_explicitly_demo():
    fixture = load_fixture()

    assert fixture.source_mode.value == "DEMO"
    assert fixture.generated_at == datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert len(fixture.accounts) == 1
    assert [snapshot.observed_at for snapshot in fixture.account_snapshots] == [
        datetime(2026, 8, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 4, tzinfo=timezone.utc),
    ]


def test_unavailable_metric_is_null_and_available_zero_is_valid():
    unavailable = InstagramMetricCell(
        metric_key="profile_links_taps",
        metric_level=InstagramMetricLevel.ACCOUNT,
        value=None,
        availability=InstagramAvailability.UNSUPPORTED,
        source_layer=InstagramDataLayer.RAW,
    )
    assert unavailable.value is None

    observed_zero = InstagramMetricCell(
        metric_key="shares",
        metric_level=InstagramMetricLevel.MEDIA,
        media_type="REELS",
        value=0,
        availability=InstagramAvailability.AVAILABLE,
        source_layer=InstagramDataLayer.RAW,
    )
    assert observed_zero.value == 0

    with pytest.raises(ValidationError, match="must keep value null"):
        InstagramMetricCell(
            metric_key="profile_links_taps",
            metric_level=InstagramMetricLevel.ACCOUNT,
            value=0,
            availability=InstagramAvailability.UNSUPPORTED,
            source_layer=InstagramDataLayer.RAW,
        )


def test_raw_snapshot_requires_exact_metric_availability_map():
    with pytest.raises(ValidationError, match="missing_availability"):
        InstagramAccountSnapshotContract(
            account_ref="ig_demo_account_001",
            observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            window_start=date(2026, 7, 5),
            window_end=date(2026, 8, 1),
            source_mode="DEMO",
            api_version="v26.0",
            raw_payload_ref="fixture:raw:account:1",
            metrics={"reach": 1},
            metric_availability={},
        )


def test_raw_and_derived_layers_cannot_be_swapped():
    with pytest.raises(ValidationError, match="RAW layer"):
        InstagramAccountSnapshotContract(
            account_ref="ig_demo_account_001",
            observed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            window_start=date(2026, 7, 5),
            window_end=date(2026, 8, 1),
            source_mode="DEMO",
            api_version="v26.0",
            raw_payload_ref="fixture:raw:account:1",
            metrics={"reach": 1},
            metric_availability={"reach": "available"},
            source_layer="DERIVED",
        )

    derived = InstagramDerivedMetricContract(
        subject_type="ACCOUNT",
        subject_ref="ig_demo_account_001",
        window_start=date(2026, 7, 5),
        window_end=date(2026, 8, 1),
        metrics={"engagement_rate_by_reach": 0.12},
        metric_availability={"engagement_rate_by_reach": "available"},
        input_metric_keys=["likes", "comments", "shares", "saved", "reach"],
        input_snapshot_refs=["fixture:instagram:account:2026-08-01"],
        calculation_version="instagram-v1.0",
        source_mode="DEMO",
    )
    assert derived.source_layer is InstagramDataLayer.DERIVED


def test_fixture_never_claims_paid_or_commerce_attribution():
    raw = FIXTURE_PATH.read_text().lower()

    assert "revenue" not in raw
    assert "roas" not in raw
    assert "shopify" not in raw
    assert "purchase" not in raw


def test_instagram_tables_are_registered_with_alembic_metadata():
    expected = {
        "instagram_capabilities",
        "instagram_account_snapshots",
        "instagram_media_snapshots",
        "instagram_derived_metric_snapshots",
        "instagram_health_score_snapshots",
        "instagram_rule_events",
        "instagram_sync_runs",
        "instagram_oauth_credentials",
    }

    assert expected.issubset(Base.metadata.tables)
    assert Base.metadata.tables["instagram_account_snapshots"].c.source_layer.nullable is False
    assert Base.metadata.tables["instagram_account_snapshots"].c.raw_payload_id.nullable is False
    assert Base.metadata.tables["instagram_account_snapshots"].c.metric_availability.nullable is False
    assert Base.metadata.tables["instagram_derived_metric_snapshots"].c.source_mode.nullable is False
    assert Base.metadata.tables["instagram_derived_metric_snapshots"].c.input_snapshot_refs.nullable is False
    assert Base.metadata.tables["instagram_derived_metric_snapshots"].c.calculation_version.nullable is False
    assert Base.metadata.tables["instagram_health_score_snapshots"].c.score.nullable is True
    assert Base.metadata.tables["instagram_rule_events"].c.evidence.nullable is False
