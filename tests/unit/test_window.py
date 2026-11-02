from datetime import UTC, date, datetime

import pytest

from ubi_ludus.pipeline.window import DateWindow, today_in_brazil, window_for


def test_full_window_is_yesterday_through_fourteen_days_ahead() -> None:
    assert window_for(date(2026, 11, 2), 14) == DateWindow(date(2026, 11, 1), date(2026, 11, 16))


def test_short_window_is_yesterday_through_tomorrow() -> None:
    assert window_for(date(2026, 11, 2), 1) == DateWindow(date(2026, 11, 1), date(2026, 11, 3))


def test_window_crosses_month_and_year_ends() -> None:
    assert window_for(date(2026, 12, 31), 1) == DateWindow(date(2026, 12, 30), date(2027, 1, 1))


def test_window_needs_at_least_one_day_ahead() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        window_for(date(2026, 11, 2), 0)


def test_the_pipeline_run_time_is_the_same_day_in_brazil() -> None:
    """The daily run starts at 09:00 UTC, which is 06:00 in São Paulo."""
    assert today_in_brazil(datetime(2026, 11, 2, 9, 0, tzinfo=UTC)) == date(2026, 11, 2)


def test_just_after_midnight_utc_it_is_still_yesterday_in_brazil() -> None:
    assert today_in_brazil(datetime(2026, 11, 3, 2, 30, tzinfo=UTC)) == date(2026, 11, 2)


def test_three_hours_later_it_is_the_next_day_in_brazil() -> None:
    assert today_in_brazil(datetime(2026, 11, 3, 3, 0, tzinfo=UTC)) == date(2026, 11, 3)


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        today_in_brazil(datetime(2026, 11, 2, 9, 0))  # noqa: DTZ001 - the naive value is the point
