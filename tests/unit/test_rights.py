"""The rights data files: schemas, the checks across files, and the real catalogue."""

import copy
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from ubi_ludus.pipeline.config import CompetitionConfig, SourceConfig, load_competitions
from ubi_ludus.pipeline.rights import (
    DEFAULT_DIR,
    Broadcaster,
    Override,
    RightsDataError,
    RightsRule,
    Service,
    load_rights,
)
from ubi_ludus.pipeline.validate import SchemaValidationError, validate
from ubi_ludus.pipeline.warehouse import connect, load_yaml_file
from ubi_ludus.pipeline.yamlio import read_yaml

COMPETITIONS = [
    CompetitionConfig("serie-a", "Série A", "Brasil", "league", (SourceConfig("p", "1", 14),))
]


def broadcaster(
    id: str, kind: str = "free_tv", service_id: str | None = None, url: str | None = None
) -> dict[str, Any]:
    return {"id": id, "name": id.title(), "kind": kind, "service_id": service_id, "url": url}


def rule(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "competition_id": "serie-a",
        "season": "2026",
        "scope": "all",
        "broadcasters": ["globo"],
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "source": "A made-up source",
    }
    return {**base, **changes}


def override(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "match_id": "football-data-1",
        "action": "add",
        "broadcasters": ["globo"],
        "reason": "A made-up reason",
        "added_at": "2026-11-01",
    }
    return {**base, **changes}


def files(**replace: Any) -> dict[str, dict[str, Any]]:
    """The four documents of a small valid rights directory, with any of them replaced."""
    documents: dict[str, dict[str, Any]] = {
        "broadcasters.yml": {
            "version": 1,
            "broadcasters": [
                broadcaster("globo"),
                broadcaster("sportv", "pay_tv", "pay-tv"),
                broadcaster("hbo", "streaming", "hbo-max"),
            ],
        },
        "services.yml": {
            "version": 1,
            "services": [
                {"id": "pay-tv", "name": "Pay TV", "includes_broadcasters": ["sportv"]},
                {"id": "hbo-max", "name": "HBO Max", "includes_broadcasters": ["hbo", "sportv"]},
            ],
        },
        "rights.yml": {"version": 1, "rules": [rule()]},
        "overrides.yml": {"version": 1, "overrides": [override()]},
    }
    for name, document in replace.items():
        documents[f"{name}.yml"] = document
    return documents


def write(tmp_path: Path, documents: dict[str, dict[str, Any]] | None = None) -> Path:
    for name, document in (documents or files()).items():
        (tmp_path / name).write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    return tmp_path


def problems_of(tmp_path: Path, **replace: Any) -> list[str]:
    write(tmp_path, files(**replace))
    with pytest.raises(RightsDataError) as caught:
        load_rights(tmp_path, COMPETITIONS)
    return caught.value.problems


# --- the real files ------------------------------------------------------------------------------


def test_the_real_rights_files_are_valid_and_agree_with_each_other() -> None:
    data = load_rights()
    assert {b.kind for b in data.broadcasters} == {
        "free_tv",
        "pay_tv",
        "ppv",
        "streaming",
        "youtube",
    }
    assert data.services
    assert data.rules  # curated in M2-04
    assert data.overrides == ()  # the owner writes these as matches need them


def test_every_competition_has_a_rights_rule_or_is_listed_as_not_covered_yet() -> None:
    """M2-04: nothing is silently missing. A gap is written down with its reason."""
    data = load_rights()
    with_a_rule = {r.competition_id for r in data.rules}
    listed_as_gap = {g.competition_id for g in data.not_covered}
    everything = {c.id for c in load_competitions()}
    assert everything <= with_a_rule | listed_as_gap
    assert not with_a_rule & listed_as_gap
    assert all(g.reason for g in data.not_covered)


def test_every_real_rule_names_its_source_and_a_period_with_an_end() -> None:
    for rule_ in load_rights().rules:
        assert rule_.source
        assert rule_.valid_from < rule_.valid_to
        assert rule_.scope == "all"  # broadcasters vary by match, so overrides refine, not rules


