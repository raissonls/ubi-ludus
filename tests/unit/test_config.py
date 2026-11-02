from pathlib import Path
from typing import Any

import pytest
import yaml

from ubi_ludus.pipeline.config import ConfigError, SourceConfig, load_competitions


def competition(competition_id: str, *sources: tuple[str, str | int, int]) -> dict[str, Any]:
    return {
        "id": competition_id,
        "name": "Some competition",
        "country_or_region": "Brasil",
        "type": "league",
        "sources": [
            {"provider": provider, "provider_id": provider_id, "horizon_days": days}
            for provider, provider_id, days in sources
        ],
    }


def write(tmp_path: Path, *competitions: dict[str, Any]) -> Path:
    path = tmp_path / "competitions.yml"
    path.write_text(
        yaml.safe_dump({"version": 1, "competitions": list(competitions)}), encoding="utf-8"
    )
    return path


def test_the_real_config_file_loads() -> None:
    by_id = {c.id: c for c in load_competitions()}
    assert by_id["brasileirao-serie-a"].coverage == "full"
    assert by_id["copa-do-brasil"].coverage == "short"
    assert by_id["eliminatorias-copa-do-mundo"].coverage == "short"  # API-Football since M1-07


def test_provider_ids_are_read_as_text_even_when_written_as_numbers(tmp_path: Path) -> None:
    path = write(tmp_path, competition("copa-do-brasil", ("api-football", 73, 1)))
    [loaded] = load_competitions(path)
    assert loaded.sources == (SourceConfig("api-football", "73", 1),)


def test_coverage_follows_the_longest_horizon(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        competition("both", ("api-football", 1, 1), ("football-data", "X", 14)),
        competition("short", ("api-football", 2, 1)),
        competition("none"),
    )
    assert {c.id: c.coverage for c in load_competitions(path)} == {
        "both": "full",
        "short": "short",
        "none": "none",
    }


def test_a_competition_listed_twice_is_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, competition("same"), competition("same"))
    with pytest.raises(ConfigError, match="'same' appears twice"):
        load_competitions(path)


def test_one_provider_id_cannot_serve_two_competitions(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        competition("first", ("football-data", "BSA", 14)),
        competition("second", ("football-data", "BSA", 14)),
    )
    with pytest.raises(
        ConfigError, match="football-data id 'BSA' is used by both 'first' and 'second'"
    ):
        load_competitions(path)


def test_the_same_id_at_different_providers_is_fine(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        competition("first", ("football-data", 71, 14)),
        competition("second", ("api-football", 71, 1)),
    )
    assert len(load_competitions(path)) == 2


def test_a_malformed_provider_name_is_rejected_by_the_schema(tmp_path: Path) -> None:
    path = write(tmp_path, competition("x", ("Sofa Score", 1, 1)))
    with pytest.raises(ConfigError, match="does not match its schema"):
        load_competitions(path)


@pytest.mark.parametrize("days", [0, 15])
def test_horizon_must_be_between_one_and_fourteen_days(tmp_path: Path, days: int) -> None:
    path = write(tmp_path, competition("x", ("football-data", "BSA", days)))
    with pytest.raises(ConfigError, match="horizon_days"):
        load_competitions(path)


def test_broken_yaml_is_a_config_error(tmp_path: Path) -> None:
    path = tmp_path / "competitions.yml"
    path.write_text("version: 1\ncompetitions: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="Cannot read"):
        load_competitions(path)


def test_a_missing_file_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Cannot read"):
        load_competitions(tmp_path / "nope.yml")
