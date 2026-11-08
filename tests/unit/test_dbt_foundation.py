"""Python and dbt working together: load, build with tests, export, validate."""

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ubi_ludus.pipeline import config
from ubi_ludus.pipeline.dbt_runner import DbtBuildError, run_dbt
from ubi_ludus.pipeline.export import export_teams
from ubi_ludus.pipeline.rights import load_rights
from ubi_ludus.pipeline.validate import SchemaValidationError, validate_file
from ubi_ludus.pipeline.warehouse import (
    connect,
    load_competitions,
    load_previous_matches,
    load_provider_responses,
    load_rights_tables,
    load_teams,
)

pytestmark = pytest.mark.dbt

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dbt"
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def build(tmp_path: Path, teams_file: str) -> Path:
    """Load a teams fixture into a fresh DuckDB file and run dbt on it."""
    database = tmp_path / "warehouse.duckdb"
    con = connect(database)
    load_teams(con, FIXTURES / teams_file)
    load_competitions(con, config.load_competitions())
    load_provider_responses(con, [])  # no matches: these tests are about teams
    load_previous_matches(con, None)
    load_rights_tables(con, load_rights())
    con.close()  # DuckDB allows one writer: close before dbt opens the file
    run_dbt(database, work_dir=tmp_path / "dbt-work")
    return database


@pytest.fixture(scope="module")
def teams_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One build of the good teams file, read by the tests that do not change it."""
    return build(tmp_path_factory.mktemp("teams"), "teams.yml")


def test_teams_go_from_yaml_through_dbt_to_a_valid_teams_json(
    teams_database: Path, tmp_path: Path
) -> None:
    database = teams_database
    out = tmp_path / "out" / "teams.json"

    assert export_teams(database, out, NOW) == 4

    validate_file(out, "teams")
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["schema_version"] == "1.0"
    assert document["generated_at"] == "2026-11-02T09:00:00Z"
    assert [t["id"] for t in document["teams"]] == [
        "estudiantes",
        "flamengo",
        "gremio",
        "palmeiras",
    ]
    flamengo = next(t for t in document["teams"] if t["id"] == "flamengo")
    assert flamengo["colors"] == {"primary": "#C52613", "secondary": "#000000"}
    assert flamengo["aliases"] == ["CR Flamengo", "Flamengo RJ"]
    assert set(flamengo) == {
        "id",
        "name",
        "short_name",
        "aliases",
        "country",
        "colors",
        "kind",
        "shirt",
    }
    # A team is a club unless it says otherwise, and its shirt is its colours unless it says
    # otherwise: the fixture says neither, so both defaults show.
    assert flamengo["kind"] == "club"
    assert flamengo["shirt"] == flamengo["colors"]


def test_a_failing_dbt_test_stops_the_build(tmp_path: Path) -> None:
    """Two teams sharing an alias would make matching ambiguous, so the unique test fails."""
    with pytest.raises(DbtBuildError) as caught:
        build(tmp_path, "teams_ambiguous.yml")
    assert any("unique_stg_team_aliases_alias" in name for name in caught.value.failed)


def test_dbt_problems_before_any_model_runs_are_reported(tmp_path: Path) -> None:
    with pytest.raises(DbtBuildError, match="dbt build failed"):
        run_dbt(tmp_path / "w.duckdb", project_dir=tmp_path / "no-such-project", work_dir=tmp_path)


def test_the_database_setting_is_put_back_after_a_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UBI_LUDUS_DB", "/somewhere/else.duckdb")
    with pytest.raises(DbtBuildError):
        run_dbt(
            tmp_path / "w.duckdb",
            project_dir=tmp_path / "no-such-project",
            work_dir=tmp_path,
            select="teams",
        )
    assert os.environ["UBI_LUDUS_DB"] == "/somewhere/else.duckdb"


def test_export_still_checks_the_schema_after_dbt_passed(
    teams_database: Path, tmp_path: Path
) -> None:
    """dbt tests check consistency; the schema checks the published shape. Both must pass."""
    database = tmp_path / "copy.duckdb"  # a copy: the shared warehouse must stay as dbt built it
    shutil.copy(teams_database, database)
    con = connect(database)
    con.execute("update teams set country = 'Brazil' where id = 'flamengo'")
    con.close()
    out = tmp_path / "out" / "teams.json"

    with pytest.raises(SchemaValidationError, match="country"):
        export_teams(database, out, NOW)
    assert not out.exists()
