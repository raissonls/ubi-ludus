"""Adapter for football-data.org (API v4, free tier).

Fetches the fixtures of each competition in the request, one call per competition, and returns
each response untouched. Cleaning happens later in dbt.

The API key comes from the ``FOOTBALL_DATA_TOKEN`` environment variable (a local ``.env`` file
or GitHub Secrets). It is sent only in a request header and is never logged, printed or put in
an error message.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar
from urllib.parse import urlencode

import ubi_ludus
from ubi_ludus.pipeline.providers.base import (
    FetchRequest,
    ProviderAdapter,
    ProviderError,
    RawResponse,
)
from ubi_ludus.pipeline.providers.http import HttpGet, HttpResponse, urllib_get

logger = logging.getLogger(__name__)

TOKEN_ENV = "FOOTBALL_DATA_TOKEN"  # noqa: S105 - the name of a variable, not a secret
BASE_URL = "https://api.football-data.org/v4/"
USER_AGENT = f"ubi-ludus/{ubi_ludus.__version__} (+https://github.com/raissonls/ubi-ludus)"
DEFAULT_PAUSE_SECONDS = 60.0


class FootballDataAdapter(ProviderAdapter):
    name: ClassVar[str] = "football-data"

    def __init__(
        self,
        token: str | None = None,
        *,
        http_get: HttpGet = urllib_get,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        resolved = (token if token is not None else os.environ.get(TOKEN_ENV, "")).strip()
        if not resolved:
            raise ProviderError(f"{TOKEN_ENV} is not set")
        self._token = resolved
        self._http_get = http_get
        self._sleep = sleep
        self._now = now
        self._pause = 0.0
        self.skipped: list[tuple[str, str]] = []
        """Competitions the provider would not serve on the last run: (id, reason)."""

    def __repr__(self) -> str:
        return "FootballDataAdapter(token=<hidden>)"

    def fetch(self, request: FetchRequest) -> list[RawResponse]:
        self.skipped = []
        responses: list[RawResponse] = []
        for target in request.targets:
            resource = f"competitions/{target.provider_id}/matches"
            params = {
                "dateFrom": target.window.date_from.isoformat(),
                "dateTo": target.window.date_to.isoformat(),
            }
            reply = self._get(resource, params)
            if reply.status in (403, 404):
                reason = f"HTTP {reply.status}: not available on this plan"
                logger.warning("football-data.org skipped %s (%s)", target.competition_id, reason)
                self.skipped.append((target.competition_id, reason))
                continue
            if reply.status == 401:
                raise ProviderError("football-data.org rejected the API token (HTTP 401)")
            if reply.status != 200:
                raise ProviderError(
                    f"football-data.org answered HTTP {reply.status} for {resource}"
                )
            responses.append(
                RawResponse(
                    provider=self.name,
                    resource=resource,
                    params=params,
                    fetched_at=self._now(),
                    payload=_json(reply, resource),
                    competition_id=target.competition_id,
                )
            )
        if request.targets and not responses:
            reasons = ", ".join(f"{cid} ({why})" for cid, why in self.skipped)
            raise ProviderError(f"football-data.org served none of the competitions: {reasons}")
        return responses

    def _get(self, resource: str, params: dict[str, str]) -> HttpResponse:
        """One GET, spaced by the rate-limit headers, with one retry after an HTTP 429."""
        url = f"{BASE_URL}{resource}?{urlencode(params)}"
        headers = {
            "X-Auth-Token": self._token,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        for _attempt in range(2):
            if self._pause > 0:
                self._sleep(self._pause)
                self._pause = 0.0
            reply = self._http_get(url, headers)
            self._pause = _pause_after(reply)
            if reply.status != 429:
                return reply
            logger.warning("football-data.org rate limit reached, waiting %.0f s", self._pause)
        raise ProviderError("football-data.org rate limit exceeded twice in a row")


def _pause_after(reply: HttpResponse) -> float:
    """Seconds to wait before the next call: only when the per-minute allowance is used up."""
    available = _number(reply.headers.get("x-requests-available-minute"))
    if reply.status != 429 and (available is None or available > 0):
        return 0.0
    reset = _number(reply.headers.get("x-requestcounter-reset"))
    return (reset if reset is not None else DEFAULT_PAUSE_SECONDS) + 1


def _number(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _json(reply: HttpResponse, resource: str) -> object:
    try:
        return json.loads(reply.body)
    except ValueError as exc:
        raise ProviderError(
            f"football-data.org returned something that is not JSON for {resource}"
        ) from exc
