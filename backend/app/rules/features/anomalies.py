import statistics
from typing import List, Optional

from app.etl.validators import safe_divide


def zscore(values: List[float], current: Optional[float]) -> Optional[float]:
    if current is None or len(values) < 3:
        return None
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    if std == 0:
        return None
    return (current - statistics.mean(values)) / std


def mad_zscore(values: List[float], current: Optional[float]) -> Optional[float]:
    if current is None or len(values) < 3:
        return None
    median = statistics.median(values)
    deviations = [abs(v - median) for v in values]
    mad = statistics.median(deviations)
    if mad == 0:
        return None
    return 0.6745 * (current - median) / mad


def rolling_baseline(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return statistics.mean(values)


def percent_change(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
    change = safe_divide(current - baseline if current is not None and baseline is not None else None, baseline)
    return float(change * 100) if change is not None else None