def test_every_broadcaster_that_costs_money_is_in_at_least_one_service() -> None:
    data = load_rights()
    included = {b for s in data.services for b in s.includes_broadcasters}
    paid = {b.id for b in data.broadcasters if b.service_id is not None}
    assert paid <= included
    free = {b.id for b in data.broadcasters if b.service_id is None}
    assert not free & included


def test_a_broadcaster_can_be_in_several_services() -> None:
    data = load_rights()
    espn = [s.id for s in data.services if "espn" in s.includes_broadcasters]
    assert len(espn) >= 2


def test_the_real_catalogue_uses_only_links_that_are_https() -> None:
    urls = [b.url for b in load_rights().broadcasters if b.url]
    assert urls
    assert all(url.startswith("https://") for url in urls)


# --- a valid directory ---------------------------------------------------------------------------


def test_a_valid_directory_loads_into_plain_objects(tmp_path: Path) -> None:
    data = load_rights(write(tmp_path), COMPETITIONS)
    assert data.broadcasters[1] == Broadcaster("sportv", "Sportv", "pay_tv", "pay-tv", None)
    assert data.services[0] == Service("pay-tv", "Pay TV", ("sportv",))
    assert data.rules == (
        RightsRule(
            competition_id="serie-a",
            season="2026",
            scope="all",
            scope_value=None,
            broadcasters=("globo",),
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
            source="A made-up source",
            notes=None,
        ),
    )
    assert data.overrides == (
        Override("football-data-1", "add", ("globo",), "A made-up reason", date(2026, 11, 1)),
    )


def test_dates_written_without_quotes_are_understood(tmp_path: Path) -> None:
    write(tmp_path)
    (tmp_path / "rights.yml").write_text(
        "version: 1\nrules:\n"
        "  - competition_id: serie-a\n    season: '2026'\n    scope: team\n"
        "    scope_value: flamengo\n"
        "    broadcasters: [globo]\n    valid_from: 2026-01-28\n    valid_to: 2026-12-31\n"
        "    source: x\n    notes: y\n",
        encoding="utf-8",
    )
    [loaded] = load_rights(tmp_path, COMPETITIONS).rules
    assert (loaded.valid_from, loaded.valid_to, loaded.scope_value, loaded.notes) == (
        date(2026, 1, 28),
        date(2026, 12, 31),
        "flamengo",
        "y",
    )


def test_the_rules_default_competition_list_is_the_real_config(tmp_path: Path) -> None:
    documents = files(rights={"version": 1, "rules": [rule(competition_id="brasileirao-serie-a")]})
    assert {c.id for c in load_competitions()} >= {"brasileirao-serie-a"}
    assert len(load_rights(write(tmp_path, documents)).rules) == 1


# --- checks across the files ---------------------------------------------------------------------


def test_a_broadcaster_pointing_at_a_service_that_does_not_exist(tmp_path: Path) -> None:
    broken = files()["broadcasters.yml"]
    broken["broadcasters"][1]["service_id"] = "nowhere"
    assert problems_of(tmp_path, broadcasters=broken) == [
        "broadcasters.yml: 'sportv' has service_id 'nowhere', which is not in services.yml"
    ]


def test_a_paid_broadcaster_its_service_does_not_list(tmp_path: Path) -> None:
    broken = files()["services.yml"]
    broken["services"][0]["includes_broadcasters"] = []
    assert problems_of(tmp_path, services=broken) == [
        "broadcasters.yml: 'sportv' needs service 'pay-tv', "
        "which does not list it in includes_broadcasters"
    ]


def test_a_free_broadcaster_must_not_sit_in_a_service(tmp_path: Path) -> None:
    broken = files()["services.yml"]
    broken["services"][0]["includes_broadcasters"] = ["sportv", "globo"]
    assert problems_of(tmp_path, services=broken) == [
        "broadcasters.yml: 'globo' is free (service_id null) but services.yml lists it in pay-tv"
    ]


def test_a_service_including_an_unknown_broadcaster(tmp_path: Path) -> None:
    broken = files()["services.yml"]
    broken["services"][0]["includes_broadcasters"] = ["sportv", "ghost"]
    assert problems_of(tmp_path, services=broken) == [
        "services.yml: 'pay-tv' includes 'ghost', which is not in broadcasters.yml"
    ]


