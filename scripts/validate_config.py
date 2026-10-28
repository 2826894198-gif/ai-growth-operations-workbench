"""PART 07 §10/§325-§332 — environment & configuration validation.

Usage:
    cd backend && .venv/bin/python ../scripts/validate_config.py
"""

import os
import sys

ALLOWED_ENVS = ("local", "test", "staging", "production")


def main() -> int:
    app_env = os.environ.get("APP_ENV", "local")
    failures = []
    if app_env not in ALLOWED_ENVS:
        failures.append(f"APP_ENV={app_env!r} not in {ALLOWED_ENVS}")
    if os.environ.get("CI", "").lower() in ("true", "1") and os.environ.get("ALLOW_LIVE_EXECUTION_TESTS", "false").lower() == "true":
        failures.append("ALLOW_LIVE_EXECUTION_TESTS=true is forbidden in CI")
    if app_env in ("staging", "production"):
        if os.environ.get("EXECUTION_DEMO_PERMISSIONS", "true").lower() == "true":
            failures.append("EXECUTION_DEMO_PERMISSIONS must be false in staging/production")
        if os.environ.get("SECRET_KEY", "dev-only-change-me") == "dev-only-change-me":
            failures.append("SECRET_KEY must be overridden in staging/production")
        if not os.environ.get("DATABASE_URL"):
            failures.append("DATABASE_URL required in staging/production")
        if app_env == "production":
            mode = os.environ.get("EXECUTION_MODE", "manual")
            if mode != "manual":
                failures.append("production requires EXECUTION_MODE=manual (Guarded Auto default OFF)")
            if os.environ.get("ALLOW_LIVE_EXECUTION_TESTS", "false").lower() == "true":
                failures.append("ALLOW_LIVE_EXECUTION_TESTS=true forbidden in production")
    if failures:
        print("CONFIG INVALID")
        for failure in failures:
            print("  -", failure)
        return 1
    print(f"CONFIG VALID (APP_ENV={app_env})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
