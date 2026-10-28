"""Canonical provider state helpers: hashing and safe serialization."""

import hashlib
import json
from decimal import Decimal
from typing import Any, Dict, Optional


def _canonicalize(value: Any) -> Any:
    """Recursively convert values to stable JSON-safe primitives."""
    if isinstance(value, Decimal):
        return {"__decimal__": str(value)}
    if isinstance(value, dict):
        return {str(k): _canonicalize(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(_canonicalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def state_hash(state: Optional[Dict[str, Any]]) -> str:
    """Deterministic SHA-256 over the canonical state representation."""
    return hashlib.sha256(canonical_json(state or {}).encode("utf-8")).hexdigest()


def decimal_from_state(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, dict) and "__decimal__" in value:
        return Decimal(value["__decimal__"])
    return Decimal(str(value))


def money_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict) and "__decimal__" in value:
        return value["__decimal__"]
    return str(value)
