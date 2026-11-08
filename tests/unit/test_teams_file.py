"""data/teams.yml: the curated teams the pipeline maps provider names to."""

import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from ubi_ludus.pipeline.owner import load_owner
from ubi_ludus.pipeline.run import DEFAULT_TEAMS_PATH
from ubi_ludus.pipeline.validate import SchemaValidationError, validate
from ubi_ludus.pipeline.yamlio import read_yaml

SERIE_A_2026 = {
    "flamengo", "palmeiras", "corinthians", "sao-paulo", "santos", "fluminense", "botafogo",
    "vasco", "gremio", "internacional", "cruzeiro", "atletico-mineiro", "athletico-paranaense",
    "bahia", "vitoria", "bragantino", "mirassol", "coritiba", "chapecoense", "remo",
}  # fmt: skip


def name_key(text: str) -> str:
    """The same normalisation as the dbt macro: lower case, no accents, words only."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", plain.lower()).strip()


@pytest.fixture(scope="module")
def teams() -> list[dict[str, Any]]:
    document = read_yaml(DEFAULT_TEAMS_PATH)
    assert isinstance(document, dict)
    assert list(document) == ["teams"]
    teams: list[dict[str, Any]] = document["teams"]
    return teams


def test_every_team_matches_the_team_schema(teams: list[dict[str, Any]]) -> None:
    for team in teams:
        try:
            validate(team, "team")
        except SchemaValidationError as exc:
            pytest.fail(f"{team.get('id')}: {exc}")


def test_the_file_makes_a_valid_teams_json(teams: list[dict[str, Any]]) -> None:
    validate(
        {"schema_version": "1.0", "generated_at": "2026-11-02T09:00:00Z", "teams": teams}, "teams"
    )


def test_country_codes_are_text_even_norways(teams: list[dict[str, Any]]) -> None:
    """Bare NO is read by YAML as the boolean false, which broke the warehouse load once."""
    assert all(isinstance(team["country"], str) for team in teams)
    assert any(team["country"] == "NO" for team in teams)


def test_ids_are_unique(teams: list[dict[str, Any]]) -> None:
    counts = Counter(team["id"] for team in teams)
    assert [i for i, n in counts.items() if n > 1] == []


def test_no_spelling_belongs_to_two_teams(teams: list[dict[str, Any]]) -> None:
    """Matching would be ambiguous, and the dbt test would stop the run: find it before then."""
    owners: dict[str, set[str]] = {}
    for team in teams:
        for spelling in [team["name"], team["short_name"], *team["aliases"]]:
            owners.setdefault(name_key(spelling), set()).add(team["id"])
    clashes = {key: ids for key, ids in owners.items() if len(ids) > 1}
    assert clashes == {}


def test_an_alias_that_only_repeats_a_name_is_noise(teams: list[dict[str, Any]]) -> None:
    for team in teams:
        own = {name_key(team["name"]), name_key(team["short_name"])}
        redundant = [a for a in team["aliases"] if name_key(a) in own]
        assert redundant == [], team["id"]


def test_the_twenty_serie_a_clubs_are_there_with_the_spellings_of_both_providers(
    teams: list[dict[str, Any]],
) -> None:
    by_id = {team["id"]: team for team in teams}
    assert set(by_id) >= SERIE_A_2026
    spellings = {
        key
        for i in SERIE_A_2026
        for key in (
            name_key(by_id[i]["name"]),
            name_key(by_id[i]["short_name"]),
            *(name_key(a) for a in by_id[i]["aliases"]),
        )
    }
    # Spellings seen in the first live run (2026-11-02) and in API-Football's list of clubs.
    for seen in (
        "CR Flamengo", "SE Palmeiras", "SC Corinthians Paulista", "CA Mineiro", "CA Paranaense",
        "Atletico-MG", "Atletico Paranaense", "Vasco DA Gama", "Gremio", "Sao Paulo", "Vitoria",
        "RB Bragantino", "Chapecoense-SC", "Clube do Remo", "SC Internacional",
    ):  # fmt: skip
        assert name_key(seen) in spellings, seen


def test_the_owners_teams_all_exist(teams: list[dict[str, Any]]) -> None:
    """config/owner.yml names six teams; this is the check that waited for this file."""
    owner = load_owner(team_ids={team["id"] for team in teams})
    assert len(owner.teams) == 6


def test_colours_are_two_hex_values_and_clubs_carry_no_crest_or_logo_fields(
    teams: list[dict[str, Any]],
) -> None:
    for team in teams:
        required = {"id", "name", "short_name", "aliases", "country", "colors"}
        assert required <= set(team) <= required | {"kind", "shirt"}  # no crest, no logo
        assert set(team["colors"]) == {"primary", "secondary"}
        assert team.get("kind", "club") in {"club", "national"}
        assert set(team.get("shirt", team["colors"])) == {"primary", "secondary"}


def test_the_default_path_is_the_one_in_the_repository() -> None:
    assert isinstance(DEFAULT_TEAMS_PATH, Path)
    assert DEFAULT_TEAMS_PATH.is_file()


def test_every_country_with_clubs_has_its_national_team(teams: list[dict[str, Any]]) -> None:
    """The onboarding shows a country as the shirt of its national team: none may be missing."""
    clubs = {t["country"] for t in teams if t.get("kind", "club") == "club"}
    nations = {t["country"] for t in teams if t.get("kind") == "national"}
    assert sorted(clubs - nations) == []


def test_there_is_one_national_team_for_each_country(teams: list[dict[str, Any]]) -> None:
    countries = [t["country"] for t in teams if t.get("kind") == "national"]
    assert len(countries) == len(set(countries))
