import threading
from typing import Dict


class AIMetricsRegistry:
    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._lock = threading.Lock()

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counters)


ai_metrics = AIMetricsRegistry()
