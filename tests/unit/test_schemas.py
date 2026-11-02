import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ubi_ludus.pipeline.validate import (
    SchemaValidationError,
    schema_names,
    validate,
    validate_file,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "schemas"
# `common` only holds shared definitions; it is exercised through every other schema.
SCHEMAS = [name for name in schema_names() if name != "common"]
PUBLISHED_FILES = ["matches", "teams", "competitions", "broadcasters", "status"]


def load(kind: str, name: str) -> Any:
    return json.loads((FIXTURES / kind / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", SCHEMAS)
def test_every_schema_has_a_valid_and_an_invalid_example(name: str) -> None:
    assert (FIXTURES / "valid" / f"{name}.json").is_file()
    assert (FIXTURES / "invalid" / f"{name}.json").is_file()


@pytest.mark.parametrize("name", [*SCHEMAS, "common"])
def test_schema_is_itself_valid(name: str) -> None:
    path = Path(__file__).resolve().parents[2] / "schemas" / f"{name}.schema.json"
    Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("name", SCHEMAS)
def test_valid_example_passes(name: str) -> None:
    validate(load("valid", name), name)


@pytest.mark.parametrize("name", SCHEMAS)
def test_invalid_example_fails(name: str) -> None:
    with pytest.raises(SchemaValidationError):
        validate(load("invalid", name), name)


@pytest.mark.parametrize("name", PUBLISHED_FILES)
def test_every_published_file_carries_a_schema_version(name: str) -> None:
    document = load("valid", name)
    assert document["schema_version"] == "1.0"
    del document["schema_version"]
    with pytest.raises(SchemaValidationError, match="schema_version"):
        validate(document, name)


def test_unknown_broadcast_never_names_a_broadcaster() -> None:
    """PRD FR-13: when nothing is known, no broadcaster name is shown."""
    unknown = {
        "broadcaster_id": None,
        "confidence": "unknown",
        "source": "none",
        "updated_at": "2026-11-02T09:05:00Z",
    }
    validate(unknown, "broadcast")
    with pytest.raises(SchemaValidationError):
        validate({**unknown, "broadcaster_id": "sportv"}, "broadcast")


@pytest.mark.parametrize(
    ("confidence", "source"),
    [("confirmed", "rights_rule"), ("rule", "override"), ("rule", "provider")],
)
def test_confidence_must_match_where_the_broadcast_came_from(confidence: str, source: str) -> None:
    broadcast = {
        "broadcaster_id": "sportv",
        "confidence": confidence,
        "source": source,
        "updated_at": "2026-11-02T09:05:00Z",
    }
    with pytest.raises(SchemaValidationError):
        validate(broadcast, "broadcast")


def test_kickoff_must_be_utc() -> None:
    match = load("valid", "match")
    match["kickoff_utc"] = "2026-11-04T19:30:00-03:00"
    with pytest.raises(SchemaValidationError, match="kickoff_utc"):
        validate(match, "match")


def test_rescheduled_at_is_optional_and_must_be_utc() -> None:
    match = load("valid", "match")
    assert "rescheduled_at" not in match  # files from before the field existed stay valid
    match["status"] = "rescheduled"
    match["rescheduled_at"] = "2026-11-02T09:00:00Z"
    validate(match, "match")

    match["rescheduled_at"] = "2026-11-02T06:00:00-03:00"
    with pytest.raises(SchemaValidationError, match="rescheduled_at"):
        validate(match, "match")


def test_match_with_teams_still_to_be_decided_is_allowed() -> None:
    match = load("valid", "match")
    match["home_team_id"] = None
    match["away_team_id"] = None
    match["broadcasts"] = []
    validate(match, "match")


def test_unexpected_fields_are_rejected_so_only_the_minimum_is_published() -> None:
    team = load("valid", "team")
    team["crest_url"] = "https://example.org/crest.png"
    with pytest.raises(SchemaValidationError, match="crest_url"):
        validate(team, "team")


def test_error_reports_where_the_problem_is() -> None:
    document = load("valid", "matches")
    document["matches"][0]["status"] = "paused"
    with pytest.raises(SchemaValidationError) as caught:
        validate(document, "matches")
    assert any(line.startswith("/matches/0/status") for line in caught.value.errors)


def test_all_problems_are_reported_not_just_the_first() -> None:
    document = copy.deepcopy(load("valid", "teams"))
    document["teams"][0]["country"] = "Brazil"
    document["teams"][0]["colors"]["primary"] = "red"
    with pytest.raises(SchemaValidationError) as caught:
        validate(document, "teams")
    assert len(caught.value.errors) == 2


def test_long_error_lists_are_shortened_in_the_message() -> None:
    document = load("valid", "teams")
    document["teams"] = [{"id": "NOT VALID"}] * 5
    with pytest.raises(SchemaValidationError) as caught:
        validate(document, "teams")
    assert len(caught.value.errors) > 10
    assert "more" in str(caught.value)


def test_error_for_a_nullable_field_says_what_is_wrong_with_the_value() -> None:
    status = load("valid", "status")
    status["unknown_ratio"] = 1.5
    with pytest.raises(SchemaValidationError, match="greater than the maximum") as caught:
        validate(status, "status")
    assert "any of the given schemas" not in str(caught.value)


def test_unknown_schema_name_is_a_clear_error() -> None:
    with pytest.raises(KeyError, match="Unknown schema 'nope'"):
        validate({}, "nope")


def test_validate_file_accepts_a_valid_file() -> None:
    validate_file(FIXTURES / "valid" / "matches.json", "matches")


def test_validate_file_rejects_an_invalid_file() -> None:
    with pytest.raises(SchemaValidationError):
        validate_file(FIXTURES / "invalid" / "matches.json", "matches")


def test_validate_file_rejects_broken_json(tmp_path: Path) -> None:
    broken = tmp_path / "matches.json"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(SchemaValidationError, match="not valid JSON"):
        validate_file(broken, "matches")
