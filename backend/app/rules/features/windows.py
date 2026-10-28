from datetime import date, timedelta
from typing import List, Tuple


def rolling_range(end: date, days: int) -> Tuple[date, date]:
    return end - timedelta(days=days - 1), end


def previous_range(end: date, days: int) -> Tuple[date, date]:
    return end - timedelta(days=2 * days - 1), end - timedelta(days=days)


def same_weekday_dates(end: date, weeks: int = 4) -> List[date]:
    return [end - timedelta(weeks=week) for week in range(1, weeks + 1)]


def series_range(end: date, days: int) -> List[date]:
    start = end - timedelta(days=days - 1)
    return [start + timedelta(days=i) for i in range(days)]
