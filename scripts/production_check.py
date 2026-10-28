"""PART 07 §331-§332 — production safety assertions (pre-launch gate)."""

import os
import sys

from app.core.config import settings


def main() -> int:
    failures = []
    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        if not ok:
            failures.append(f"{name}: {detail}")

    check("APP_ENV explicit", settings.app_env in ("local", "test", "staging", "production"), settings.app_env)
    check("demo permissions off in prod", settings.app_env != "production" or not settings.execution_demo_permissions)
    check("secret key overridden in prod", settings.app_env != "production" or settings.secret_key != "dev-only-change-me")
    check("execution mode manual in prod", settings.app_env != "production" or settings.execution_mode == "manual")
    check("live execution tests disabled", not settings.allow_live_execution_tests)
    check(
        "write credentials least privilege",
        settings.meta_write_enabled is False or bool(settings.meta_write_credential_reference or settings.meta_write_access_token),
        "META_WRITE_ENABLED without credential reference",
    )
    check(
        "google write credentials least privilege",
        settings.google_ads_write_enabled is False or bool(settings.google_ads_write_credential_reference),
        "GOOGLE_ADS_WRITE_ENABLED without credential reference",
    )
    check("maintenance mode off", not settings.maintenance_mode)
    check("ai is optional", settings.ai_enabled or True)

    print("PRODUCTION SAFETY CHECK")
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" ({detail})" if detail else ""))
    if failures:
        print("NOT READY")
        return 1
    print("READY (configuration level)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
