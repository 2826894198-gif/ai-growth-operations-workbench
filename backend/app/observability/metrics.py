"""Internal metrics registry (PART 07 §166-§173).

Lightweight, dependency-free counters exposed via /metrics and structured logs.
Production can export the same events through OpenTelemetry/Prometheus.
"""

import threading
from typing import Dict, Optional, Tuple

_lock = threading.Lock()
_counters: Dict[Tuple[str, str], float] = {}
_gauges: Dict[Tuple[str, str], float] = {}
_latency: Dict[Tuple[str, str], list] = {}


def increment(metric: str, labels: Optional[Dict[str, str]] = None, value: float = 1.0) -> None:
    key = (metric, _encode(labels or {}))
    with _lock:
        _counters[key] = _counters.get(key, 0.0) + value


def set_gauge(metric: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    key = (metric, _encode(labels or {}))
    with _lock:
        _gauges[key] = value


def observe_latency(metric: str, duration_ms: float, labels: Optional[Dict[str, str]] = None) -> None:
    key = (metric, _encode(labels or {}))
    with _lock:
        _latency.setdefault(key, []).append(duration_ms)
        _latency[key] = _latency[key][-200:]


def snapshot() -> Dict[str, object]:
    out: Dict[str, object] = {"counters": {}, "gauges": {}, "latency": {}}
    with _lock:
        for (metric, label_key), value in _counters.items():
            out["counters"][f"{metric}{{{label_key}}}" if label_key else metric] = value
        for (metric, label_key), value in _gauges.items():
            out["gauges"][f"{metric}{{{label_key}}}" if label_key else metric] = value
        for (metric, label_key), values in _latency.items():
            name = f"{metric}{{{label_key}}}" if label_key else metric
            out["latency"][name] = {
                "p50": _percentile(values, 0.50),
                "p95": _percentile(values, 0.95),
                "count": len(values),
            }
    return out


def _encode(labels: Dict[str, str]) -> str:
    return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))


def _percentile(values: list, percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * percentile))
    return round(ordered[index], 2)