def test_ids_that_appear_twice(tmp_path: Path) -> None:
    broadcasters = files()["broadcasters.yml"]
    broadcasters["broadcasters"].append(broadcaster("globo"))
    services = files()["services.yml"]
    services["services"].append(copy.deepcopy(services["services"][0]))
    assert problems_of(tmp_path, broadcasters=broadcasters, services=services) == [
        "broadcasters.yml: id 'globo' appears twice",
        "services.yml: id 'pay-tv' appears twice",
    ]


def test_a_rule_for_a_competition_we_do_not_follow(tmp_path: Path) -> None:
    rules = {"version": 1, "rules": [rule(competition_id="la-liga")]}
    assert problems_of(tmp_path, rights=rules) == [
        "rights.yml, rule 1 (la-liga 2026): competition 'la-liga' is not in competitions.yml"
    ]


def test_a_gap_that_is_also_covered_by_a_rule_is_a_contradiction(tmp_path: Path) -> None:
    document = {
        "version": 1,
        "rules": [rule()],
        "not_covered": [
            {
                "competition_id": "serie-a",
                "season": "2026",
                "reason": "x",
                "checked_at": "2026-11-02",
            }
        ],
    }
    assert problems_of(tmp_path, rights=document) == [
        "rights.yml, not_covered 1 (serie-a 2026): listed as not covered, but a rule covers it"
    ]


def test_a_gap_for_another_season_of_a_covered_competition_is_fine(tmp_path: Path) -> None:
    gap = {"competition_id": "serie-a", "season": "2027", "reason": "x", "checked_at": "2026-11-02"}
    document = {"version": 1, "rules": [rule()], "not_covered": [gap]}
    data = load_rights(write(tmp_path, files(rights=document)), COMPETITIONS)
    assert [(g.competition_id, g.season, g.checked_at) for g in data.not_covered] == [
        ("serie-a", "2027", date(2026, 11, 2))
    ]


def test_gaps_for_unknown_competitions_twice_or_with_a_false_date_are_reported(
    tmp_path: Path,
) -> None:
    gap = {"competition_id": "serie-a", "season": "2027", "reason": "x", "checked_at": "2026-11-02"}
    document = {
        "version": 1,
        "rules": [],
        "not_covered": [
            gap,
            gap,
            {**gap, "competition_id": "la-liga"},
            {**gap, "season": "2028", "checked_at": "2026-02-31"},
        ],
    }
    assert problems_of(tmp_path, rights=document) == [
        "rights.yml, not_covered 4: checked_at 2026-02-31 is not a real date",
        "rights.yml, not_covered 2 (serie-a 2027): listed twice",
        "rights.yml, not_covered 3 (la-liga 2027): "
        "competition 'la-liga' is not in competitions.yml",
    ]


def test_a_rule_or_override_naming_an_unknown_broadcaster(tmp_path: Path) -> None:
    rules = {"version": 1, "rules": [rule(broadcasters=["globo", "ghost"])]}
    overrides = {"version": 1, "overrides": [override(broadcasters=["phantom"])]}
    assert problems_of(tmp_path, rights=rules, overrides=overrides) == [
        "rights.yml, rule 1 (serie-a 2026): broadcaster 'ghost' is not in broadcasters.yml",
        "overrides.yml, override 1 (football-data-1): "
        "broadcaster 'phantom' is not in broadcasters.yml",
    ]


def test_a_rule_that_ends_before_it_starts(tmp_path: Path) -> None:
    rules = {"version": 1, "rules": [rule(valid_from="2026-12-31", valid_to="2026-01-01")]}
    assert problems_of(tmp_path, rights=rules) == [
        "rights.yml, rule 1: valid_to 2026-01-01 is before valid_from 2026-12-31"
    ]


