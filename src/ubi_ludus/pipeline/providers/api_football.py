"""Adapter for API-Football (api-sports.io, v3, free plan).

The free plan only answers for yesterday, today and tomorrow, but one call for a date returns the
fixtures of every league. So a run makes one call per day (three at most), keeps the leagues listed
in ``config/competitions.yml`` and leaves everything else to dbt. Before the sweep it reads the
``status`` endpoint, so the daily quota (100 requests) is never exceeded.

The API key comes from the ``API_FOOTBALL_KEY`` environment variable (a local ``.env`` file or
GitHub Secrets). It is sent only in a request header and is never logged, printed or put in an
error message.

The provider reports most problems with HTTP 200 and an ``errors`` object, for example a date the
plan cannot see. A date it refuses is skipped and listed in ``adapter.skipped``; the run only fails
when no date could be served at all.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, ClassVar
from urllib.parse import urlencode

import ubi_ludus
from ubi_ludus.pipeline.providers.base import (
    FetchRequest,
    ProviderAdapter,
    ProviderError,
    RawResponse,
)
from ubi_ludus.pipeline.providers.guard import CallBudget, QuotaExceededError
from ubi_ludus.pipeline.providers.http import HttpGet, HttpResponse, urllib_get
from ubi_ludus.pipeline.window import BRAZIL_TZ

logger = logging.getLogger(__name__)

KEY_ENV = "API_FOOTBALL_KEY"
BASE_URL = "https://v3.football.api-sports.io/"
USER_AGENT = f"ubi-ludus/{ubi_ludus.__version__} (+https://github.com/raissonls/ubi-ludus)"
DEFAULT_PAUSE_SECONDS = 60.0
RESOURCE = "fixtures"
TIMEZONE = str(BRAZIL_TZ)
"""Days are asked for in Brazil's calendar, so evening matches stay on the day people see."""

_MINUTE_LEFT = "x-ratelimit-remaining"
_DAY_LEFT = "x-ratelimit-requests-remaining"


class _KeyRejectedError(ProviderError):
    """The provider did not accept the key. Unlike a failed quota check, this ends the run."""


@dataclass(frozen=True)
class _Reply:
    http: HttpResponse
    body: dict[str, Any]
    errors: dict[str, str]


