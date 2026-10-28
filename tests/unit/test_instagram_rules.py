from app.instagram.contracts import InstagramAvailability
from app.services.instagram.rules import (
    RULE_VERSION,
    InstagramRuleCode,
    RuleContext,
    evaluate_instagram_rules,
)


def available_context(values, *, confidence=0.8):
    return RuleContext(
        subject_ref="ig_media_reel_001",
        values=values,
        availability={key: InstagramAvailability.AVAILABLE for key in values},
        confidence=confidence,
        evidence_refs=("raw:media:001", "derived:media:001"),
    )


def test_all_v1_rules_have_stable_order_and_versioned_evidence():
    evaluations = evaluate_instagram_rules(
        available_context(
            {
                "content_score": 88,
                "reach_to_baseline_ratio": 2.4,
                "engagement_to_baseline_ratio": 1.8,
                "audience_fit_delta": -20,
                "profile_views": 1000,
                "profile_link_tap_rate": 0.01,
                "reach_score": 85,
                "intent_score": 30,
                "content_to_baseline_ratio": 0.4,
            }
        )
    )

    assert len(evaluations) == 8
    assert [evaluation.rule_code for evaluation in evaluations] == list(InstagramRuleCode)
    assert all(evaluation.rule_version == RULE_VERSION for evaluation in evaluations)
    assert all(evaluation.evidence["input_refs"] for evaluation in evaluations)
    assert all(evaluation.status == "TRIGGERED" for evaluation in evaluations[:5])
    assert evaluations[5].status == "TRIGGERED"
    assert evaluations[6].status == "NOT_TRIGGERED"
    assert evaluations[7].status == "NOT_TRIGGERED"

    decay = evaluate_instagram_rules(
        available_context({"content_score": 20, "content_to_baseline_ratio": 0.4})
    )[-1]
    assert decay.status == "TRIGGERED"


def test_unavailable_metric_is_insufficient_not_zero_trigger():
    context = RuleContext(
        subject_ref="ig_media_carousel_001",
        values={"content_score": 0},
        availability={"content_score": InstagramAvailability.UNSUPPORTED},
        confidence=0.9,
    )

    winning = evaluate_instagram_rules(context)[0]
    assert winning.triggered is False
    assert winning.status == "INSUFFICIENT_DATA"
    assert winning.missing_fields == ("content_score",)


def test_low_confidence_suppresses_assertion_but_preserves_observed_values():
    context = available_context({"content_score": 90}, confidence=0.2)
    winning = evaluate_instagram_rules(context)[0]

    assert winning.triggered is False
    assert winning.status == "INSUFFICIENT_DATA"
    assert winning.confidence == 0.2
    assert winning.evidence["observations"]["content_score"] == 90
