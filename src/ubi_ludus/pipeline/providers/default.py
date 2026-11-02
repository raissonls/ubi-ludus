"""The adapters that ship with the project, each behind the guard of ``guard.py``."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from ubi_ludus.pipeline.providers.api_football import ApiFootballAdapter
from ubi_ludus.pipeline.providers.base import ProviderAdapter
from ubi_ludus.pipeline.providers.cache import DEFAULT_TTL_SECONDS, ResponseCache
from ubi_ludus.pipeline.providers.football_data import FootballDataAdapter
from ubi_ludus.pipeline.providers.guard import CallBudget, CallLog, GuardedHttp, RateLimiter
from ubi_ludus.pipeline.providers.http import HttpGet, urllib_get
from ubi_ludus.pipeline.providers.registry import AdapterRegistry


@dataclass(frozen=True)
class ProviderLimits:
    calls_per_minute: int
    """The provider's documented rate limit (docs/research/provider-comparison.md)."""
    calls_per_run: int | None
    """A fuse on real calls in one run. A run needs far fewer; this stops a runaway loop."""


# football-data.org: 10 calls a minute, about 13 competitions a run. API-Football: 10 a minute
# and 100 a day; a run is a status call plus three days, and its real daily quota is read from
# the provider at the start of each run and replaces this fuse.
LIMITS = {
    "football-data": ProviderLimits(calls_per_minute=10, calls_per_run=40),
    "api-football": ProviderLimits(calls_per_minute=10, calls_per_run=10),
}


def default_registry(
    *,
    cache_dir: Path | None = None,
    cache_ttl_seconds: float = DEFAULT_TTL_SECONDS,
    call_log: CallLog | None = None,
    http: HttpGet = urllib_get,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> AdapterRegistry:
    """A registry with every adapter written so far.

    ``cache_dir`` turns the response cache on (it is off by default, so nothing is written to
    disk unless asked). ``call_log`` collects the calls of the run; pass the same one to
    ``fetch_all`` to have the run's total logged. ``http``, ``sleep`` and ``clock`` are for tests.
    """
    cache = ResponseCache(cache_dir, cache_ttl_seconds) if cache_dir else None
    if cache is not None:
        cache.prune()
    log = call_log if call_log is not None else CallLog()

    def guarded(
        provider: str, never_cache: Callable[[str], bool] = lambda _url: False
    ) -> tuple[GuardedHttp, CallBudget]:
        limits = LIMITS[provider]
        budget = CallBudget(provider, limits.calls_per_run)
        guard = GuardedHttp(
            provider,
            http,
            cache=cache,
            limiter=RateLimiter(limits.calls_per_minute, 60.0, clock=clock, sleep=sleep),
            budget=budget,
            call_log=log,
            never_cache=never_cache,
        )
        return guard, budget

    def football_data() -> ProviderAdapter:
        guard, _budget = guarded(FootballDataAdapter.name)
        return FootballDataAdapter(http_get=guard, sleep=sleep)

    def api_football() -> ProviderAdapter:
        # The status endpoint reports today's quota, so it is never replayed from the cache.
        guard, budget = guarded(
            ApiFootballAdapter.name, lambda url: urlsplit(url).path.endswith("/status")
        )
        return ApiFootballAdapter(http_get=guard, sleep=sleep, budget=budget)

    registry = AdapterRegistry()
    registry.register(ApiFootballAdapter.name, api_football)
    registry.register(FootballDataAdapter.name, football_data)
    return registry
