"""Internal Instagram Growth Health score and confidence calculation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Dict, Mapping, Optional, Tuple

HEALTH_CALCULATION_VERSION = "instagram-health-v1.0"
HEALTH_DIMENSION_WEIGHTS = {
    "content_quality": 0.30,
    "growth": 0.20,
    "engagement": 0.20,
    "audience_fit": 0.10,
    "conversion_intent": 0.20,
}


@dataclass(frozen=True)
class HealthScoreResult:
    score: Optional[float]
    dimension_scores: Dict[str, float]
    effective_weights: Dict[str, float]
    missing_dimensions: Tuple[str, ...]
    data_coverage: float
    sample_factor: float
    freshness_factor: float
    confidence: float
    confidence_level: str
    status: str
    calculation_version: str = HEALTH_CALCULATION_VERSION

    def as_dict(self) -> Dict[str, object]:
        return {
            "score": self.score,
            "dimension_scores": dict(self.dimension_scores),
            "effective_weights": dict(self.effective_weights),
            "missing_dimensions": list(self.missing_dimensions),
            "data_coverage": self.data_coverage,
            "sample_factor": self.sample_factor,
            "freshness_factor": self.freshness_factor,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "status": self.status,
            "calculation_version": self.calculation_version,
        }


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def sample_factor(
    *,
    content_sample_size: int,
    account_snapshot_days: int,
    minimum_content_samples: int = 10,
    minimum_account_snapshot_days: int = 21,
) -> float:
    """Use the weaker sample source so one rich source cannot hide a cold start."""

    if minimum_content_samples <= 0 or minimum_account_snapshot_days <= 0:
        raise ValueError("minimum sample sizes must be positive")
    content_factor = _clamp(max(content_sample_size, 0) / minimum_content_samples)
    account_factor = _clamp(max(account_snapshot_days, 0) / minimum_account_snapshot_days)
    return min(content_factor, account_factor)


def freshness_factor(
    last_sync_at: Optional[datetime],
    *,
    now: datetime,
    max_age_hours: float = 24.0,
) -> float:
    if last_sync_at is None:
        return 0.0
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be positive")
    if last_sync_at.tzinfo is None:
        last_sync_at = last_sync_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - last_sync_at).total_seconds() / 3600)
    return _clamp(1.0 - age_hours / max_age_hours)


def _usable_dimension_scores(
    dimensions: Mapping[str, Optional[float]],
) -> Tuple[Dict[str, float], Tuple[str, ...]]:
    available: Dict[str, float] = {}
    missing = []
    for dimension, _weight in HEALTH_DIMENSION_WEIGHTS.items():
        value = dimensions.get(dimension)
        if value is None or isinstance(value, bool) or not isfinite(float(value)):
            missing.append(dimension)
            continue
        available[dimension] = max(0.0, min(100.0, float(value)))
    return available, tuple(missing)


def calculate_internal_growth_health(
    dimensions: Mapping[str, Optional[float]],
    *,
    content_sample_size: int,
    account_snapshot_days: int,
    last_sync_at: Optional[datetime],
    now: Optional[datetime] = None,
    minimum_content_samples: int = 10,
    minimum_account_snapshot_days: int = 21,
    max_age_hours: float = 24.0,
) -> HealthScoreResult:
    """Calculate an internal score with explicit missing-weight reallocation."""

    now = now or datetime.now(timezone.utc)
    available, missing = _usable_dimension_scores(dimensions)
    available_weight = sum(HEALTH_DIMENSION_WEIGHTS[key] for key in available)
    total_weight = sum(HEALTH_DIMENSION_WEIGHTS.values())
    effective_weights = {
        key: HEALTH_DIMENSION_WEIGHTS[key] / available_weight for key in available
    }
    weighted_score = (
        sum(available[key] * effective_weights[key] for key in available)
        if available_weight > 0
        else None
    )
    coverage = available_weight / total_weight
    samples = sample_factor(
        content_sample_size=content_sample_size,
        account_snapshot_days=account_snapshot_days,
        minimum_content_samples=minimum_content_samples,
        minimum_account_snapshot_days=minimum_account_snapshot_days,
    )
    freshness = freshness_factor(last_sync_at, now=now, max_age_hours=max_age_hours)
    confidence = coverage * samples * freshness
    cold_start = (
        content_sample_size < minimum_content_samples
        or account_snapshot_days < minimum_account_snapshot_days
    )
    if cold_start or weighted_score is None:
        score = None
        status = "CALIBRATING"
        confidence_level = "CALIBRATING"
    else:
        score = max(0.0, min(100.0, weighted_score))
        status = "AVAILABLE"
        if confidence >= 0.80:
            confidence_level = "HIGH"
        elif confidence >= 0.50:
            confidence_level = "MEDIUM"
        elif confidence > 0:
            confidence_level = "LOW"
        else:
            confidence_level = "CALIBRATING"

    return HealthScoreResult(
        score=score,
        dimension_scores=available,
        effective_weights=effective_weights,
        missing_dimensions=missing,
        data_coverage=coverage,
        sample_factor=samples,
        freshness_factor=freshness,
        confidence=confidence,
        confidence_level=confidence_level,
        status=status,
    )
