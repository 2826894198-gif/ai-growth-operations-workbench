from typing import Any, Dict, List, Optional, Tuple


class HealthEvaluator:
    """Pure evaluation logic for environment health (unit-testable without I/O)."""

    CRITICAL_CHECKS = ("api", "proxy", "country", "browser_launch", "cdp", "page_load")

    def evaluate(
        self,
        *,
        api_ok: bool,
        proxy_ok: bool,
        country_us: bool,
        browser_launch_ok: bool = True,
        cdp_ok: bool = True,
        page_load_ok: bool = True,
        timezone_ok: bool = True,
        language_ok: bool = True,
        latency_ms: Optional[int] = None,
    ) -> Tuple[str, str, Dict[str, Any], List[str]]:
        checks = {
            "api": {"ok": api_ok},
            "proxy": {"ok": proxy_ok},
            "country": {"ok": country_us, "expected": "US"},
            "browser_launch": {"ok": browser_launch_ok},
            "cdp": {"ok": cdp_ok},
            "page_load": {"ok": page_load_ok},
            "timezone": {"ok": timezone_ok},
            "language": {"ok": language_ok},
        }
        reasons: List[str] = []
        for name in self.CRITICAL_CHECKS:
            if not checks[name]["ok"]:
                reasons.append(f"{name}_failed")
        if not timezone_ok:
            reasons.append("timezone_mismatch")
        if not language_ok:
            reasons.append("language_mismatch")
        if latency_ms is not None and latency_ms > 1500:
            reasons.append("high_latency")

        if reasons and not any(
            checks[name]["ok"] is False for name in ("api", "proxy", "country", "browser_launch", "cdp", "page_load")
        ):
            status = "DEGRADED"
        elif reasons:
            status = "UNHEALTHY"
        elif api_ok and proxy_ok and country_us and browser_launch_ok and cdp_ok and page_load_ok:
            status = "HEALTHY"
        else:
            status = "UNKNOWN"
        return status, ";".join(reasons), checks, reasons
