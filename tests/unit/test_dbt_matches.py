"""Provider responses go through dbt into matches.json, with team mapping and local dates."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from ubi_ludus.pipeline import config
from ubi_ludus.pipeline.dbt_runner import DbtBuildError, run_dbt
from ubi_ludus.pipeline.export import export_competitions, export_matches
from ubi_ludus.pipeline.providers.base import RawResponse
from ubi_ludus.pipeline.validate import validate_file
from ubi_ludus.pipeline.warehouse import (
    connect,
    load_competitions,
    load_provider_responses,
    load_yaml_file,
)

pytestmark = pytest.mark.dbt

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dbt"
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
CODES = {"brasileirao-serie-a": "BSA", "uefa-champions-league": "CL"}

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


def build(
    tmp_path: Path, change: Callable[[Payloads], list[RawResponse] | None] | None = None
) -> Path:
    """Load teams, competitions and fixture responses into a fresh DuckDB file and run dbt.

    ``change`` may edit the payloads first, and may return extra responses to load as well.
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
    con.close()  # DuckDB allows one writer: close before dbt opens the file
    run_dbt(database, work_dir=tmp_path / "dbt-work")
    return database


@pytest.fixture(scope="module")
def database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One build of the unchanged fixtures, shared by the tests that only read from it."""
    return build(tmp_path_factory.mktemp("matches"))


def query(database: Path, sql: str) -> list[tuple[Any, ...]]:
    con = connect(database)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_matches_go_from_provider_responses_to_a_valid_matches_json(
    database: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out" / "matches.json"

    # 9 matches in the fixture; the one with an unknown club is held back.
    assert export_matches(database, out, NOW) == 8

    validate_file(out, "matches")
    matches = {m["id"]: m for m in json.loads(out.read_text(encoding="utf-8"))["matches"]}
    assert matches["football-data-910001"] == {
        "id": "football-data-910001",
        "competition_id": "brasileirao-serie-a",
        "season": "2026",
        "round": "33",
        "kickoff_utc": "2026-11-01T19:00:00Z",
        "home_team_id": "flamengo",
        "away_team_id": "gremio",
        "status": "finished",
        "broadcasts": [],
    }
    assert list(matches.values()) == sorted(
        matches.values(), key=lambda m: (m["kickoff_utc"], m["id"])
    )


def test_provider_codes_become_our_statuses_seasons_and_rounds(database: Path) -> None:
    rows = {r[0]: r[1:] for r in query(database, "select id, status, season, round from matches")}
    assert rows["football-data-910002"][0] == "scheduled"  # TIMED
    assert rows["football-data-910003"][0] == "live"  # IN_PLAY
    assert rows["football-data-910004"][0] == "postponed"
    assert rows["football-data-910007"] == ("scheduled", "2026", "final")  # knockout: the stage
    assert rows["football-data-920001"] == ("scheduled", "2026-27", "3")  # season crosses a year
    assert rows["football-data-920002"] == ("scheduled", "2026-27", "last-16")


def test_local_dates_follow_the_sao_paulo_zone_around_midnight(database: Path) -> None:
    local = {
        r[0]: (r[1], r[2])
        for r in query(
            database,
            "select match_id, kickoff_local_date, kickoff_local_time from int_matches",
        )
    }
    # 02:30 UTC is 23:30 the evening before in Brazil; 03:00 UTC is exactly midnight.
    assert local["football-data-910003"] == (date(2026, 11, 2), "23:30")
    assert local["football-data-910004"] == (date(2026, 11, 3), "00:00")
    # Brazil used daylight saving until 2019 (UTC-2 in December 2018). A fixed -03:00 offset
    # would say 23:30 on 30 November; the IANA zone says 00:30 on 1 December.
    assert local["football-data-910005"] == (date(2018, 12, 1), "00:30")


def test_kickoff_is_published_in_utc(database: Path) -> None:
    kickoffs = query(database, "select kickoff_utc from matches where id = 'football-data-910003'")
    assert kickoffs == [("2026-11-03T02:30:00Z",)]


def test_a_final_between_undecided_teams_is_kept_with_null_teams(database: Path) -> None:
    final = query(
        database,
        "select home_team_id, away_team_id from matches where id = 'football-data-910007'",
    )
    assert final == [(None, None)]


def test_a_match_with_an_unknown_club_is_held_back_and_reported(database: Path) -> None:

    assert query(database, "select 1 from matches where id = 'football-data-910006'") == []
    assert query(
        database,
        "select team_name, resolution, match_count from int_unmapped_teams",
    ) == [("Clube Desconhecido", "unmapped", 1)]


def test_adding_the_clubs_spelling_as_an_alias_brings_the_match_back(tmp_path: Path) -> None:
    def rename(payloads: Payloads) -> None:
        for match in payloads["brasileirao-serie-a"]["matches"]:
            if match["homeTeam"]["name"] == "Clube Desconhecido":
                match["homeTeam"]["name"] = "SE PALMEIRAS"  # case and accents never matter
                match["homeTeam"]["shortName"] = "Verdão"

    database = build(tmp_path, rename)
    assert query(
        database, "select home_team_id from matches where id = 'football-data-910006'"
    ) == [("palmeiras",)]


def test_the_same_match_in_two_responses_keeps_the_freshest(tmp_path: Path) -> None:
    def add_newer_copy(payloads: Payloads) -> list[RawResponse]:
        original = payloads["brasileirao-serie-a"]["matches"][1]
        newer = {**original, "status": "POSTPONED", "lastUpdated": "2026-11-02T08:00:00Z"}
        return [response("brasileirao-serie-a", {"matches": [newer]}, fetched_hour=8)]

    database = build(tmp_path, add_newer_copy)
    assert query(database, "select status from matches where id = 'football-data-910002'") == [
        ("postponed",)
    ]


def test_a_status_we_do_not_know_stops_the_build(tmp_path: Path) -> None:
    def invent_status(payloads: Payloads) -> None:
        payloads["brasileirao-serie-a"]["matches"][0]["status"] = "ABANDONED"

    with pytest.raises(DbtBuildError) as caught:
        build(tmp_path, invent_status)
    assert any("accepted_values_stg_football_data_matches" in n for n in caught.value.failed)


def test_a_name_that_fits_two_teams_is_ambiguous_and_the_match_is_held_back(
    tmp_path: Path,
) -> None:
    """The provider's full name fits Flamengo and its short name fits Grêmio: never guess."""

    def fit_two_teams(payloads: Payloads) -> None:
        away = payloads["brasileirao-serie-a"]["matches"][0]["awayTeam"]
        away["name"] = "Flamengo"
        away["shortName"] = "Grêmio"

    database = build(tmp_path, fit_two_teams)
    assert query(database, "select 1 from matches where id = 'football-data-910001'") == []
    assert query(database, "select resolution from int_unmapped_teams order by resolution") == [
        ("ambiguous",),
        ("unmapped",),
    ]  # the second is the unknown club of the fixture


def test_competitions_are_published_with_their_provider_ids_and_coverage(
    database: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out" / "competitions.json"

    assert export_competitions(database, out, NOW) == 17

    validate_file(out, "competitions")
    by_id = {c["id"]: c for c in json.loads(out.read_text(encoding="utf-8"))["competitions"]}
    assert by_id["brasileirao-serie-a"]["provider_ids"] == {"football-data": "BSA"}
    assert by_id["brasileirao-serie-a"]["coverage"] == "full"
    assert by_id["copa-do-brasil"]["coverage"] == "short"
    assert by_id["copa-do-brasil"]["provider_ids"] == {"api-football": "73"}