def test_a_date_that_does_not_exist_passes_the_schema_but_not_the_loader(tmp_path: Path) -> None:
    rules = {"version": 1, "rules": [rule(valid_to="2026-02-30")]}
    overrides = {"version": 1, "overrides": [override(added_at="2026-13-01")]}
    assert problems_of(tmp_path, rights=rules, overrides=overrides) == [
        "rights.yml, rule 1: 2026-01-01 to 2026-02-30 is not a pair of real dates",
        "overrides.yml, override 1: added_at 2026-13-01 is not a real date",
    ]


def test_two_rules_that_say_the_same_thing_about_the_same_start(tmp_path: Path) -> None:
    rules = {"version": 1, "rules": [rule(), rule(broadcasters=["sportv"])]}
    assert problems_of(tmp_path, rights=rules) == [
        "rights.yml, rule 2 (serie-a 2026): another rule has the same competition, season, "
        "scope and valid_from"
    ]


def test_rules_for_other_scopes_or_start_dates_are_not_duplicates(tmp_path: Path) -> None:
    rules = {
        "version": 1,
        "rules": [
            rule(),
            rule(valid_from="2026-06-01"),
            rule(scope="team", scope_value="flamengo"),
            rule(scope="team", scope_value="gremio"),
            rule(scope="round", scope_value="33"),
            rule(scope="stage", scope_value="final"),
        ],
    }
    assert len(load_rights(write(tmp_path, files(rights=rules)), COMPETITIONS).rules) == 6


def test_every_problem_is_reported_at_once(tmp_path: Path) -> None:
    rules = {"version": 1, "rules": [rule(competition_id="la-liga", broadcasters=["ghost"])]}
    broken = files()["services.yml"]
    broken["services"][0]["includes_broadcasters"] = []
    found = problems_of(tmp_path, rights=rules, services=broken)
    assert len(found) == 3


# --- files that cannot be read or do not match their schema --------------------------------------


def test_a_missing_file_is_named(tmp_path: Path) -> None:
    write(tmp_path)
    (tmp_path / "services.yml").unlink()
    with pytest.raises(RightsDataError, match=r"services\.yml: cannot read it"):
        load_rights(tmp_path, COMPETITIONS)


def test_a_file_that_is_not_yaml_is_named(tmp_path: Path) -> None:
    write(tmp_path)
    (tmp_path / "rights.yml").write_text("rules: [unclosed", encoding="utf-8")
    with pytest.raises(RightsDataError, match=r"rights\.yml: cannot read it"):
        load_rights(tmp_path, COMPETITIONS)


def test_schema_errors_name_the_file_and_the_place(tmp_path: Path) -> None:
    broken = files()["broadcasters.yml"]
    broken["broadcasters"][0]["kind"] = "terrestrial"
    del broken["broadcasters"][1]["url"]
    write(tmp_path, files(broadcasters=broken))
    with pytest.raises(RightsDataError) as caught:
        load_rights(tmp_path, COMPETITIONS)
    text = "\n".join(caught.value.problems)
    assert "broadcasters.yml: /broadcasters/0/kind" in text
    assert "broadcasters.yml: /broadcasters/1" in text and "url" in text


def test_problems_in_several_files_come_together(tmp_path: Path) -> None:
    write(tmp_path, files(rights={"version": 2, "rules": []}, overrides={"overrides": []}))
    with pytest.raises(RightsDataError) as caught:
        load_rights(tmp_path, COMPETITIONS)
    files_named = {p.split(":")[0] for p in caught.value.problems}
    assert files_named == {"rights.yml", "overrides.yml"}


def test_an_empty_file_is_a_schema_error_not_a_crash(tmp_path: Path) -> None:
    write(tmp_path)
    (tmp_path / "overrides.yml").write_text("", encoding="utf-8")
    with pytest.raises(RightsDataError, match=r"overrides\.yml"):
        load_rights(tmp_path, COMPETITIONS)


# --- the rules of the schemas --------------------------------------------------------------------


def check_rule(**changes: Any) -> None:
    validate({"version": 1, "rules": [rule(**changes)]}, "rights-config")


