from app.rules.conflict.resolver import resolve_conflicts
from app.rules.result import RESULT_TRIGGERED, EvaluationResult


def _result(entity_id, action, reason):
    return EvaluationResult(
        rule_key=f"R_{action}",
        rule_version=1,
        entity_type="AD",
        entity_id=entity_id,
        result=RESULT_TRIGGERED,
        action=action,
        reason_group=reason,
    )


def test_tracking_suppresses_scale():
    results = [
        _result("ad1", "REVIEW_SCALE", "ROAS_ABOVE_TARGET"),
        _result("ad1", "CHECK_TRACKING", "TRACKING_ANOMALY"),
    ]
    resolved = resolve_conflicts(results)
    by_action = {r.action: r for r in resolved}
    assert by_action["REVIEW_SCALE"].result == "SUPPRESSED"
    assert "tracking issue blocks scale" in by_action["REVIEW_SCALE"].suppressed_reasons


def test_checkout_issue_downgrades_pause():
    results = [
        _result("ad2", "REVIEW_PAUSE", "NO_PURCHASE_BURN"),
        _result("ad2", "CHECK_CHECKOUT", "CHECKOUT_DROP"),
    ]
    resolved = resolve_conflicts(results)
    by_action = {r.action: r for r in resolved}
    assert by_action["REVIEW_PAUSE"].result == "CONFLICTED"
    assert by_action["CHECK_CHECKOUT"].result == "TRIGGERED"


def test_deterministic_same_order():
    group_a = [_result("ad3", "OBSERVE", "X"), _result("ad3", "REVIEW_SCALE", "Y")]
    group_b = [_result("ad3", "REVIEW_SCALE", "Y"), _result("ad3", "OBSERVE", "X")]
    assert [r.action for r in resolve_conflicts(group_a)] == [r.action for r in resolve_conflicts(group_b)]
