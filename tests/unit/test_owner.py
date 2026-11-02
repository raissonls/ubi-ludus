"""config/owner.yml: the owner's teams, services and tastes."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from ubi_ludus.pipeline.config import CompetitionConfig, SourceConfig, load_competitions
from ubi_ludus.pipeline.owner import DEFAULT_PATH, OwnerConfig, OwnerConfigError, load_owner
from ubi_ludus.pipeline.rights import load_rights
from ubi_ludus.pipeline.validate import SchemaValidationError, validate

COMPETITIONS = [
    CompetitionConfig("cl", "Champions", "Europa", "cup", (SourceConfig("p", "1", 14),))
]


def write(tmp_path: Path, **fields: Any) -> Path:
    document: dict[str, Any] = {"version": 1, "teams": ["palmeiras"], "services": ["hbo-max"]}
    document.update(fields)
    path = tmp_path / "owner.yml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_the_real_owner_file_is_valid_and_says_what_the_owner_told_us() -> None:
    owner = load_owner()
    assert owner.teams == (
        "palmeiras",
        "brasil",
        "real-madrid",
        "barcelona",
        "chelsea",
        "manchester-city",
    )
    assert set(owner.services) == {"disney-plus", "globoplay", "premiere", "hbo-max"}
    assert owner.notable_competitions == ("uefa-champions-league",)
    assert owner.preferred_broadcasters == ("cazetv",)
    assert owner.preferred_kinds == ("youtube",)


def test_the_real_owner_file_holds_no_contact_details() -> None:
    """FR-41: the e-mail address and the credentials are GitHub Secrets, never in the repository."""
    lines = DEFAULT_PATH.read_text(encoding="utf-8").splitlines()
    values = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
    assert "@" not in values  # no e-mail address
    assert set(yaml.safe_load("\n".join(lines))) == {
        "version",
        "teams",
        "services",
        "notable_competitions",
        "preferred_broadcasters",
        "preferred_kinds",
    }


def test_what_the_owner_has_is_watchable_through_the_catalogue() -> None:
    """The owner's services between them include ESPN, Premiere and HBO Max's TNT Sports."""
    rights = load_rights()
    owner = load_owner(rights=rights)
    included = {
        b for s in rights.services if s.id in owner.services for b in s.includes_broadcasters
    }
    assert {"espn", "premiere", "globoplay", "hbo-max", "tnt-sports"} <= included
    assert "sportv" not in included  # pay TV was not named


def test_only_the_teams_and_the_services_are_needed(tmp_path: Path) -> None:
    owner = load_owner(write(tmp_path), competitions=COMPETITIONS)
    assert owner == OwnerConfig(("palmeiras",), ("hbo-max",), (), (), ())


def test_teams_are_not_checked_until_the_teams_file_exists(tmp_path: Path) -> None:
    path = write(tmp_path, teams=["a-team-nobody-has-heard-of"])
    assert load_owner(path, competitions=COMPETITIONS).teams == ("a-team-nobody-has-heard-of",)


def test_teams_are_checked_against_the_teams_file_when_there_is_one(tmp_path: Path) -> None:
    path = write(tmp_path, teams=["palmeiras", "palmeiras-b"])
    with pytest.raises(OwnerConfigError) as caught:
        load_owner(path, competitions=COMPETITIONS, team_ids={"palmeiras"})
    assert caught.value.problems == ["team 'palmeiras-b' does not exist"]


def test_everything_the_owner_names_must_exist(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        services=["hbo-max", "netflix"],
        notable_competitions=["cl", "la-liga-2"],
        preferred_broadcasters=["cazetv", "ghost"],
    )
    with pytest.raises(OwnerConfigError) as caught:
        load_owner(path, competitions=COMPETITIONS)
    assert caught.value.problems == [
        "service 'netflix' does not exist",
        "broadcaster 'ghost' does not exist",
        "competition 'la-liga-2' does not exist",
    ]
    assert "3 problem(s)" in str(caught.value)


def test_the_default_competitions_are_the_real_ones(tmp_path: Path) -> None:
    path = write(tmp_path, notable_competitions=["uefa-champions-league"])
    assert "uefa-champions-league" in {c.id for c in load_competitions()}
    assert load_owner(path).notable_competitions == ("uefa-champions-league",)


def test_a_missing_file_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(OwnerConfigError, match="cannot read owner.yml"):
        load_owner(tmp_path / "owner.yml")


def test_a_file_that_is_not_yaml_is_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "owner.yml"
    path.write_text("teams: [unclosed", encoding="utf-8")
    with pytest.raises(OwnerConfigError, match="cannot read owner.yml"):
        load_owner(path)


def test_schema_errors_say_where_the_problem_is(tmp_path: Path) -> None:
    path = write(tmp_path, teams=[], services=["Pay TV"])
    with pytest.raises(OwnerConfigError) as caught:
        load_owner(path, competitions=COMPETITIONS)
    text = "\n".join(caught.value.problems)
    assert "/teams" in text
    assert "/services/0" in text


def check(**fields: Any) -> None:
    document: dict[str, Any] = {"version": 1, "teams": ["palmeiras"], "services": []}
    document.update(fields)
    validate(document, "owner-config")


def test_a_person_can_follow_teams_and_have_no_service_at_all() -> None:
    check(services=[])


@pytest.mark.parametrize(
    "fields",
    [
        {"teams": []},
        {"teams": ["palmeiras", "palmeiras"]},
        {"teams": ["Palmeiras FC"]},
        {"preferred_kinds": ["radio"]},
        {"email": "someone@example.org"},
        {"smtp_password": "x"},
    ],
)
def test_unclear_or_secret_fields_are_refused(fields: dict[str, Any]) -> None:
    with pytest.raises(SchemaValidationError):
        check(**fields)
