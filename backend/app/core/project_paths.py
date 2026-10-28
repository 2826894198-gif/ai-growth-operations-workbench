"""Resolve repository assets in source checkouts and installed containers."""

import os
from pathlib import Path


def _asset_root(name: str, env_name: str) -> Path:
    override = os.environ.get(env_name)
    if override:
        return Path(override).expanduser().resolve()

    candidates = (
        Path.cwd() / name,
        Path(__file__).resolve().parents[3] / name,
        Path("/app") / name,
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"{name} directory not found; searched: {searched}")


def config_path(*parts: str) -> Path:
    return _asset_root("config", "APP_CONFIG_DIR").joinpath(*parts)


def fixture_path(*parts: str) -> Path:
    return _asset_root("fixtures", "APP_FIXTURES_DIR").joinpath(*parts)


def eval_path(*parts: str) -> Path:
    return _asset_root("evals", "APP_EVALS_DIR").joinpath(*parts)
