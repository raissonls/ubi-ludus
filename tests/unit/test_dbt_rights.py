"""Rights table to broadcasts: matching, windows, confidence, and the dbt unit tests themselves.

Fixture matches (Série A season 2026 unless noted; dates are Brazil's calendar):

    910001  round 33     1 Nov  Flamengo x Grêmio
    910002  round 34     3 Nov  Palmeiras x Flamengo, 19:30
    910003  round 34     2 Nov  Grêmio x Palmeiras, 23:30 (03:30 UTC the next day)
    910004  round 34     3 Nov  Flamengo x Palmeiras, 00:00 exactly
    910007  final       16 Nov  teams not decided
    920001  Champions League 2026-27, round 3, 4 Nov
    920002  Champions League 2026-27, last 16, 12 Nov
"""

import json
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from dbt_helpers import NOW, TODAY, build, query

from ubi_ludus.pipeline.dbt_runner import DBT_DIR, DbtBuildError, run_dbt
from ubi_ludus.pipeline.export import export_matches
from ubi_ludus.pipeline.rights import RightsData, RightsRule, load_rights
from ubi_ludus.pipeline.validate import validate_file

pytestmark = pytest.mark.dbt

SERIE_A = "brasileirao-serie-a"
CHAMPIONS = "uefa-champions-league"


def rule(
    competition: str,
    scope: str,
    broadcasters: list[str],
    valid_from: str = "2026-01-01",
    valid_to: str = "2026-12-31",
    scope_value: str | None = None,
    season: str = "2026",
) -> RightsRule:
    return RightsRule(
        competition_id=competition,
        season=season,
        scope=scope,  # type: ignore[arg-type]
        scope_value=scope_value,
        broadcasters=tuple(broadcasters),
        valid_from=date.fromisoformat(valid_from),
        valid_to=date.fromisoformat(valid_to),
        source="A made-up source for the tests",
        notes=None,
    )


def rights_with(*rules: RightsRule) -> RightsData:
    return replace(load_rights(), rules=tuple(rules))


RULES = (
    rule(SERIE_A, "all", ["sportv", "premiere"]),
    rule(SERIE_A, "round", ["globo"], "2026-11-01", "2026-11-30", scope_value="34"),
    rule(SERIE_A, "stage", ["band"], scope_value="final"),
    rule(SERIE_A, "team", ["cazetv"], scope_value="gremio"),
    # Starts on 3 Nov: the 23:30 match of 2 Nov is out, the midnight match of 3 Nov is in.
    rule(SERIE_A, "all", ["record"], "2026-11-03", "2026-11-03"),
    # The Champions League rule ends on 5 Nov, so the match of 12 Nov has no rule.
    rule(CHAMPIONS, "all", ["tnt-sports", "hbo-max"], "2026-08-01", "2026-11-05", season="2026-27"),
    # Neither of these covers any fixture match: another season, and a competition without one.
    rule(SERIE_A, "all", ["espn"], season="2025"),
    rule("copa-do-brasil", "all", ["prime-video"]),
)


@pytest.fixture(scope="module")
def database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("rights"), rights=rights_with(*RULES))


@pytest.fixture(scope="module")
def published(
    database: Path, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, list[dict[str, str]]]:
    out = tmp_path_factory.mktemp("out") / "matches.json"
    export_matches(database, out, NOW)
    validate_file(out, "matches")
    matches = json.loads(out.read_text(encoding="utf-8"))["matches"]
    return {m["id"].removeprefix("football-data-"): m["broadcasts"] for m in matches}


def names(broadcasts: list[dict[str, str]]) -> list[str]:
    return [b["broadcaster_id"] for b in broadcasts]


def test_a_rule_for_all_matches_a_round_a_stage_and_a_team_add_up(
    published: dict[str, list[dict[str, str]]],
) -> None:
    assert names(published["910001"]) == ["cazetv", "premiere", "sportv"]  # all + Grêmio plays
    assert names(published["910002"]) == ["globo", "premiere", "record", "sportv"]  # all + round 34
    assert names(published["910007"]) == ["band", "premiere", "sportv"]  # all + the final


def test_a_team_rule_covers_the_team_on_either_side(
    published: dict[str, list[dict[str, str]]],
) -> None:
    assert "cazetv" in names(published["910001"])  # Grêmio away
    assert "cazetv" in names(published["910003"])  # Grêmio home
    assert "cazetv" not in names(published["910002"])  # Palmeiras x Flamengo


def test_a_broadcaster_named_by_two_rules_is_listed_once(
    published: dict[str, list[dict[str, str]]],
) -> None:
    for broadcasts in published.values():
        listed = names(broadcasts)
        assert len(listed) == len(set(listed))


