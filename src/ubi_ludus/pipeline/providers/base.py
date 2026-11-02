"""The contract every data provider adapter follows.

An adapter only fetches. It returns each provider response exactly as received, wrapped in
a :class:`RawResponse`; cleaning, merging and checking happen later in dbt (ADR-002). Adding
a provider means writing one subclass and one entry in ``config/competitions.yml``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import ClassVar

from ubi_ludus.pipeline.window import DateWindow


class ProviderError(Exception):
    """A provider could not be reached or refused the request. Other providers still run."""


@dataclass(frozen=True)
class FetchTarget:
    """One competition to fetch, in the provider's own terms."""

    competition_id: str
    provider_id: str
    window: DateWindow


@dataclass(frozen=True)
class FetchRequest:
    """Everything one provider has to fetch in one run."""

    provider: str
    targets: tuple[FetchTarget, ...]
    today: date


@dataclass(frozen=True)
class RawResponse:
    """One provider response, untouched.

    ``competition_id`` is ours and is set when the call was for one competition. It is ``None``
    for calls that cover many, such as a whole day across all leagues.
    """

    provider: str
    resource: str
    params: Mapping[str, str]
    fetched_at: datetime
    payload: object
    competition_id: str | None = None

    def __post_init__(self) -> None:
        if self.fetched_at.utcoffset() != timedelta(0):
            raise ValueError("fetched_at must be timezone-aware and in UTC")


class ProviderAdapter(ABC):
    """Fetches fixtures from one provider."""

    name: ClassVar[str]
    """Matches the ``provider`` value used in ``config/competitions.yml``."""

    @abstractmethod
    def fetch(self, request: FetchRequest) -> list[RawResponse]:
        """Fetch what the request asks for.

        Stay inside the provider's rate limits, never log keys, and raise
        :class:`ProviderError` when the provider cannot be used.
        """
