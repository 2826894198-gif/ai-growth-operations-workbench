from datetime import date

from app.rules.features.windows import previous_range, rolling_range, same_weekday_dates


def test_rolling_and_previous():
    end = date(2026, 8, 10)
    assert rolling_range(end, 7) == (date(2026, 8, 4), date(2026, 8, 10))
    assert previous_range(end, 7) == (date(2026, 7, 28), date(2026, 8, 3))


def test_same_weekday_baseline():
    end = date(2026, 8, 10)  # Monday
    days = same_weekday_dates(end, weeks=3)
    assert days == [date(2026, 8, 3), date(2026, 7, 27), date(2026, 7, 20)]
    assert all(d.weekday() == end.weekday() for d in days)


def test_account_timezone_semantics():
    # Windows are date-based in the account timezone; UTC is never used to cut days.
    assert rolling_range(date(2026, 8, 10), 1)[0] == date(2026, 8, 10)
