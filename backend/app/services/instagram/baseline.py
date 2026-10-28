"""Self-history baselines for Instagram V1."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from math import isfinite, log2
from statistics import median
from typing import Iterable, List, Optional, Sequence, Tuple, Union


class BaselineStatus(str, Enum):
    READY = "READY"
    CALIBRATING = "CALIBRATING"


ObservedAt = Union[date, datetime]


@dataclass(frozen=True)
class BaselineObservation:
    reference: str
    observed_at: ObservedAt
    value: Optional[float]
    media_type: Optional[str] = None


@dataclass(frozen=True)
class BaselineResult:
    status: BaselineStatus
    sample_size: int
    minimum_sample_size: int
    p25: Optional[float]
    p50: Optional[float]
    p75: Optional[float]
    p90: Optional[float]
    mad: Optional[float]
    observation_refs: Tuple[str, ...]

    @property
    def median(self) -> Optional[float]:
        return self.p50


def _as_date(value: ObservedAt) -> date:
    return value.date() if isinstance(value, datetime) else value


def _percentile(values: Sequence[float], quantile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_baseline(
    values: Iterable[Optional[float]],
    *,
    minimum_sample_size: int,
    observation_refs: Sequence[str] = (),
) -> BaselineResult:
    raw_values = list(values)
    finite: List[float] = []
    finite_refs: List[str] = []
    for index, value in enumerate(raw_values):
        if value is None or isinstance(value, bool):
            continue
        numeric = float(value)
        if isfinite(numeric):
            finite.append(numeric)
            if index < len(observation_refs):
                finite_refs.append(observation_refs[index])
    refs = tuple(finite_refs)
    if len(finite) < minimum_sample_size:
        return BaselineResult(
            status=BaselineStatus.CALIBRATING,
            sample_size=len(finite),
            minimum_sample_size=minimum_sample_size,
            p25=None,
            p50=None,
            p75=None,
            p90=None,
            mad=None,
            observation_refs=refs,
        )

    p50 = median(finite)
    deviations = [abs(value - p50) for value in finite]
    return BaselineResult(
        status=BaselineStatus.READY,
        sample_size=len(finite),
        minimum_sample_size=minimum_sample_size,
        p25=_percentile(finite, 0.25),
        p50=p50,
        p75=_percentile(finite, 0.75),
        p90=_percentile(finite, 0.90),
        mad=median(deviations),
        observation_refs=refs,
    )


def build_content_baseline(
    observations: Sequence[BaselineObservation],
    *,
    media_type: str,
    as_of: date,
    lookback_days: int = 90,
    max_samples: int = 60,
    minimum_sample_size: int = 10,
) -> BaselineResult:
    cutoff = as_of - timedelta(days=lookback_days)
    eligible = [
        observation
        for observation in observations
        if observation.media_type == media_type
        and cutoff <= _as_date(observation.observed_at) <= as_of
        and observation.value is not None
    ]
    eligible.sort(key=lambda observation: observation.observed_at, reverse=True)
    selected = eligible[:max_samples]
    return summarize_baseline(
        [observation.value for observation in selected],
        minimum_sample_size=minimum_sample_size,
        observation_refs=[observation.reference for observation in selected],
    )


def build_account_baseline(
    observations: Sequence[BaselineObservation],
    *,
    as_of: date,
    lookback_days: int = 90,
    minimum_sample_size: int = 21,
) -> BaselineResult:
    cutoff = as_of - timedelta(days=lookback_days)
    eligible = [
        observation
        for observation in observations
        if cutoff <= _as_date(observation.observed_at) <= as_of and observation.value is not None
    ]
    eligible.sort(key=lambda observation: observation.observed_at, reverse=True)

    # Account baselines count snapshot days, not duplicate snapshots from one day.
    unique_days = {}
    for observation in eligible:
        unique_days.setdefault(_as_date(observation.observed_at), observation)
    selected = [unique_days[day] for day in sorted(unique_days, reverse=True)]
    return summarize_baseline(
        [observation.value for observation in selected],
        minimum_sample_size=minimum_sample_size,
        observation_refs=[observation.reference for observation in selected],
    )


def relative_baseline_score(
    current: Optional[float],
    baseline: Optional[float],
    *,
    direction: str = "UP",
    epsilon: float = 1e-9,
) -> Optional[float]:
    """Map a current value against its baseline to the spec's 0–100 score."""

    if current is None or baseline is None:
        return None
    if not isfinite(float(current)) or not isfinite(float(baseline)):
        return None
    if current < 0 or baseline < 0 or epsilon <= 0:
        return None
    if direction not in {"UP", "DOWN"}:
        raise ValueError("direction must be UP or DOWN")

    ratio = (current + epsilon) / (baseline + epsilon)
    if direction == "DOWN":
        ratio = 1 / ratio
    score = 70 + 20 * log2(ratio)
    return max(0.0, min(100.0, score))