def check_override(**changes: Any) -> None:
    validate({"version": 1, "overrides": [override(**changes)]}, "overrides-config")


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "all"},
        {"scope": "round", "scope_value": "33"},
        {"scope": "stage", "scope_value": "quarter-finals"},
        {"scope": "team", "scope_value": "flamengo"},
        {"season": "2026-27"},
        {"notes": "Anything"},
    ],
)
def test_rules_that_say_what_they_cover_are_valid(changes: dict[str, Any]) -> None:
    check_rule(**changes)


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"scope": "all", "scope_value": "33"}, "scope_value"),
        ({"scope": "round"}, "scope_value"),
        ({"scope": "round", "scope_value": "final"}, "does not match"),
        ({"scope": "stage"}, "scope_value"),
        ({"scope": "stage", "scope_value": "33"}, "does not match"),
        ({"scope": "stage", "scope_value": "Final"}, "does not match"),
        ({"scope": "team"}, "scope_value"),
        ({"scope": "team", "scope_value": "Flamengo FC"}, "does not match"),
        ({"scope": "league"}, "is not one of"),
        ({"broadcasters": []}, "non-empty|too short"),
        ({"broadcasters": ["globo", "globo"]}, "non-unique"),
        ({"valid_from": "28/01/2026"}, "does not match"),
        ({"valid_to": "2026-12-31T00:00:00Z"}, "does not match"),
        ({"season": "26"}, "does not match"),
        ({"source": ""}, "non-empty|too short"),
        ({"source": "x" * 501}, "too long"),
        ({"competition_id": "Serie A"}, "does not match"),
    ],
)
def test_rules_that_are_unclear_are_refused(changes: dict[str, Any], fragment: str) -> None:
    with pytest.raises(SchemaValidationError, match=fragment):
        check_rule(**changes)


def test_a_rule_without_a_source_is_refused() -> None:
    document: dict[str, Any] = {"version": 1, "rules": [rule()]}
    del document["rules"][0]["source"]
    with pytest.raises(SchemaValidationError, match="source"):
        validate(document, "rights-config")


def test_a_rule_with_a_field_we_do_not_know_is_refused() -> None:
    with pytest.raises(SchemaValidationError, match="priority"):
        check_rule(priority=1)


@pytest.mark.parametrize("action", ["add", "replace", "remove"])
def test_the_three_override_actions_are_valid(action: str) -> None:
    check_override(action=action)


@pytest.mark.parametrize(
    "changes",
    [
        {"action": "swap"},
        {"broadcasters": []},
        {"reason": ""},
        {"added_at": "yesterday"},
        {"match_id": "Football Data 1"},
    ],
)
def test_overrides_that_are_unclear_are_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(SchemaValidationError):
        check_override(**changes)


@pytest.mark.parametrize("field", ["reason", "added_at"])
def test_an_override_without_a_reason_or_a_date_is_refused(field: str) -> None:
    document: dict[str, Any] = {"version": 1, "overrides": [override()]}
    del document["overrides"][0][field]
    with pytest.raises(SchemaValidationError, match=field):
        validate(document, "overrides-config")


# --- reading YAML --------------------------------------------------------------------------------


def test_dates_stay_text_and_other_values_keep_their_types(tmp_path: Path) -> None:
    path = tmp_path / "x.yml"
    path.write_text(
        "day: 2026-11-02\nquoted: '2026-11-02'\nn: 3\nflag: true\nnothing: null\n", "utf-8"
    )
    assert read_yaml(path) == {
        "day": "2026-11-02",
        "quoted": "2026-11-02",
        "n": 3,
        "flag": True,
        "nothing": None,
    }


def test_the_warehouse_can_load_yaml_that_has_dates_in_it(tmp_path: Path) -> None:
    (tmp_path / "rights.yml").write_text(
        "version: 1\nrules:\n  - {competition_id: serie-a, valid_from: 2026-01-28}\n", "utf-8"
    )
    con = connect(tmp_path / "w.duckdb")
    assert load_yaml_file(con, "raw_rules", tmp_path / "rights.yml", key="rules") == 1
    assert con.execute("select valid_from from raw_rules").fetchall() == [
        (date(2026, 1, 28),)
    ]  # DuckDB reads the text as a date


def test_the_default_directory_is_the_one_in_the_repository() -> None:
    assert DEFAULT_DIR.name == "rights"
    assert (DEFAULT_DIR / "broadcasters.yml").is_file()