def test_the_validity_window_counts_the_local_day_and_includes_both_ends(
    published: dict[str, list[dict[str, str]]],
) -> None:
    # 23:30 on 2 Nov in Brazil is already 3 Nov in UTC: the rule starting on 3 Nov must not fit.
    assert "record" not in names(published["910003"])
    # Exactly midnight on 3 Nov is the first moment of the rule.
    assert "record" in names(published["910004"])
    assert "record" in names(published["910002"])
    # The last day of the rule is 3 Nov: nothing later is covered.
    assert "record" not in names(published["910007"])


def test_a_rule_for_another_season_or_competition_covers_nothing(
    published: dict[str, list[dict[str, str]]],
) -> None:
    everything = {b for broadcasts in published.values() for b in names(broadcasts)}
    assert "espn" not in everything
    assert "prime-video" not in everything


def test_a_competition_with_a_season_that_crosses_a_year_is_matched_by_its_label(
    published: dict[str, list[dict[str, str]]],
) -> None:
    assert names(published["920001"]) == ["hbo-max", "tnt-sports"]


def test_every_broadcast_carries_a_confidence_and_where_it_came_from(
    published: dict[str, list[dict[str, str]]],
) -> None:
    for match_id, broadcasts in published.items():
        for broadcast in broadcasts:
            if match_id == "920002":
                continue
            assert broadcast["confidence"] == "rule"
            assert broadcast["source"] == "rights_rule"
            assert broadcast["updated_at"] == "2026-11-02T09:00:00Z"


def test_a_match_no_rule_covers_is_unknown_and_names_no_broadcaster(
    published: dict[str, list[dict[str, str]]],
) -> None:
    assert published["920002"] == [
        {
            "broadcaster_id": None,
            "confidence": "unknown",
            "source": "none",
            "updated_at": "2026-11-02T09:00:00Z",
        }
    ]


def test_with_no_rules_at_all_every_match_is_unknown(tmp_path: Path) -> None:
    database = build(tmp_path)
    rows = query(
        database,
        "select id, len(broadcasts), broadcasts[1].broadcaster_id, broadcasts[1].confidence "
        "from matches",
    )
    assert rows
    assert all(count == 1 and who is None and how == "unknown" for _id, count, who, how in rows)


def test_a_rule_naming_a_broadcaster_that_does_not_exist_stops_the_build(tmp_path: Path) -> None:
    with pytest.raises(DbtBuildError) as caught:
        build(tmp_path, rights=rights_with(rule(SERIE_A, "all", ["ghost"])))
    assert any("stg_rights_rule_broadcasters" in name for name in caught.value.failed)


def test_a_rule_for_a_competition_we_do_not_follow_stops_the_build(tmp_path: Path) -> None:
    with pytest.raises(DbtBuildError) as caught:
        build(tmp_path, rights=rights_with(rule("made-up-cup", "all", ["globo"])))
    assert any("stg_rights_rule_broadcasters" in name for name in caught.value.failed)


# --- the dbt unit tests ---------------------------------------------------------------------------


def unit_test_results(work_dir: Path) -> dict[str, str]:
    run_results = json.loads((work_dir / "target" / "run_results.json").read_text(encoding="utf-8"))
    return {
        r["unique_id"].split(".")[-1]: r["status"]
        for r in run_results["results"]
        if r["unique_id"].startswith("unit_test.")
    }


def test_the_dbt_unit_tests_run_with_every_build_and_pass(database: Path) -> None:
    results = unit_test_results(database.parent / "dbt-work")
    assert results == {
        "rule_matching_by_competition_season_and_scope": "pass",
        "rule_validity_window_includes_both_ends": "pass",
        "two_periods_of_one_deal_hand_over_on_the_day_they_change": "pass",
        "a_match_with_no_rule_is_unknown_and_names_no_broadcaster": "pass",
    }


def test_a_change_that_breaks_the_window_is_caught_by_the_unit_tests(tmp_path: Path) -> None:
    """Make the end of the window exclusive in a copy of the project: a unit test must fail."""
    project = tmp_path / "project"
    shutil.copytree(DBT_DIR, project, ignore=shutil.ignore_patterns("target", "logs", "*.duckdb"))
    model = project / "models" / "intermediate" / "int_rule_broadcasts.sql"
    source = model.read_text(encoding="utf-8")
    assert "between r.valid_from and r.valid_to" in source
    model.write_text(
        source.replace(
            "m.kickoff_local_date between r.valid_from and r.valid_to",
            "m.kickoff_local_date >= r.valid_from and m.kickoff_local_date < r.valid_to",
        ),
        encoding="utf-8",
    )
    database = build(tmp_path / "healthy")  # a warehouse with every raw table in place
    with pytest.raises(DbtBuildError) as caught:
        run_dbt(
            database, project_dir=project, work_dir=tmp_path / "broken", run_at=NOW, today=TODAY
        )
    # dbt may stop at the first failure, so either window test can be the one reported.
    window_tests = {
        "rule_validity_window_includes_both_ends",
        "two_periods_of_one_deal_hand_over_on_the_day_they_change",
    }
    assert caught.value.failed
    assert set(caught.value.failed) <= window_tests
