"""Match-level overrides (FR-11) through the real models: they win over rules and say `confirmed`.

Fixture matches (Série A, all with the rule broadcasters sportv and premiere unless noted):

    910001  Flamengo x Grêmio       overridden: both rule broadcasters removed
    910002  Palmeiras x Flamengo    overridden: cazetv added
    910003  Grêmio x Palmeiras      overridden: replaced by globo
    910004  Flamengo x Palmeiras    overridden: sportv removed
    910007  the final               overridden: band added, then replaced by globo a day later
    920001  Champions League        no rule at all; an override adds hbo-max
    920002  Champions League        no rule at all, no override: unknown
"""

import json
from pathlib import Path

import pytest
from dbt_helpers import NOW, build, override, query, rights_with, rule

from ubi_ludus.pipeline.dbt_runner import DbtBuildError
from ubi_ludus.pipeline.export import export_matches
from ubi_ludus.pipeline.validate import validate_file

pytestmark = pytest.mark.dbt

OVERRIDES = (
    override("football-data-910001", "remove", ["sportv", "premiere"]),
    override("football-data-910002", "add", ["cazetv"]),
    override("football-data-910003", "replace", ["globo"]),
    override("football-data-910004", "remove", ["sportv"]),
    override("football-data-910007", "add", ["band"], "2026-11-01"),
    override("football-data-910007", "replace", ["globo"], "2026-11-02"),
    override("football-data-920001", "add", ["hbo-max"]),
    # This match is long gone: harmless, and only warned about.
    override("football-data-111111", "add", ["globo"]),
)


@pytest.fixture(scope="module")
def database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    rights = rights_with(
        rule("brasileirao-serie-a", "all", ["sportv", "premiere"]), overrides=OVERRIDES
    )
    return build(tmp_path_factory.mktemp("overrides"), rights=rights)


@pytest.fixture(scope="module")
def published(
    database: Path, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, list[tuple[str | None, str, str]]]:
    out = tmp_path_factory.mktemp("out") / "matches.json"
    export_matches(database, out, NOW)
    validate_file(out, "matches")
    matches = json.loads(out.read_text(encoding="utf-8"))["matches"]
    return {
        m["id"].removeprefix("football-data-"): [
            (b["broadcaster_id"], b["confidence"], b["source"]) for b in m["broadcasts"]
        ]
        for m in matches
    }


def test_an_added_broadcaster_is_confirmed_and_the_rule_ones_stay_rules(
    published: dict[str, list[tuple[str | None, str, str]]],
) -> None:
    assert published["910002"] == [
        ("cazetv", "confirmed", "override"),
        ("premiere", "rule", "rights_rule"),
        ("sportv", "rule", "rights_rule"),
    ]


def test_a_replacement_leaves_only_what_it_lists(
    published: dict[str, list[tuple[str | None, str, str]]],
) -> None:
    assert published["910003"] == [("globo", "confirmed", "override")]


def test_a_removed_broadcaster_goes_and_the_others_stay_rules(
    published: dict[str, list[tuple[str | None, str, str]]],
) -> None:
    assert published["910004"] == [("premiere", "rule", "rights_rule")]


def test_removing_every_broadcaster_makes_the_match_unknown_again(
    published: dict[str, list[tuple[str | None, str, str]]],
) -> None:
    assert published["910001"] == [(None, "unknown", "none")]


def test_the_newer_override_has_the_last_word(
    published: dict[str, list[tuple[str | None, str, str]]],
) -> None:
    assert published["910007"] == [("globo", "confirmed", "override")]


def test_an_override_can_give_a_match_with_no_rule_its_broadcaster(
    published: dict[str, list[tuple[str | None, str, str]]],
) -> None:
    assert published["920001"] == [("hbo-max", "confirmed", "override")]
    assert published["920002"] == [(None, "unknown", "none")]


def test_every_confirmed_broadcast_names_a_broadcaster_and_an_override(
    published: dict[str, list[tuple[str | None, str, str]]],
) -> None:
    confirmed = [b for broadcasts in published.values() for b in broadcasts if b[1] == "confirmed"]
    assert confirmed
    assert all(who is not None and source == "override" for who, _, source in confirmed)


def test_an_override_for_a_match_we_no_longer_have_only_warns(database: Path) -> None:
    run_results = json.loads(
        (database.parent / "dbt-work" / "target" / "run_results.json").read_text(encoding="utf-8")
    )
    statuses = {
        r["unique_id"].split(".")[2]: r["status"]
        for r in run_results["results"]
        if r["unique_id"].startswith("test.") and "overrides_for_matches" in r["unique_id"]
    }
    assert statuses == {"overrides_for_matches_we_no_longer_have": "warn"}
    assert query(database, "select count(*) from stg_overrides") == [
        (9,)
    ]  # 910001 lists two broadcasters, so it is two rows


def test_an_override_naming_a_broadcaster_that_does_not_exist_stops_the_build(
    tmp_path: Path,
) -> None:
    rights = rights_with(overrides=(override("football-data-910002", "add", ["ghost"]),))
    with pytest.raises(DbtBuildError) as caught:
        build(tmp_path, rights=rights)
    assert any("stg_overrides" in name for name in caught.value.failed)
