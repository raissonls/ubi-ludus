import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ubi_ludus.pipeline.providers.base import RawResponse
from ubi_ludus.pipeline.warehouse import (
    connect,
    load_json_file,
    load_provider_responses,
    load_records,
    load_yaml_file,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dbt"


def test_connect_creates_missing_folders(tmp_path: Path) -> None:
    database = tmp_path / "deep" / "er" / "warehouse.duckdb"
    connect(database).close()
    assert database.is_file()


def test_records_become_rows_with_nested_values_kept(tmp_path: Path) -> None:
    con = connect(tmp_path / "w.duckdb")
    count = load_records(
        con,
        "raw_things",
        [
            {"id": "a", "tags": ["x", "y"], "meta": {"n": 1}},
            {"id": "b", "tags": [], "meta": {"n": 2}},
        ],
    )
    assert count == 2
    rows = con.execute("select id, tags, meta.n from raw_things order by id").fetchall()
    assert rows == [("a", ["x", "y"], 1), ("b", [], 2)]


def test_loading_again_replaces_the_table(tmp_path: Path) -> None:
    con = connect(tmp_path / "w.duckdb")
    load_records(con, "raw_things", [{"id": "a"}, {"id": "b"}])
    load_records(con, "raw_things", [{"id": "c"}])
    assert con.execute("select id from raw_things").fetchall() == [("c",)]


def test_an_empty_list_is_rejected(tmp_path: Path) -> None:
    con = connect(tmp_path / "w.duckdb")
    with pytest.raises(ValueError, match="empty"):
        load_records(con, "raw_things", [])


@pytest.mark.parametrize("name", ["teams", "raw_", "raw_Teams", "raw_x; drop table raw_x", "RAW_x"])
def test_only_raw_table_names_are_accepted(tmp_path: Path, name: str) -> None:
    con = connect(tmp_path / "w.duckdb")
    with pytest.raises(ValueError, match="raw_something"):
        load_records(con, name, [{"id": "a"}])


def test_a_yaml_file_is_loaded_from_under_its_key(tmp_path: Path) -> None:
    con = connect(tmp_path / "w.duckdb")
    assert load_yaml_file(con, "raw_teams", FIXTURES / "teams.yml", key="teams") == 4
    ids = [row[0] for row in con.execute("select id from raw_teams order by id").fetchall()]
    assert ids == ["estudiantes", "flamengo", "gremio", "palmeiras"]


def test_a_json_file_can_hold_the_list_directly(tmp_path: Path) -> None:
    source = tmp_path / "things.json"
    source.write_text(json.dumps([{"id": "a"}, {"id": "b"}]), encoding="utf-8")
    con = connect(tmp_path / "w.duckdb")
    assert load_json_file(con, "raw_things", source) == 2


def test_a_json_file_can_hold_the_list_under_a_key(tmp_path: Path) -> None:
    source = tmp_path / "things.json"
    source.write_text(json.dumps({"things": [{"id": "a"}]}), encoding="utf-8")
    con = connect(tmp_path / "w.duckdb")
    assert load_json_file(con, "raw_things", source, key="things") == 1


def test_something_that_is_not_a_list_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "things.json"
    source.write_text(json.dumps({"things": {"id": "a"}}), encoding="utf-8")
    con = connect(tmp_path / "w.duckdb")
    with pytest.raises(ValueError, match="list of records under 'things'"):
        load_json_file(con, "raw_things", source, key="things")
    with pytest.raises(ValueError, match="list of records in things.json"):
        load_json_file(con, "raw_things", source)


def test_provider_responses_keep_their_payload_untouched(tmp_path: Path) -> None:
    payload = {"matches": [{"id": 1, "homeTeam": None}], "note": "Série A"}
    response = RawResponse(
        provider="football-data",
        resource="competitions/BSA/matches",
        params={"dateTo": "2026-11-16", "dateFrom": "2026-11-01"},
        fetched_at=datetime(2026, 11, 2, 9, 0, tzinfo=UTC),
        payload=payload,
        competition_id="brasileirao-serie-a",
    )
    con = connect(tmp_path / "w.duckdb")
    assert load_provider_responses(con, [response]) == 1
    provider, resource, params, fetched_at, competition_id, stored = (
        con.execute(
            "select provider, resource, params, fetched_at, competition_id, payload "
            "from raw_provider_responses"
        ).fetchone()
        or (None,) * 6
    )
    assert (provider, resource, competition_id) == (
        "football-data",
        "competitions/BSA/matches",
        "brasileirao-serie-a",
    )
    assert json.loads(params) == {"dateFrom": "2026-11-01", "dateTo": "2026-11-16"}
    assert fetched_at == datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    assert json.loads(stored) == payload


def test_no_provider_responses_still_creates_the_table(tmp_path: Path) -> None:
    con = connect(tmp_path / "w.duckdb")
    assert load_provider_responses(con, []) == 0
    assert con.execute("select count(*) from raw_provider_responses").fetchone() == (0,)
