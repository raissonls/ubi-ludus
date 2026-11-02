"""Turn the competition config into fetch requests and run them through the adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from ubi_ludus.pipeline.config import CompetitionConfig
from ubi_ludus.pipeline.providers.base import (
    FetchRequest,
    FetchTarget,
    ProviderError,
    RawResponse,
)
from ubi_ludus.pipeline.providers.registry import AdapterRegistry, UnknownProviderError
from ubi_ludus.pipeline.window import window_for


@dataclass(frozen=True)
class FetchOutcome:
    """What one provider gave back. ``error`` is set when it failed."""

    provider: str
    responses: tuple[RawResponse, ...]
    error: str | None = None


def plan_fetches(competitions: Sequence[CompetitionConfig], today: date) -> list[FetchRequest]:
    """One request per provider, listing every competition it serves and the days to ask for."""
    grouped: dict[str, list[FetchTarget]] = {}
    for competition in competitions:
        for source in competition.sources:
            window = window_for(today, source.horizon_days)
            target = FetchTarget(competition.id, source.provider_id, window)
            grouped.setdefault(source.provider, []).append(target)
    return [
        FetchRequest(provider, tuple(targets), today)
        for provider, targets in sorted(grouped.items())
    ]


def fetch_all(requests: Sequence[FetchRequest], registry: AdapterRegistry) -> list[FetchOutcome]:
    """Run every request. A provider that fails does not stop the others.

    Raises :class:`UnknownProviderError` before any call if the config names a provider with
    no adapter, because that is a setup mistake, not a runtime outage.
    """
    missing = sorted({r.provider for r in requests if r.provider not in registry})
    if missing:
        registered = ", ".join(registry.names()) or "none"
        raise UnknownProviderError(
            f"No adapter registered for: {', '.join(missing)}. Registered: {registered}"
        )
    outcomes: list[FetchOutcome] = []
    for request in requests:
        try:
            # Building the adapter can fail too, for example when its API key is not set.
            adapter = registry.create(request.provider)
            responses = adapter.fetch(request)
        except ProviderError as exc:
            outcomes.append(FetchOutcome(request.provider, (), str(exc)))
        else:
            outcomes.append(FetchOutcome(request.provider, tuple(responses)))
    return outcomes
