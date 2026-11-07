"""Keeps every provider call inside the provider's limits, and counts them (PRD FR-03).

:class:`GuardedHttp` wraps an ``HttpGet`` function (see ``http.py``) and is what the adapters
call instead of the network. For each request it:

1. answers from the :class:`~ubi_ludus.pipeline.providers.cache.ResponseCache` when it can, which
   costs nothing;
2. otherwise checks the :class:`CallBudget`: a limit on real calls for this run, so the pipeline
   stops calling before a quota would be exceeded;
3. waits, if needed, for the :class:`RateLimiter`: never more than N calls in any 60 seconds;
4. makes the call, logs it and counts it in the :class:`CallLog`.

Adapters keep their own handling of the provider's answers (rate-limit headers, plan errors).
This layer is the floor under them: it does not depend on the provider telling the truth.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from ubi_ludus.logs import event
from ubi_ludus.pipeline.providers.base import ProviderError
from ubi_ludus.pipeline.providers.cache import ResponseCache
from ubi_ludus.pipeline.providers.http import HttpGet, HttpResponse, urllib_get

logger = logging.getLogger(__name__)


class QuotaExceededError(ProviderError):
    """The next call would go over the number of calls this run may make to a provider."""


class RateLimiter:
    """At most ``max_calls`` calls in any ``per_seconds`` seconds, by waiting.

    A sliding window is stricter than the fixed minute that providers count, so staying inside
    it keeps us inside theirs.
    """

    def __init__(
        self,
        max_calls: int,
        per_seconds: float = 60.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be at least 1")
        self._max_calls = max_calls
        self._per_seconds = per_seconds
        self._clock = clock
        self._sleep = sleep
        self._calls: deque[float] = deque()

    def wait(self) -> float:
        """Block until a call is allowed, then record it. Returns the seconds waited."""
        waited = 0.0
        self._forget_old()
        if len(self._calls) >= self._max_calls:
            waited = self._calls[0] + self._per_seconds - self._clock()
            logger.info("Rate limit: waiting %.1f s before the next call", waited)
            self._sleep(waited)
            self._forget_old()
        self._calls.append(self._clock())
        return waited

    def _forget_old(self) -> None:
        now = self._clock()
        while self._calls and now - self._calls[0] >= self._per_seconds:
            self._calls.popleft()


class CallBudget:
    """How many real calls this run may still make to one provider. ``None`` means no limit."""

    def __init__(self, provider: str, limit: int | None = None) -> None:
        self._provider = provider
        self._limit = limit
        self.used = 0

    def spend(self) -> None:
        """Count one call, or raise before it is made if the budget is used up."""
        if self._limit is not None and self.used >= self._limit:
            raise QuotaExceededError(
                f"{self._provider} call budget of {self._limit} used up for this run"
            )
        self.used += 1

    def allow_only(self, more_calls: int) -> None:
        """From now on, allow at most ``more_calls`` further calls (for example the quota left)."""
        self._limit = self.used + max(more_calls, 0)


@dataclass
class CallStats:
    network: int = 0
    cached: int = 0

    @property
    def total(self) -> int:
        return self.network + self.cached


@dataclass
class CallLog:
    """Every call of one run, by provider. :meth:`log_summary` is the run's total (FR-03)."""

    by_provider: dict[str, CallStats] = field(default_factory=dict)

    def stats(self, provider: str) -> CallStats:
        return self.by_provider.setdefault(provider, CallStats())

    @property
    def network_calls(self) -> int:
        return sum(s.network for s in self.by_provider.values())

    def log_summary(self) -> None:
        parts = [
            f"{provider} {stats.total} "
            f"({stats.network} over the network, {stats.cached} from cache)"
            for provider, stats in sorted(self.by_provider.items())
        ]
        event(
            logger,
            f"Provider calls this run: {'; '.join(parts) or 'none'}. "
            f"Total over the network: {self.network_calls}",
            "provider_calls",
            providers={
                provider: {"total": stats.total, "network": stats.network, "cached": stats.cached}
                for provider, stats in sorted(self.by_provider.items())
            },
            network_total=self.network_calls,
        )


class GuardedHttp:
    """An ``HttpGet`` that caches, limits, counts and logs. Build one per provider and run."""

    def __init__(
        self,
        provider: str,
        inner: HttpGet = urllib_get,
        *,
        cache: ResponseCache | None = None,
        limiter: RateLimiter | None = None,
        budget: CallBudget | None = None,
        call_log: CallLog | None = None,
        never_cache: Callable[[str], bool] = lambda _url: False,
    ) -> None:
        self.provider = provider
        self._inner = inner
        self._cache = cache
        self._limiter = limiter
        self._budget = budget
        self._never_cache = never_cache
        self._stats = (call_log or CallLog()).stats(provider)

    def __call__(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        cache = None if self._never_cache(url) else self._cache
        if cache is not None:
            hit = cache.get(self.provider, url)
            if hit is not None:
                self._stats.cached += 1
                logger.info("%s GET %s: from cache", self.provider, _describe(url))
                return hit
        if self._budget is not None:
            self._budget.spend()
        if self._limiter is not None:
            self._limiter.wait()
        self._stats.network += 1
        reply = self._inner(url, headers)
        logger.info("%s GET %s: HTTP %d", self.provider, _describe(url), reply.status)
        if cache is not None:
            cache.put(self.provider, url, reply)
        return reply


def _describe(url: str) -> str:
    """Path and query only: enough to read the log, nothing a key could hide in."""
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}" if parts.query else parts.path
