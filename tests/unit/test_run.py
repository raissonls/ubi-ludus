"""Running the pipeline up to a built warehouse."""

import logging
from collections.abc import Callable
from pathlib import Path

import pytest
from dbt_helpers import (
    FIXTURES,
    LEGACY_COMPETITIONS,
    NOW,
    FixtureAdapter,
    fixture_registry,
    query,
    rights_with,
)

from ubi_ludus.pipeline.config import load_competitions
from ubi_ludus.pipeline.providers.base import (
    FetchRequest,
    ProviderAdapter,
    ProviderError,
    RawResponse,
)
from ubi_ludus.pipeline.providers.registry import AdapterRegistry
from ubi_ludus.pipeline.run import DEFAULT_TEAMS_PATH, PipelineError, build_warehouse

pytestmark = pytest.mark.dbt

TEAMS = FIXTURES / "teams.yml"


class Broken(ProviderAdapter):
    name = "football-data"

    def fetch(self, request: FetchRequest) -> list[RawResponse]:
        raise ProviderError("the provider is down")


def registry_of(*adapters: Callable[[], ProviderAdapter]) -> AdapterRegistry:
    registry = AdapterRegistry()
    for factory in adapters:
        registry.register(factory().name, factory)
    return registry


def test_the_pipeline_goes_from_provider_answers_to_a_tested_warehouse_with_the_real_teams(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    result = build_warehouse(
        tmp_path / "w.duckdb",
        now=NOW,
        registry=fixture_registry(),
        competitions=load_competitions(LEGACY_COMPETITIONS),  # with API-Football, as before ADR-003
        teams_path=DEFAULT_TEAMS_PATH,  # the curated file: its unique-alias tests run on it too
        rights=rights_with(),
        work_dir=tmp_path / "dbt-work",
    )

    assert query(result.database, "select count(*) from matches") == [(7,)]
    assert [o.provider for o in result.outcomes] == ["api-football", "football-data"]
    assert result.failed_providers == {}
    assert "Provider calls this run" in caplog.text  # fetch_all logged the run's total


def test_a_provider_that_fails_is_reported_but_the_other_still_feeds_the_run(
    tmp_path: Path,
) -> None:
    class FailingApiFootball(Broken):
        name = "api-football"

    registry = registry_of(FixtureAdapter, FailingApiFootball)
    result = build_warehouse(
        tmp_path / "w.duckdb",
        now=NOW,
        registry=registry,
        competitions=load_competitions(LEGACY_COMPETITIONS),
        teams_path=TEAMS,
        rights=rights_with(),
        work_dir=tmp_path / "dbt-work",
    )
    assert result.failed_providers == {"api-football": "the provider is down"}
    assert query(result.database, "select count(*) from matches") == [(7,)]


def test_with_no_data_from_any_provider_the_run_stops_and_says_why(tmp_path: Path) -> None:
    class FailingFootballData(Broken):
        name = "football-data"

    class FailingApiFootball(Broken):
        name = "api-football"

    with pytest.raises(PipelineError, match="No provider gave any data") as caught:
        build_warehouse(
            tmp_path / "w.duckdb",
            now=NOW,
            registry=registry_of(FailingFootballData, FailingApiFootball),
            teams_path=TEAMS,
            rights=rights_with(),
        )
    assert "the provider is down" in str(caught.value)


def test_without_the_curated_teams_the_run_stops_before_calling_anyone(tmp_path: Path) -> None:
    called: list[str] = []

    class Spy(ProviderAdapter):
        name = "football-data"

        def fetch(self, request: FetchRequest) -> list[RawResponse]:
            called.append("called")
            return []

    with pytest.raises(PipelineError, match=r"teams.yml is missing.*#77"):
        build_warehouse(
            tmp_path / "w.duckdb",
            now=NOW,
            registry=registry_of(Spy),
            teams_path=tmp_path / "teams.yml",
            rights=rights_with(),
        )
    assert called == []


def test_the_default_teams_file_is_the_one_in_the_repository() -> None:
    assert DEFAULT_TEAMS_PATH.parent.name == "data"
    assert DEFAULT_TEAMS_PATH.name == "teams.yml"
