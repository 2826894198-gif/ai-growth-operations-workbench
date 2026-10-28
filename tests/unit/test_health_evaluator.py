from app.services.health_evaluator import HealthEvaluator


def test_healthy():
    evaluator = HealthEvaluator()
    status, _, checks, reasons = evaluator.evaluate(
        api_ok=True,
        proxy_ok=True,
        country_us=True,
        timezone_ok=True,
        language_ok=True,
    )
    assert status == "HEALTHY"
    assert reasons == []
    assert checks["country"]["ok"] is True


def test_unhealthy_country_mismatch():
    status, _, _, reasons = HealthEvaluator().evaluate(
        api_ok=True,
        proxy_ok=True,
        country_us=False,
    )
    assert status == "UNHEALTHY"
    assert "country_failed" in reasons


def test_degraded_timezone_mismatch_only():
    status, _, _, reasons = HealthEvaluator().evaluate(
        api_ok=True,
        proxy_ok=True,
        country_us=True,
        timezone_ok=False,
    )
    assert status == "DEGRADED"
    assert "timezone_mismatch" in reasons


def test_degraded_high_latency():
    status, _, _, reasons = HealthEvaluator().evaluate(
        api_ok=True,
        proxy_ok=True,
        country_us=True,
        latency_ms=2500,
    )
    assert status == "DEGRADED"
    assert "high_latency" in reasons


def test_unhealthy_proxy_dead():
    status, _, _, reasons = HealthEvaluator().evaluate(
        api_ok=True,
        proxy_ok=False,
        country_us=True,
    )
    assert status == "UNHEALTHY"
    assert "proxy_failed" in reasons
