"""Shared setup for the tests that run the dbt models on provider responses."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ubi_ludus.pipeline import config
from ubi_ludus.pipeline.dbt_runner import run_dbt
from ubi_ludus.pipeline.providers.base import RawResponse
from ubi_ludus.pipeline.rights import RightsData, load_rights
from ubi_ludus.pipeline.warehouse import (
    connect,
    load_competitions,
    load_previous_matches,
    load_provider_responses,
    load_rights_tables,
    load_yaml_file,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dbt"
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
    load_yaml_file(con, "raw_teams", FIXTURES / "teams.yml", key="teams")
    load_competitions(con, config.load_competitions())
    load_provider_responses(
        con, [response(cid, payload) for cid, payload in payloads.items()] + extra
    )
    load_previous_matches(con, previous)
    load_rights_tables(con, rights if rights is not None else load_rights())
    con.close()  # DuckDB allows one writer: close before dbt opens the file
    run_dbt(database, work_dir=tmp_path / "dbt-work", run_at=NOW, today=TODAY)
    return database


def query(database: Path, sql: str) -> list[tuple[Any, ...]]:
    con = connect(database)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()
