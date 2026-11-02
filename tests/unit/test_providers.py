from datetime import UTC, date, datetime
from typing import ClassVar

import pytest

from ubi_ludus.pipeline.config import CompetitionConfig, SourceConfig
from ubi_ludus.pipeline.fetch import FetchOutcome, fetch_all, plan_fetches
from ubi_ludus.pipeline.providers.base import (
    FetchRequest,
    ProviderAdapter,
    ProviderError,
    RawResponse,
)
from ubi_ludus.pipeline.providers.registry import AdapterRegistry, UnknownProviderError
from ubi_ludus.pipeline.window import DateWindow

TODAY = date(2026, 11, 2)
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


class FakeAdapter(ProviderAdapter):
    """Answers every target with one canned response and remembers what it was asked."""

    name: ClassVar[str] = "fake"

    def __init__(self) -> None:
        self.requests: list[FetchRequest] = []

    def fetch(self, request: FetchRequest) -> list[RawResponse]:
        self.requests.append(request)
        return [
            RawResponse(
                provider=self.name,
                resource=f"competitions/{target.provider_id}/matches",
                params={"dateFrom": target.window.date_from.isoformat()},
                fetched_at=NOW,
                payload={"matches": []},
                competition_id=target.competition_id,
            )
            for target in request.targets
        ]


class BrokenAdapter(ProviderAdapter):
    name: ClassVar[str] = "broken"

    def fetch(self, request: FetchRequest) -> list[RawResponse]:
        raise ProviderError("quota exceeded")


def competition(competition_id: str, *sources: SourceConfig) -> CompetitionConfig:
    return CompetitionConfig(competition_id, "Name", "Brasil", "league", tuple(sources))


def test_an_adapter_must_implement_fetch() -> None:
    class Incomplete(ProviderAdapter):
        name: ClassVar[str] = "incomplete"

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_raw_responses_must_be_in_utc() -> None:
    with pytest.raises(ValueError, match="UTC"):
        RawResponse("fake", "x", {}, datetime(2026, 11, 2, 9, 0), {})  # noqa: DTZ001


def test_the_registry_builds_adapters_by_name() -> None:
    registry = AdapterRegistry()
    registry.register("fake", FakeAdapter)
    assert "fake" in registry
    assert registry.names() == ["fake"]
    assert isinstance(registry.create("fake"), FakeAdapter)


def test_the_registry_builds_a_new_adapter_each_time() -> None:
    registry = AdapterRegistry()
    registry.register("fake", FakeAdapter)
    assert registry.create("fake") is not registry.create("fake")


def test_registering_a_name_twice_is_rejected() -> None:
    registry = AdapterRegistry()
    registry.register("fake", FakeAdapter)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("fake", FakeAdapter)


def test_an_unknown_provider_lists_what_is_available() -> None:
    registry = AdapterRegistry()
    registry.register("fake", FakeAdapter)
    with pytest.raises(UnknownProviderError, match="'nope'.*Registered: fake"):
        registry.create("nope")


def test_an_adapter_registered_under_the_wrong_name_is_rejected() -> None:
    registry = AdapterRegistry()
    registry.register("not-fake", FakeAdapter)
    with pytest.raises(ValueError, match="calls itself 'fake'"):
        registry.create("not-fake")


def test_plan_groups_competitions_by_provider_with_their_own_windows() -> None:
    plan = plan_fetches(
        [
            competition("serie-a", SourceConfig("football-data", "BSA", 14)),
            competition("copa", SourceConfig("api-football", "73", 1)),
            competition("libertadores", SourceConfig("football-data", "CLI", 14)),
            competition("not-covered"),
        ],
        TODAY,
    )
    assert [r.provider for r in plan] == ["api-football", "football-data"]
    api_football, football_data = plan
    assert [t.provider_id for t in football_data.targets] == ["BSA", "CLI"]
    assert football_data.targets[0].window == DateWindow(date(2026, 11, 1), date(2026, 11, 16))
    assert api_football.targets[0].window == DateWindow(date(2026, 11, 1), date(2026, 11, 3))
    assert football_data.today == TODAY


def test_plan_for_competitions_without_sources_is_empty() -> None:
    assert plan_fetches([competition("not-covered")], TODAY) == []


def test_fetch_all_runs_every_request_through_its_adapter() -> None:
    adapter = FakeAdapter()
    registry = AdapterRegistry()
    registry.register("fake", lambda: adapter)
    plan = plan_fetches(
        [
            competition("a", SourceConfig("fake", "A", 14)),
            competition("b", SourceConfig("fake", "B", 1)),
        ],
        TODAY,
    )
    [outcome] = fetch_all(plan, registry)
    assert outcome.error is None
    assert [r.competition_id for r in outcome.responses] == ["a", "b"]
    assert adapter.requests == plan


def test_a_failing_provider_does_not_hide_the_others() -> None:
    registry = AdapterRegistry()
    registry.register("fake", FakeAdapter)
    registry.register("broken", BrokenAdapter)
    plan = plan_fetches(
        [
            competition("a", SourceConfig("fake", "A", 14)),
            competition("b", SourceConfig("broken", "B", 14)),
        ],
        TODAY,
    )
    outcomes = {o.provider: o for o in fetch_all(plan, registry)}
    assert outcomes["fake"].error is None
    assert len(outcomes["fake"].responses) == 1
    assert outcomes["broken"] == FetchOutcome("broken", (), "quota exceeded")


def test_a_config_provider_without_an_adapter_stops_the_run_before_any_call() -> None:
    adapter = FakeAdapter()
    registry = AdapterRegistry()
    registry.register("fake", lambda: adapter)
    plan = plan_fetches(
        [
            competition("a", SourceConfig("fake", "A", 14)),
            competition("b", SourceConfig("ghost", "B", 14)),
        ],
        TODAY,
    )
    with pytest.raises(UnknownProviderError, match="ghost"):
        fetch_all(plan, registry)
    assert adapter.requests == []


def test_unexpected_errors_are_not_swallowed() -> None:
    class Buggy(ProviderAdapter):
        name: ClassVar[str] = "buggy"

        def fetch(self, request: FetchRequest) -> list[RawResponse]:
            raise RuntimeError("a bug, not an outage")

    registry = AdapterRegistry()
    registry.register("buggy", Buggy)
    plan = plan_fetches([competition("a", SourceConfig("buggy", "A", 14))], TODAY)
    with pytest.raises(RuntimeError, match="a bug"):
        fetch_all(plan, registry)
