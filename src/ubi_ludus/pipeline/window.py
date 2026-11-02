"""Which days to ask a provider for, counted in Brazil's calendar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class DateWindow:
    """Both ends are included."""

    date_from: date
    date_to: date


def today_in_brazil(now: datetime) -> date:
    """The calendar date in São Paulo at ``now``. Always use the IANA zone, never a fixed offset."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(BRAZIL_TZ).date()


def window_for(today: date, horizon_days: int) -> DateWindow:
    """Yesterday through ``horizon_days`` ahead (PRD FR-04).

    A horizon of 14 gives the full window. A horizon of 1 gives yesterday through
    tomorrow, which is all the API-Football free plan allows.
    """
    if horizon_days < 1:
        raise ValueError("horizon_days must be at least 1")
    return DateWindow(today - timedelta(days=1), today + timedelta(days=horizon_days))
