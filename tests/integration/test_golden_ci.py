"""CI contract: run the golden scenario suites as processes (review P0)."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "scripts")


def _run_script(script: str, db_name: str) -> int:
    db_path = f"sqlite+aiosqlite:////tmp/{db_name}.db"
    if os.path.exists(f"/tmp/{db_name}.db"):
        os.remove(f"/tmp/{db_name}.db")
    env = {
        **os.environ,
        "DATABASE_URL": db_path,
        "DATA_PROVIDER_MODE": "mock",
        "SOCIAL_PROVIDER_MODE": "mock",
        "EXECUTION_ENABLED": "true",
        "EXECUTION_MODE": "manual",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.call([sys.executable, os.path.join(SCRIPTS, script)], env=env, cwd=ROOT)


def test_golden_social_ci():
    assert _run_script("smoke_social.py", "ci_social") == 0


def test_golden_execution_ci():
    assert _run_script("smoke_execution.py", "ci_execution") == 0
