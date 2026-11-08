"""Shared setup for the tests that run the dbt models on provider responses."""

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, ClassVar

from ubi_ludus.pipeline import config
from ubi_ludus.pipeline.dbt_runner import run_dbt
from ubi_ludus.pipeline.providers.base import FetchRequest, ProviderAdapter, RawResponse
from ubi_ludus.pipeline.providers.registry import AdapterRegistry
from ubi_ludus.pipeline.rights import Override, RightsData, RightsRule, load_rights
from ubi_ludus.pipeline.warehouse import (
    connect,
    load_competitions,
    load_previous_matches,
    load_provider_responses,
    load_rights_tables,
    load_teams,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dbt"
# The competitions as they were before API-Football was dropped (ADR-003): its adapter and dbt
# model are kept, switched off, and their tests need competitions that use it.
LEGACY_COMPETITIONS = (
    Path(__file__).resolve().parents[1] / "fixtures" / "competitions-with-api-football.yml"
)
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
TODAY = date(2026, 11, 2)
# The code is only the label in the resource name. Copa do Brasil is served by another provider
# in real life; here it stands in for a competition with a one-day horizon.
CODES = {
    "brasileirao-serie-a": "BSA",
    "uefa-champions-league": "CL",
    "copa-do-brasil": "CDB",
}

Payloads = dict[str, dict[str, Any]]


def fixture_payloads() -> Payloads:
    payloads: Payloads = json.loads(
        (FIXTURES / "football_data_matches.json").read_text(encoding="utf-8")
    )
    return payloads


def response(competition_id: str, payload: dict[str, Any], fetched_hour: int = 9) -> RawResponse:
    return RawResponse(
        provider="football-data",
        resource=f"competitions/{CODES[competition_id]}/matches",
        params={},
        fetched_at=datetime(2026, 11, 2, fetched_hour, tzinfo=UTC),
        payload=payload,
        competition_id=competition_id,
    )


def api_football_fixture(
    fixture_id: int,
    league_id: int,
    kickoff: str,
    home: str,
    away: str,
    status: str = "NS",
    round_label: str | None = "Regular Season - 33",
) -> dict[str, Any]:
    """One entry of the ``response`` list of API-Football's ``fixtures`` endpoint."""
    return {
        "fixture": {"id": fixture_id, "date": kickoff, "status": {"short": status}},
        "league": {"id": league_id, "season": 2026, "round": round_label},
        "teams": {"home": {"id": 1, "name": home}, "away": {"id": 2, "name": away}},
    }


def api_football_response(fixtures: list[dict[str, Any]], fetched_hour: int = 9) -> RawResponse:
    return RawResponse(
        provider="api-football",
        resource="fixtures",
        params={"date": "2026-11-02"},
        fetched_at=datetime(2026, 11, 2, fetched_hour, tzinfo=UTC),
        payload={"errors": [], "response": fixtures},
    )


def rule(
    competition: str,
    scope: str,
    broadcasters: list[str],
    valid_from: str = "2026-01-01",
    valid_to: str = "2026-12-31",
    scope_value: str | None = None,
    season: str = "2026",
) -> RightsRule:
    """A rights rule for the tests. The broadcaster ids must be in the real catalogue."""
    return RightsRule(
        competition_id=competition,
        season=season,
        scope=scope,  # type: ignore[arg-type]
        scope_value=scope_value,
        broadcasters=tuple(broadcasters),
        valid_from=date.fromisoformat(valid_from),
        valid_to=date.fromisoformat(valid_to),
        source="A made-up source for the tests",
        notes=None,
    )


def override(
    match_id: str, action: str, broadcasters: list[str], added_at: str = "2026-11-01"
) -> Override:
    """A match-level override for the tests."""
    return Override(
        match_id=match_id,
        action=action,  # type: ignore[arg-type]
        broadcasters=tuple(broadcasters),
        reason="A made-up reason for the tests",
        added_at=date.fromisoformat(added_at),
    )


def rights_with(*rules: RightsRule, overrides: tuple[Override, ...] = ()) -> RightsData:
    """The repository's catalogue with these rules and overrides in place of its own."""
    return replace(load_rights(), rules=tuple(rules), overrides=overrides)


def build(
    tmp_path: Path,
    change: Callable[[Payloads], list[RawResponse] | None] | None = None,
    previous: dict[str, Any] | None = None,
    rights: RightsData | None = None,
) -> Path:
    """Load teams, competitions and fixture responses into a fresh DuckDB file and run dbt.

    ``change`` may edit the payloads first, and may return extra responses to load as well.
    ``previous`` stands for the previously published matches.json (none by default).
    """
    payloads = fixture_payloads()
    extra = (change(payloads) if change else None) or []
    database = tmp_path / "warehouse.duckdb"
    con = connect(database)
    load_teams(con, FIXTURES / "teams.yml")
    load_competitions(con, config.load_competitions(LEGACY_COMPETITIONS))
    load_provider_responses(
        con, [response(cid, payload) for cid, payload in payloads.items()] + extra
    )
    load_previous_matches(con, previous)
    load_rights_tables(con, rights if rights is not None else rights_with())
    con.close()  # DuckDB allows one writer: close before dbt opens the file
    run_dbt(database, work_dir=tmp_path / "dbt-work", run_at=NOW, today=TODAY)
    return database


def query(database: Path, sql: str) -> list[tuple[Any, ...]]:
    con = connect(database)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


class FixtureAdapter(ProviderAdapter):
    """A football-data.org stand-in that answers every request with the dbt fixture matches."""

    name: ClassVar[str] = "football-data"

    def fetch(self, request: FetchRequest) -> list[RawResponse]:
        return [response(cid, payload) for cid, payload in fixture_payloads().items()]


class SilentAdapter(ProviderAdapter):
    """A provider that has nothing to say, so only the other one feeds the run."""

    name: ClassVar[str] = "api-football"

    def fetch(self, request: FetchRequest) -> list[RawResponse]:
        return []


def fixture_registry() -> AdapterRegistry:
    """Both providers of the real config, answering from the fixtures: no network, no keys."""
    registry = AdapterRegistry()
    registry.register(FixtureAdapter.name, FixtureAdapter)
    registry.register(SilentAdapter.name, SilentAdapter)
    return registry
