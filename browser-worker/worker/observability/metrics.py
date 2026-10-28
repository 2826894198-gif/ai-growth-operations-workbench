import threading
import time
from typing import Dict


class MetricsRegistry:
    """Tiny in-memory metrics registry with Prometheus text output."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._lock = threading.Lock()

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def render(self) -> str:
        lines: list = []
        with self._lock:
            for name, value in sorted(self._counters.items()):
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {value}")
            for name, value in sorted(self._gauges.items()):
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {value}")
        return "\n".join(lines)


metrics = MetricsRegistry()


def timed(fn_name: str):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            started = time.monotonic()
            try:
                return fn(*args, **kwargs)
            finally:
                metrics.inc(f"worker_{fn_name}_total")
                metrics.set_gauge(f"worker_{fn_name}_duration_seconds", time.monotonic() - started)

        return wrapper

    return decorator