class ApiFootballAdapter(ProviderAdapter):
    name: ClassVar[str] = "api-football"

    def __init__(
        self,
        key: str | None = None,
        *,
        http_get: HttpGet = urllib_get,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        budget: CallBudget | None = None,
    ) -> None:
        resolved = (key if key is not None else os.environ.get(KEY_ENV, "")).strip()
        if not resolved:
            raise ProviderError(f"{KEY_ENV} is not set")
        self._key = resolved
        self._http_get = http_get
        self._budget = budget
        self._sleep = sleep
        self._now = now
        self._pause = 0.0
        self.skipped: list[tuple[str, str]] = []
        """Days the provider would not serve on the last run: (date, reason)."""

    def __repr__(self) -> str:
        return "ApiFootballAdapter(key=<hidden>)"

    def fetch(self, request: FetchRequest) -> list[RawResponse]:
        self.skipped = []
        leagues = {str(target.provider_id): target.competition_id for target in request.targets}
        days = self._days(request)
        if not days:
            return []
        days = self._within_quota(days)

        responses: list[RawResponse] = []
        for day in days:
            params = {"date": day.isoformat(), "timezone": TIMEZONE}
            try:
                reply = self._call(RESOURCE, params)
            except QuotaExceededError as exc:
                self._skip(day, str(exc))
                self._skip_rest(days, day, "call budget used up")
                break
            left = _number(reply.http.headers.get(_DAY_LEFT))
            if "requests" in reply.errors:
                self._skip(day, f"daily quota reached: {reply.errors['requests']}")
                self._skip_rest(days, day, "daily quota reached")
                break
            if reply.errors:
                self._skip(day, "; ".join(reply.errors.values()))
                continue
            responses.append(
                RawResponse(
                    provider=self.name,
                    resource=RESOURCE,
                    params=params,
                    fetched_at=self._now(),
                    payload=_keep_leagues(reply.body, leagues, day),
                )
            )
            if left is not None and left <= 0:
                self._skip_rest(days, day, "daily quota used up")
                break
        if not responses:
            reasons = ", ".join(f"{day} ({why})" for day, why in self.skipped)
            raise ProviderError(f"API-Football served none of the days: {reasons}")
        return responses

    def _days(self, request: FetchRequest) -> list[date]:
        """The days to ask for: those the plan allows that some competition needs.

        Today first, so a short quota drops yesterday before anything else.
        """
        allowed = [request.today + timedelta(days=offset) for offset in (0, 1, -1)]
        wanted = [
            day
            for day in allowed
            if any(t.window.date_from <= day <= t.window.date_to for t in request.targets)
        ]
        too_far = [t.competition_id for t in request.targets if t.window.date_to > max(allowed)]
        if too_far:
            logger.warning(
                "API-Football's free plan ends tomorrow; ignoring the longer horizon of %s",
                ", ".join(sorted(too_far)),
            )
        return wanted

    def _within_quota(self, days: list[date]) -> list[date]:
        """Keep only as many days as the daily quota still has room for."""
        left = self._quota_left()
        if left is None:
            return days
        if self._budget is not None:
            # Retries count too, so the budget is what the provider will still accept today.
            self._budget.allow_only(left)
        if left <= 0:
            raise ProviderError("API-Football daily quota is used up")
        if left < len(days):
            for day in days[left:]:
                self._skip(day, "not enough of the daily quota left")
        return days[:left]

    def _quota_left(self) -> int | None:
        """Requests left today, from the ``status`` endpoint. ``None`` when it cannot be read."""
        try:
            reply = self._call("status", {})
            requests = reply.body["response"]["requests"]
            return int(requests["limit_day"]) - int(requests["current"])
        except _KeyRejectedError:
            raise
        except (ProviderError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "API-Football quota unknown, going on with the response headers: %s", exc
            )
            return None

    def _skip(self, day: date, reason: str) -> None:
        logger.warning("API-Football skipped %s (%s)", day, reason)
        self.skipped.append((day.isoformat(), reason))

    def _skip_rest(self, days: list[date], after: date, reason: str) -> None:
        for day in days[days.index(after) + 1 :]:
            self._skip(day, reason)

    def _call(self, resource: str, params: Mapping[str, str]) -> _Reply:
        """One GET, spaced by the rate-limit headers, with one retry after the rate limit."""
        url = f"{BASE_URL}{resource}" + (f"?{urlencode(params)}" if params else "")
        headers = {
            "x-apisports-key": self._key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        for _attempt in range(2):
            if self._pause > 0:
                self._sleep(self._pause)
                self._pause = 0.0
            http = self._http_get(url, headers)
            self._pause = _pause_after(http)
            reply = _parse(http, resource)
            if "token" in reply.errors or http.status in (401, 403):
                raise _KeyRejectedError("API-Football rejected the API key")
            if http.status != 429 and "rateLimit" not in reply.errors:
                if http.status != 200:
                    raise ProviderError(f"API-Football answered HTTP {http.status} for {resource}")
                return reply
            self._pause = max(self._pause, DEFAULT_PAUSE_SECONDS + 1)
            logger.warning("API-Football rate limit reached, waiting %.0f s", self._pause)
        raise ProviderError("API-Football rate limit exceeded twice in a row")


def _parse(http: HttpResponse, resource: str) -> _Reply:
    if http.status == 429:  # the body of a rate-limit answer is not worth reading
        return _Reply(http, {}, {"rateLimit": "HTTP 429"})
    try:
        body = json.loads(http.body)
    except ValueError as exc:
        raise ProviderError(
            f"API-Football returned something that is not JSON for {resource}"
        ) from exc
    if not isinstance(body, dict):
        raise ProviderError(f"API-Football returned an unexpected document for {resource}")
    return _Reply(http, body, _errors(body.get("errors")))


def _errors(raw: object) -> dict[str, str]:
    """The ``errors`` member is an empty list when all is well and an object when it is not."""
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list) and raw:
        return {"error": "; ".join(str(item) for item in raw)}
    return {}


def _keep_leagues(body: dict[str, Any], leagues: Mapping[str, str], day: date) -> dict[str, Any]:
    """The same document with only the fixtures of the leagues we follow."""
    fixtures = body.get("response")
    if not isinstance(fixtures, list):
        raise ProviderError(f"API-Football sent no fixture list for {day}")
    kept = [item for item in fixtures if str(_league_id(item)) in leagues]
    return {**body, "response": kept, "results": len(kept)}


def _league_id(fixture: object) -> object:
    league = fixture.get("league") if isinstance(fixture, dict) else None
    return league.get("id") if isinstance(league, dict) else None


def _pause_after(http: HttpResponse) -> float:
    """Seconds to wait before the next call: only when the per-minute allowance is used up."""
    left = _number(http.headers.get(_MINUTE_LEFT))
    if http.status == 429 or (left is not None and left <= 0):
        return DEFAULT_PAUSE_SECONDS + 1
    return 0.0


def _number(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None
