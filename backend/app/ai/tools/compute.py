from statistics import median as stat_median
from typing import Any, Dict, List

from app.etl.validators import safe_divide
from app.rules.features.anomalies import mad_zscore, percent_change, zscore


async def safe_divide_tool(db, numerator, denominator) -> Dict[str, Any]:
    return {"result": float(safe_divide(numerator, denominator)) if safe_divide(numerator, denominator) is not None else None}


async def percent_change_tool(db, current, baseline) -> Dict[str, Any]:
    return {"result": percent_change(current, baseline)}


async def weighted_average(db, values: List[float], weights: List[float]) -> Dict[str, Any]:
    if not values or len(values) != len(weights):
        return {"result": None}
    total = sum(weights)
    return {"result": sum(v * w for v, w in zip(values, weights)) / total if total else None}


async def zscore_tool(db, values: List[float], current: float) -> Dict[str, Any]:
    return {"result": zscore(values, current)}


async def median_tool(db, values: List[float]) -> Dict[str, Any]:
    return {"result": stat_median(values) if values else None}


async def mad_tool(db, values: List[float], current: float) -> Dict[str, Any]:
    return {"result": mad_zscore(values, current)}


async def confidence_components_tool(db, **kwargs) -> Dict[str, Any]:
    return {"result": "see rule engine confidence scorer"}
