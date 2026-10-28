from app.rules.confidence.scorer import confidence_band, score_confidence


def test_confidence_bands():
    assert confidence_band(0.3) == "LOW"
    assert confidence_band(0.5) == "MEDIUM"
    assert confidence_band(0.75) == "HIGH"
    assert confidence_band(0.9) == "VERY_HIGH"


def test_weights_and_penalties():
    weights = {"data_freshness": 0.2, "sample_reliability": 0.25, "rule_strength": 0.25, "signal_agreement": 0.2, "cross_source": 0.1}
    score, components = score_confidence(
        freshness_minutes=5,
        sample_reliability=100.0,
        evidence=[{"metric": "spend", "current": 10}],
        rule_strength_thresholds={},
        context={},
        weights=weights,
    )
    assert score > 0.7
    assert set(components) == set(weights)


def test_penalties_reduce_score():
    weights = {"data_freshness": 0.2, "sample_reliability": 0.25, "rule_strength": 0.25, "signal_agreement": 0.2, "cross_source": 0.1}
    score_no, _ = score_confidence(freshness_minutes=5, sample_reliability=100.0, evidence=[], rule_strength_thresholds={}, context={}, weights=weights)
    score_pen, _ = score_confidence(freshness_minutes=5, sample_reliability=100.0, evidence=[], rule_strength_thresholds={}, context={}, weights=weights, penalties=[0.3])
    assert score_pen < score_no
