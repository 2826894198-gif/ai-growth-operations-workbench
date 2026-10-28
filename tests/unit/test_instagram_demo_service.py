from app.services.instagram.demo_service import (
    demo_content,
    demo_overview,
    load_demo_fixture,
)


def test_demo_overview_is_explicitly_non_live_and_calibrating():
    fixture = load_demo_fixture()
    result = demo_overview("ws_test", days=28)

    assert result["workspace_id"] == "ws_test"
    assert result["source"]["mode"] == "DEMO"
    assert result["source"]["is_live"] is False
    assert result["health"]["score"] is None
    assert result["health"]["status"] == "CALIBRATING"
    assert result["account"]["account_ref"] == fixture.accounts[0].account_ref
    assert result["derived"]["profile_link_tap_rate"]["source_metric"] == "website_clicks"


def test_demo_content_preserves_null_unsupported_metrics():
    result = demo_content("ws_test", media_type="CAROUSEL_ALBUM")

    assert result["source"]["is_live"] is False
    assert result["total"] == 1
    row = result["rows"][0]
    assert row["raw"]["metrics"]["views"] is None
    assert row["raw"]["metric_availability"]["views"] == "unsupported"
    assert row["content_score"] is None
