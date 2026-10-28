"""Traceable, null-safe Instagram derived metric calculations."""

from dataclasses import dataclass
from math import isfinite
from typing import Dict, Mapping, Optional, Sequence, Tuple, Union

from app.instagram.contracts import (
    InstagramAvailability,
    InstagramDataLayer,
    InstagramMediaType,
    InstagramMetricLevel,
)

CALCULATION_VERSION = "instagram-v1.0"
MetricInput = Mapping[str, Optional[Union[int, float]]]
AvailabilityInput = Mapping[str, Union[str, InstagramAvailability]]


@dataclass(frozen=True)
class MetricResult:
    """One derived value with the evidence needed to interpret it."""

    value: Optional[float]
    availability: InstagramAvailability
    input_metric_keys: Tuple[str, ...]
    source_layer: InstagramDataLayer = InstagramDataLayer.DERIVED
    source_metric: Optional[str] = None
    note: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        return {
            "value": self.value,
            "availability": self.availability.value,
            "input_metric_keys": list(self.input_metric_keys),
            "source_layer": self.source_layer.value,
            "source_metric": self.source_metric,
            "note": self.note,
        }


def safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Return a ratio only when both operands exist and the denominator is positive."""

    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if isfinite(value) else None


def _reason(value: object) -> InstagramAvailability:
    if isinstance(value, InstagramAvailability):
        return value
    try:
        return InstagramAvailability(str(value))
    except ValueError:
        return InstagramAvailability.UNAVAILABLE


def _raw_metric(
    metrics: MetricInput,
    availability: AvailabilityInput,
    metric_key: str,
    *,
    metric_level: InstagramMetricLevel,
    media_type: Optional[InstagramMediaType] = None,
) -> MetricResult:
    value = _number(metrics.get(metric_key))
    reason = _reason(availability.get(metric_key, InstagramAvailability.UNAVAILABLE))
    if reason is InstagramAvailability.AVAILABLE and value is None:
        reason = InstagramAvailability.UNAVAILABLE
    if reason is not InstagramAvailability.AVAILABLE:
        value = None
    return MetricResult(
        value=value,
        availability=reason,
        input_metric_keys=(metric_key,),
        source_layer=InstagramDataLayer.RAW,
    )


def _derived(
    metric_key: str,
    value: Optional[float],
    availability: InstagramAvailability,
    input_metric_keys: Sequence[str],
    *,
    source_metric: Optional[str] = None,
    note: Optional[str] = None,
) -> MetricResult:
    if availability is not InstagramAvailability.AVAILABLE:
        value = None
    return MetricResult(
        value=value,
        availability=availability,
        input_metric_keys=tuple(input_metric_keys),
        source_metric=source_metric,
        note=note,
    )


def _missing_reason(cells: Sequence[MetricResult]) -> InstagramAvailability:
    """Choose the most actionable reason when a derived value cannot be made."""

    reasons = {cell.availability for cell in cells if cell.value is None}
    for reason in (
        InstagramAvailability.PERMISSION_DENIED,
        InstagramAvailability.UNSUPPORTED,
        InstagramAvailability.EMPTY,
        InstagramAvailability.UNAVAILABLE,
    ):
        if reason in reasons:
            return reason
    return InstagramAvailability.UNAVAILABLE


def _ratio(
    metric_key: str,
    numerator: MetricResult,
    denominator: MetricResult,
    *,
    note: Optional[str] = None,
) -> MetricResult:
    inputs = numerator.input_metric_keys + denominator.input_metric_keys
    if numerator.value is None:
        return _derived(metric_key, None, numerator.availability, inputs, note=note)
    if denominator.value is None:
        return _derived(metric_key, None, denominator.availability, inputs, note=note)
    value = safe_divide(numerator.value, denominator.value)
    if value is None:
        return _derived(
            metric_key,
            None,
            InstagramAvailability.UNAVAILABLE,
            inputs,
            note=note or "denominator_must_be_positive",
        )
    return _derived(metric_key, value, InstagramAvailability.AVAILABLE, inputs, note=note)


def engagement_metrics(
    metrics: MetricInput,
    availability: AvailabilityInput,
    *,
    metric_level: InstagramMetricLevel = InstagramMetricLevel.ACCOUNT,
    media_type: Optional[InstagramMediaType] = None,
) -> Dict[str, MetricResult]:
    """Calculate engagement components without treating unavailable metrics as zero."""

    component_keys = ("likes", "comments", "shares", "saved")
    components = {
        key: _raw_metric(
            metrics,
            availability,
            key,
            metric_level=metric_level,
            media_type=media_type,
        )
        for key in component_keys
    }
    available = [cell for cell in components.values() if cell.value is not None]
    all_inputs = tuple(component_keys)
    result: Dict[str, MetricResult] = {}

    if available:
        engagement_count = sum(cell.value for cell in available if cell.value is not None)
        result["engagement_count"] = _derived(
            "engagement_count",
            engagement_count,
            InstagramAvailability.AVAILABLE,
            all_inputs,
        )
    else:
        result["engagement_count"] = _derived(
            "engagement_count",
            None,
            _missing_reason(list(components.values())),
            all_inputs,
        )

    result["engagement_component_count"] = _derived(
        "engagement_component_count",
        float(len(available)),
        InstagramAvailability.AVAILABLE,
        all_inputs,
    )
    result["engagement_completeness"] = _derived(
        "engagement_completeness",
        len(available) / len(component_keys),
        InstagramAvailability.AVAILABLE,
        all_inputs,
    )

    reach = _raw_metric(
        metrics,
        availability,
        "reach",
        metric_level=metric_level,
        media_type=media_type,
    )
    result["engagement_rate_by_reach"] = _ratio(
        "engagement_rate_by_reach",
        result["engagement_count"],
        reach,
    )
    for component_key, output_key in (
        ("likes", "like_rate_by_reach"),
        ("comments", "comment_rate_by_reach"),
        ("shares", "share_rate_by_reach"),
        ("saved", "save_rate_by_reach"),
    ):
        result[output_key] = _ratio(output_key, components[component_key], reach)

    return result


def follower_growth_metrics(
    current_metrics: MetricInput,
    current_availability: AvailabilityInput,
    previous_metrics: MetricInput,
    previous_availability: AvailabilityInput,
) -> Dict[str, MetricResult]:
    current = _raw_metric(
        current_metrics,
        current_availability,
        "follower_count",
        metric_level=InstagramMetricLevel.ACCOUNT,
    )
    previous = _raw_metric(
        previous_metrics,
        previous_availability,
        "follower_count",
        metric_level=InstagramMetricLevel.ACCOUNT,
    )
    inputs = ("follower_count", "previous_follower_count")
    if current.value is None or previous.value is None:
        reason = _missing_reason([current, previous])
        return {
            "follower_delta": _derived("follower_delta", None, reason, inputs),
            "follower_growth_rate": _derived("follower_growth_rate", None, reason, inputs),
        }

    delta = current.value - previous.value
    rate = safe_divide(delta, max(previous.value, 1.0))
    return {
        "follower_delta": _derived("follower_delta", delta, InstagramAvailability.AVAILABLE, inputs),
        "follower_growth_rate": _derived(
            "follower_growth_rate",
            rate,
            InstagramAvailability.AVAILABLE if rate is not None else InstagramAvailability.UNAVAILABLE,
            inputs,
        ),
    }


def profile_link_tap_rate(
    metrics: MetricInput,
    availability: AvailabilityInput,
) -> MetricResult:
    """Use profile_links_taps first, with website_clicks as an explicit fallback."""

    profile_views = _raw_metric(
        metrics,
        availability,
        "profile_views",
        metric_level=InstagramMetricLevel.ACCOUNT,
    )
    primary = _raw_metric(
        metrics,
        availability,
        "profile_links_taps",
        metric_level=InstagramMetricLevel.ACCOUNT,
    )
    fallback = _raw_metric(
        metrics,
        availability,
        "website_clicks",
        metric_level=InstagramMetricLevel.ACCOUNT,
    )
    selected = primary if primary.value is not None else fallback
    source_metric = "profile_links_taps" if primary.value is not None else (
        "website_clicks" if fallback.value is not None else None
    )
    result = _ratio(
        "profile_link_tap_rate",
        selected,
        profile_views,
        note="website_clicks_fallback" if source_metric == "website_clicks" else None,
    )
    return MetricResult(
        value=result.value,
        availability=result.availability,
        input_metric_keys=result.input_metric_keys,
        source_metric=source_metric,
        note=result.note,
    )


def watch_ratio(
    metrics: MetricInput,
    availability: AvailabilityInput,
    *,
    media_type: InstagramMediaType = InstagramMediaType.REELS,
) -> MetricResult:
    average_watch_time = _raw_metric(
        metrics,
        availability,
        "average_watch_time",
        metric_level=InstagramMetricLevel.MEDIA,
        media_type=media_type,
    )
    duration = _raw_metric(
        metrics,
        availability,
        "duration",
        metric_level=InstagramMetricLevel.MEDIA,
        media_type=media_type,
    )
    result = _ratio("watch_ratio", average_watch_time, duration)
    if result.value is None:
        return result
    return MetricResult(
        value=max(0.0, min(1.0, result.value)),
        availability=result.availability,
        input_metric_keys=result.input_metric_keys,
        note="clamped_to_0_1",
    )


def replay_metrics(
    metrics: MetricInput,
    availability: AvailabilityInput,
    *,
    media_type: InstagramMediaType = InstagramMediaType.REELS,
) -> Dict[str, MetricResult]:
    replays = _raw_metric(
        metrics,
        availability,
        "replays",
        metric_level=InstagramMetricLevel.MEDIA,
        media_type=media_type,
    )
    plays = _raw_metric(
        metrics,
        availability,
        "plays",
        metric_level=InstagramMetricLevel.MEDIA,
        media_type=media_type,
    )
    if replays.value is None:
        rate = _derived(
            "replay_rate",
            None,
            replays.availability,
            ("replays", "plays"),
        )
    else:
        rate = _ratio(
            "replay_rate",
            replays,
            plays,
            note="raw_replay_count_preserved_when_rate_unavailable",
        )
    return {"replays": replays, "replay_rate": rate}
