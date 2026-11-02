"""The weekly review report, from a warehouse built on the fixtures."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from dbt_helpers import (
    FIXTURES,
    NOW,
    fixture_registry,
    override,
    rights_with,
    rule,
)

from ubi_ludus.pipeline import review
from ubi_ludus.pipeline.owner import OwnerConfig
from ubi_ludus.pipeline.review import (
    MAX_ROWS,
    FollowedMatch,
    ReviewReport,
    build_review,
    render_markdown,
)
from ubi_ludus.pipeline.run import RunResult, build_warehouse

pytestmark = pytest.mark.dbt

EXPECTED = Path(__file__).resolve().parents[1] / "fixtures" / "review" / "expected_report.md"
OWNER = OwnerConfig(("palmeiras", "flamengo"), (), (), (), ())

# Today is Monday 2 Nov 2026. Fixture matches of Palmeiras or Flamengo still to be played:
#   910002  Série A       Palmeiras x Flamengo           3 Nov 19:30  (override adds CazéTV)
#   920001  Champions     Estudiantes x Palmeiras        4 Nov 17:00  (rule runs to 10 Nov)
#   920002  Champions     Flamengo x Estudiantes        12 Nov 17:00  (past the rule: unknown)
RIGHTS = rights_with(
    rule("brasileirao-serie-a", "all", ["globo", "sportv"], valid_to="2026-12-31"),
    rule("uefa-champions-league", "all", ["hbo-max"], "2026-08-01", "2026-11-10", season="2026-27"),
    # Ended 13 days ago and nothing replaced it.
    rule("copa-do-brasil", "all", ["globo", "prime-video"], valid_to="2026-10-20"),
    # Ended 8 days ago, but another rule for the same competition and season is in force.
    rule(
        "brasileirao-serie-a", "team", ["premiere"], valid_to="2026-10-25", scope_value="palmeiras"
    ),
    # Ended long ago, and one that runs out much later: neither is mentioned.
    rule("la-liga", "all", ["cazetv"], "2025-08-01", "2026-06-30", season="2025-26"),
    rule("premier-league", "all", ["disney-plus"], "2026-08-01", "2027-06-30", season="2026-27"),
    overrides=(override("football-data-910002", "add", ["cazetv"]),),
)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> RunResult:
    work = tmp_path_factory.mktemp("review")
    return build_warehouse(
        work / "warehouse.duckdb",
        now=NOW,
        registry=fixture_registry(),
        teams_path=FIXTURES / "teams.yml",
        rights=RIGHTS,
        work_dir=work / "dbt-work",
    )


@pytest.fixture(scope="module")
def report(built: RunResult) -> ReviewReport:
    return build_review(built.database, owner=OWNER, rights=RIGHTS, now=NOW)


def test_the_sample_data_produces_the_expected_report(report: ReviewReport) -> None:
    assert render_markdown(report) == EXPECTED.read_text(encoding="utf-8")


def test_followed_matches_are_the_upcoming_ones_of_the_owners_teams_with_their_confidence(
    report: ReviewReport,
) -> None:
    assert [(m.match_id, m.confidence) for m in report.followed] == [
        ("football-data-910002", "confirmed"),
        ("football-data-920001", "rule"),
        ("football-data-920002", "unknown"),
    ]
    assert [m.match_id for m in report.unknown] == ["football-data-920002"]
    assert (report.count("confirmed"), report.count("rule"), report.count("unknown")) == (1, 1, 1)


def test_kickoffs_are_shown_in_brazils_time(report: ReviewReport) -> None:
    last = report.unknown[0]
    assert last.kickoff.isoformat() == "2026-11-12T17:00:00-03:00"
    assert (last.home, last.away, last.competition) == (
        "Flamengo",
        "Estudiantes",
        "UEFA Champions League",
    )


def test_matches_that_are_over_or_off_are_not_asked_about(report: ReviewReport) -> None:
    # 910003 is live and 910004 postponed, 910001 is finished: none is something to fix.
    assert {m.match_id for m in report.followed}.isdisjoint(
        {"football-data-910001", "football-data-910003", "football-data-910004"}
    )


def test_a_team_nobody_follows_brings_no_matches(built: RunResult) -> None:
    nobody = OwnerConfig(("estudiantes-de-nada",), (), (), (), ())
    assert build_review(built.database, owner=nobody, rights=RIGHTS, now=NOW).followed == ()


def test_matches_already_played_today_or_before_are_left_out(built: RunResult) -> None:
    later = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)  # 4 Nov: 910002 (3 Nov) is behind us
    ids = [
        m.match_id
        for m in build_review(built.database, owner=OWNER, rights=RIGHTS, now=later).followed
    ]
    assert ids == ["football-data-920001", "football-data-920002"]


def test_rules_ending_soon_are_listed_with_the_days_left(report: ReviewReport) -> None:
    assert [(e.rule.competition_id, e.days_left) for e in report.ending] == [
        ("uefa-champions-league", 8)
    ]


def test_a_rule_that_ended_is_listed_only_if_nothing_replaced_it(report: ReviewReport) -> None:
    assert [(e.rule.competition_id, e.days_left) for e in report.ended_without_successor] == [
        ("copa-do-brasil", -13)
    ]


@pytest.mark.parametrize(
    ("valid_to", "listed_as"),
    [
        ("2026-11-02", "ending"),  # last day is today: still in force, about to end
        ("2026-12-02", "ending"),  # exactly 30 days
        ("2026-12-03", None),  # 31 days
        ("2026-11-01", "ended"),  # yesterday
        ("2026-10-03", "ended"),  # exactly 30 days ago
        ("2026-10-02", None),  # 31 days ago
    ],
)
def test_the_thirty_day_edges(built: RunResult, valid_to: str, listed_as: str | None) -> None:
    rights = rights_with(
        rule("la-liga", "all", ["cazetv"], "2026-01-01", valid_to, season="2026-27")
    )
    found = build_review(built.database, owner=OWNER, rights=rights, now=NOW)
    assert [bool(found.ending), bool(found.ended_without_successor)] == [
        listed_as == "ending",
        listed_as == "ended",
    ]


# --- the Markdown --------------------------------------------------------------------------------


def test_a_quiet_week_says_so_in_every_section() -> None:
    quiet = ReviewReport(NOW, ())
    text = render_markdown(quiet)
    assert text.startswith("# Weekly review: 2 Nov 2026\n")
    assert "None. Every upcoming match of your teams has a broadcaster." in text
    assert "None. Nothing runs out soon." in text
    assert "None. Every competition that lost a rule" in text
    assert "```yaml" not in text  # no override template when there is nothing to fix


def test_a_long_list_is_cut_and_says_how_many_are_left() -> None:
    kickoff = datetime(2026, 11, 3, 19, 30, tzinfo=UTC)
    many = tuple(
        FollowedMatch(f"m-{n}", kickoff, "Série A", "A", "B", "unknown")
        for n in range(MAX_ROWS + 7)
    )
    text = render_markdown(ReviewReport(NOW, many))
    assert text.count("| `m-") == MAX_ROWS
    assert "| ... | 7 more | | |" in text
    assert f"**{MAX_ROWS + 7} unknown**" in text


# --- the command line ----------------------------------------------------------------------------


def test_the_command_writes_the_report_from_an_existing_warehouse(
    built: RunResult,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(review, "load_rights", lambda: RIGHTS)
    monkeypatch.setattr(review, "load_owner", lambda rights: OWNER)
    out = tmp_path / "report.md"

    assert review.main(["--database", str(built.database), "--out", str(out)]) == 0

    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Weekly review:")
    assert "`football-data-920002`" in text
    assert f"Wrote {out}" in capsys.readouterr().out


def test_with_run_the_command_builds_the_warehouse_first(
    built: RunResult, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[Path, Path | None]] = []

    def fake_build(database: Path, *, now: datetime, cache_dir: Path | None = None) -> RunResult:
        calls.append((database, cache_dir))
        return built

    monkeypatch.setattr(review, "build_warehouse", fake_build)
    monkeypatch.setattr(review, "load_rights", lambda: RIGHTS)
    monkeypatch.setattr(review, "load_owner", lambda rights: OWNER)
    cache = tmp_path / "cache"

    review.main(
        [
            "--run",
            "--database",
            str(built.database),
            "--out",
            str(tmp_path / "r.md"),
            "--cache-dir",
            str(cache),
        ]
    )

    assert calls == [(built.database, cache)]


def test_the_default_database_is_the_one_dbt_builds() -> None:
    assert review.DEFAULT_DATABASE.name == "ubi_ludus.duckdb"
    assert review.DEFAULT_DATABASE.parent.name == "target"
