"""Explicit DEMO-mode read models for the Instagram V1 preview."""

import json
from pathlib import Path
from typing import Dict, Optional

from app.instagram.contracts import InstagramDemoFixture
from app.services.instagram.health import calculate_internal_growth_health
from app.services.instagram.metrics import (
    engagement_metrics,
    follower_growth_metrics,
    profile_link_tap_rate,
    replay_metrics,
    watch_ratio,
)
from app.services.instagram.rules import RuleContext, evaluate_instagram_rules

FIXTURE_PATH = Path(__file__).resolve().parents[4] / "fixtures" / "instagram" / "growth_intelligence_v1.json"


def load_demo_fixture() -> InstagramDemoFixture:
    return InstagramDemoFixture.model_validate(json.loads(FIXTURE_PATH.read_text()))


def _metric_dict(result) -> Dict[str, object]:
    return result.as_dict()


def _source(fixture: InstagramDemoFixture) -> Dict[str, object]:
    return {
        "mode": fixture.source_mode.value,
        "is_live": False,
        "fixture_version": fixture.fixture_version,
        "data_layer": "RAW",
        "label": "Demo fixture — not live Meta data",
    }


def demo_overview(workspace_id: str, days: int = 28) -> Dict[str, object]:
    fixture = load_demo_fixture()
    account = fixture.accounts[0]
    current = fixture.account_snapshots[0]
    previous = fixture.account_snapshots[1]
    engagement = engagement_metrics(current.metrics, current.metric_availability)
    growth = follower_growth_metrics(
        current.metrics,
        current.metric_availability,
        previous.metrics,
        previous.metric_availability,
    )
    link_rate = profile_link_tap_rate(current.metrics, current.metric_availability)
    health = calculate_internal_growth_health(
        {
            "content_quality": None,
            "growth": None,
            "engagement": None,
            "audience_fit": None,
            "conversion_intent": None,
        },
        content_sample_size=len(fixture.media),
        account_snapshot_days=len(fixture.account_snapshots),
        last_sync_at=account.last_sync,
    )
    return {
        "workspace_id": workspace_id,
        "requested_window_days": days,
        "available_windows": [28],
        "source": _source(fixture),
        "account": account.model_dump(mode="json"),
        "capabilities": [
            {**capability.model_dump(mode="json"), "scope_key": capability.scope_key}
            for capability in fixture.capabilities
        ],
        "raw": {
            "current_account_snapshot": current.model_dump(mode="json"),
            "previous_account_snapshot": previous.model_dump(mode="json"),
        },
        "derived": {
            **{key: _metric_dict(value) for key, value in engagement.items()},
            **{key: _metric_dict(value) for key, value in growth.items()},
            "profile_link_tap_rate": _metric_dict(link_rate),
        },
        "health": health.as_dict(),
        "caveats": [
            "Demo fixture is deterministic and is not a Meta API response.",
            "Health score remains CALIBRATING because content and account history are below V1 minimum samples.",
            "Unsupported metrics remain null with an availability reason.",
        ],
    }


def demo_content(workspace_id: str, media_type: Optional[str] = None) -> Dict[str, object]:
    fixture = load_demo_fixture()
    snapshots = {snapshot.external_media_id: snapshot for snapshot in fixture.media_snapshots}
    rows = []
    for media in fixture.media:
        if media_type and media.media_type.value != media_type.upper():
            continue
        snapshot = snapshots[media.external_media_id]
        derived = engagement_metrics(
            snapshot.metrics,
            snapshot.metric_availability,
            metric_level="MEDIA",
            media_type=media.media_type,
        )
        derived["profile_link_tap_rate"] = profile_link_tap_rate(
            snapshot.metrics,
            snapshot.metric_availability,
        )
        if media.media_type.value == "REELS":
            derived["watch_ratio"] = watch_ratio(
                snapshot.metrics,
                snapshot.metric_availability,
                media_type=media.media_type,
            )
            derived.update(replay_metrics(snapshot.metrics, snapshot.metric_availability, media_type=media.media_type))
        context = RuleContext(
            subject_ref=media.external_media_id,
            values={},
            availability={},
            confidence=0.0,
            evidence_refs=(snapshot.raw_payload_ref,),
        )
        rows.append(
            {
                "media": media.model_dump(mode="json"),
                "raw": snapshot.model_dump(mode="json"),
                "derived": {key: _metric_dict(value) for key, value in derived.items()},
                "content_score": None,
                "content_score_status": "CALIBRATING",
                "rule_evaluations": [evaluation.as_dict() for evaluation in evaluate_instagram_rules(context)],
            }
        )
    return {
        "workspace_id": workspace_id,
        "source": _source(fixture),
        "media_type": media_type.upper() if media_type else None,
        "rows": rows,
        "total": len(rows),
        "caveats": [
            "Content scores and baselines are withheld until V1 minimum samples are available.",
            "Paid, revenue, ROAS, interest and purchase attribution are intentionally absent.",
        ],
    }
