"""Writing the five published files, and reading the local .env."""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from dbt_helpers import FIXTURES, NOW, fixture_registry, rights_with, rule
from log_helpers import leave_logging_as_found  # noqa: F401 - an autouse fixture

from ubi_ludus.pipeline import export, publish
from ubi_ludus.pipeline.env import load_env_file
from ubi_ludus.pipeline.fetch import FetchOutcome
from ubi_ludus.pipeline.providers.guard import CallLog
from ubi_ludus.pipeline.publish import Published
from ubi_ludus.pipeline.rights import RightsData
from ubi_ludus.pipeline.run import RunResult, build_warehouse
from ubi_ludus.pipeline.validate import SchemaValidationError, validate_file

# The warehouse is built from the dbt fixtures, so it needs dbt.
dbt = pytest.mark.dbt

RIGHTS = rights_with(rule("brasileirao-serie-a", "all", ["globo", "sportv"]))


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> RunResult:
    work = tmp_path_factory.mktemp("publish")
    return build_warehouse(
        work / "warehouse.duckdb",
        now=NOW,
        registry=fixture_registry(),
        teams_path=FIXTURES / "teams.yml",
        rights=RIGHTS,
        work_dir=work / "dbt-work",
    )


def read(directory: Path, name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
    return document


@dbt
def test_the_five_files_are_written_and_each_one_is_valid(built: RunResult, tmp_path: Path) -> None:
    result = publish.publish(built.database, tmp_path / "data", rights=RIGHTS, now=NOW)

    for name in publish.FILES:
        validate_file(tmp_path / "data" / f"{name}.json", name)
    assert result.counts == {
        "matches": 7,
        "teams": 4,
        "competitions": 17,
        "broadcasters": len(RIGHTS.broadcasters),
        "services": len(RIGHTS.services),
    }


@dbt
def test_the_status_says_when_it_worked_and_how_much_is_unknown(
    built: RunResult, tmp_path: Path
) -> None:
    result = publish.publish(built.database, tmp_path, rights=RIGHTS, now=NOW)
    status = read(tmp_path, "status")
    matches = read(tmp_path, "matches")["matches"]

    assert status["generated_at"] == status["last_success_at"] == "2026-11-02T09:00:00Z"
    assert status["record_counts"] == result.counts
    unknown = [m for m in matches if m["broadcasts"][0]["confidence"] == "unknown"]
    assert 0 < len(unknown) < len(matches)  # Série A has a rule, the Champions League has none
    assert status["unknown_ratio"] == round(len(unknown) / len(matches), 4) == result.unknown_ratio


@dbt
def test_the_broadcasters_file_is_the_rights_catalogue(built: RunResult, tmp_path: Path) -> None:
    publish.publish(built.database, tmp_path, rights=RIGHTS, now=NOW)
    document = read(tmp_path, "broadcasters")
    assert [b["id"] for b in document["broadcasters"]] == [b.id for b in RIGHTS.broadcasters]
    globoplay = next(s for s in document["services"] if s["id"] == "globoplay-canais")
    assert "sportv" in globoplay["includes_broadcasters"]
    free = next(b for b in document["broadcasters"] if b["id"] == "globo")
    assert free["service_id"] is None


@dbt
def test_nothing_is_written_when_one_document_is_invalid(
    built: RunResult, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The files of the last good run stay as they were."""
    out = tmp_path / "data"
    out.mkdir()
    (out / "matches.json").write_text('{"last good run": true}', encoding="utf-8")

    def refuse(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise SchemaValidationError("status", ["/unknown_ratio: nonsense"])

    monkeypatch.setattr(export, "build_status_document", refuse)
    with pytest.raises(SchemaValidationError):
        publish.publish(built.database, out, rights=RIGHTS, now=NOW)

    assert [p.name for p in out.iterdir()] == ["matches.json"]
    assert json.loads((out / "matches.json").read_text(encoding="utf-8")) == {"last good run": True}


def test_with_no_matches_the_unknown_ratio_is_null_not_a_division_by_zero() -> None:
    now = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    documents: dict[str, dict[str, object]] = {
        "matches": {"matches": []},
        "teams": {"teams": []},
        "competitions": {"competitions": []},
        "broadcasters": {"broadcasters": [], "services": []},
    }
    status = export.build_status_document(documents, now)
    assert status["unknown_ratio"] is None
    assert status["record_counts"] == {
        "matches": 0,
        "teams": 0,
        "competitions": 0,
        "broadcasters": 0,
        "services": 0,
    }


def test_the_broadcasters_document_works_without_a_warehouse() -> None:
    rights: RightsData = rights_with()
    document = export.build_broadcasters_document(rights, NOW)
    assert document["generated_at"] == "2026-11-02T09:00:00Z"
    assert len(document["broadcasters"]) == len(rights.broadcasters)  # type: ignore[arg-type]


# --- the command line ---------------------------------------------------------------------------


@dbt
def test_the_command_writes_the_files_and_says_what(
    built: RunResult,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(publish, "load_rights", lambda: RIGHTS)
    out = tmp_path / "data"

    assert publish.main(["--database", str(built.database), "--out", str(out)]) == 0

    assert sorted(p.name for p in out.iterdir()) == sorted(f"{n}.json" for n in publish.FILES)
    assert f"Wrote 5 files to {out}" in capsys.readouterr().out


@dbt
def test_with_run_the_command_loads_the_env_file_and_builds_the_warehouse_first(
    built: RunResult, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_build(
        database: Path,
        *,
        now: datetime,
        cache_dir: Path | None = None,
        previous_url: str | None = None,
    ) -> RunResult:
        calls.append(f"build {database.name} cache={cache_dir} previous={previous_url}")
        return built

    def fake_env() -> list[str]:
        calls.append("env")
        return []

    monkeypatch.setattr(publish, "load_env_file", fake_env)
    monkeypatch.setattr(publish, "build_warehouse", fake_build)
    monkeypatch.setattr(publish, "load_rights", lambda: RIGHTS)

    publish.main(
        [
            "--run",
            "--database",
            str(built.database),
            "--out",
            str(tmp_path),
            "--cache-dir",
            "c",
            "--previous-url",
            "https://example.org/data/matches.json",
        ]
    )

    expected = f"build {built.database.name} cache=c previous=https://example.org/data/matches.json"
    assert calls == ["env", expected]


def test_the_defaults_point_at_the_site_data_folder_and_the_dbt_warehouse() -> None:
    assert publish.DEFAULT_OUT.parts[-2:] == ("site", "data")
    assert publish.DEFAULT_DATABASE.name == "ubi_ludus.duckdb"


# --- the .env file -------------------------------------------------------------------------------


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A private copy of the environment, so what the tests set is gone afterwards."""
    monkeypatch.setattr(os, "environ", dict(os.environ))


def test_the_env_file_sets_the_variables_it_holds(tmp_path: Path, clean_environment: None) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# provider keys\n\nFIRST=abc\nSECOND = \"quoted value\"\nTHIRD='single'\n"
        "EMPTY=\nNO_EQUALS\n",
        encoding="utf-8",
    )
    names = load_env_file(path)
    assert names == ["FIRST", "SECOND", "THIRD"]
    assert (os.environ["FIRST"], os.environ["SECOND"], os.environ["THIRD"]) == (
        "abc",
        "quoted value",
        "single",
    )
    assert "EMPTY" not in os.environ and "NO_EQUALS" not in os.environ


def test_a_variable_already_set_is_never_replaced_by_the_file(
    tmp_path: Path, clean_environment: None
) -> None:
    os.environ["API_KEY_FOR_TEST"] = "from the real environment"
    path = tmp_path / ".env"
    path.write_text("API_KEY_FOR_TEST=from the file\n", encoding="utf-8")
    assert load_env_file(path) == []
    assert os.environ["API_KEY_FOR_TEST"] == "from the real environment"


def test_a_missing_env_file_is_fine(tmp_path: Path, clean_environment: None) -> None:
    assert load_env_file(tmp_path / "nothing-here") == []


def test_a_value_may_contain_an_equals_sign(tmp_path: Path, clean_environment: None) -> None:
    path = tmp_path / ".env"
    path.write_text("VALUE_FOR_TEST=abc==\n", encoding="utf-8")
    load_env_file(path)
    assert os.environ["VALUE_FOR_TEST"] == "abc=="


# --- a provider that fails must not replace what is published (M4-03) -------------------------


def failed_run(database: Path, *providers: str) -> RunResult:
    outcomes = tuple(FetchOutcome(name, (), "answered HTTP 500") for name in providers)
    ok = (FetchOutcome("fine", ()),)
    return RunResult(database, outcomes + ok, CallLog())


def command(monkeypatch: pytest.MonkeyPatch, result: RunResult) -> list[str]:
    written: list[str] = []

    def fake_publish(*args: Any, **kwargs: Any) -> Published:
        written.append("published")
        return Published(Path("."), {"matches": 1}, 0.0)

    monkeypatch.setattr(publish, "load_env_file", lambda: [])
    monkeypatch.setattr(publish, "build_warehouse", lambda *a, **k: result)
    monkeypatch.setattr(publish, "load_rights", lambda: RIGHTS)
    monkeypatch.setattr(publish, "publish", fake_publish)
    return written


def test_a_failed_provider_stops_the_run_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    written = command(monkeypatch, failed_run(tmp_path / "w.duckdb", "api-football", "other"))
    code = publish.main(["--run", "--require-all-providers", "--out", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 1 and written == []
    assert "provider api-football failed: answered HTTP 500" in captured.err
    assert "provider other failed" in captured.err
    assert "stays as it is" in captured.err and captured.out == ""


def test_with_every_provider_working_the_strict_run_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written = command(monkeypatch, failed_run(tmp_path / "w.duckdb"))
    assert publish.main(["--run", "--require-all-providers", "--out", str(tmp_path)]) == 0
    assert written == ["published"]


def test_without_the_strict_flag_a_failed_provider_still_writes_what_there_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written = command(monkeypatch, failed_run(tmp_path / "w.duckdb", "api-football"))
    assert publish.main(["--run", "--out", str(tmp_path)]) == 0  # as on your own machine
    assert written == ["published"]


# --- the run leaves structured logs (FR-54) -----------------------------------------------------


def events(stderr: str) -> list[dict[str, Any]]:
    """The JSON lines of the log, as the Actions page would show them."""
    return [json.loads(line) for line in stderr.splitlines() if line.startswith("{")]


def test_a_finished_run_logs_one_summary_with_the_counts_the_calls_and_the_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = failed_run(tmp_path / "w.duckdb")
    result.call_log.stats("football-data").network += 9
    command(monkeypatch, result)
    assert publish.main(["--run", "--require-all-providers", "--out", str(tmp_path)]) == 0
    [summary] = [e for e in events(capsys.readouterr().err) if e.get("event") == "run_summary"]
    assert summary["outcome"] == "published" and summary["level"] == "INFO"
    assert summary["record_counts"] == {"matches": 1}
    assert summary["unknown_ratio"] == 0.0
    assert summary["network_calls"] == 9 and summary["failed_providers"] == {}
    assert isinstance(summary["duration_seconds"], float)
    assert summary["time"].endswith("Z")


def test_a_stopped_run_logs_which_providers_failed_and_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    command(monkeypatch, failed_run(tmp_path / "w.duckdb", "api-football"))
    assert publish.main(["--run", "--require-all-providers", "--out", str(tmp_path)]) == 1
    [summary] = [e for e in events(capsys.readouterr().err) if e.get("event") == "run_summary"]
    assert summary["outcome"] == "stopped"
    assert summary["failed_providers"] == {"api-football": "answered HTTP 500"}


def test_a_run_without_the_run_flag_logs_a_summary_with_no_call_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    command(monkeypatch, failed_run(tmp_path / "w.duckdb"))
    assert publish.main(["--out", str(tmp_path)]) == 0  # an existing warehouse: nothing was called
    [summary] = [e for e in events(capsys.readouterr().err) if e.get("event") == "run_summary"]
    assert summary["network_calls"] is None


def test_no_secret_in_the_environment_reaches_the_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    hidden_value = "tok-9d2c7e41ab55"
    monkeypatch.setenv("FOOTBALL_DATA_TOKEN", hidden_value)
    result = failed_run(tmp_path / "w.duckdb", "football-data")

    def leaky_build(*args: Any, **kwargs: Any) -> RunResult:
        logging.getLogger("ubi_ludus.test").warning("provider said no to %s", hidden_value)
        return result

    command(monkeypatch, result)
    monkeypatch.setattr(publish, "build_warehouse", leaky_build)
    publish.main(["--run", "--require-all-providers", "--out", str(tmp_path)])
    captured = capsys.readouterr()
    assert hidden_value not in captured.err + captured.out
    assert "provider said no to ***" in captured.err
