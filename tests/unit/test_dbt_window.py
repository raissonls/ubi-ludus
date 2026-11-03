"""Rolling window (FR-04) and reschedule detection (FR-05), through the real dbt models.

Today is 2 Nov 2026 in Brazil (UTC-3) and the run happens at 09:00 UTC. A competition with a
14-day horizon publishes local dates from 1 Nov through 16 Nov; one with a 1-day horizon
publishes 1 Nov through 3 Nov.

Two dbt builds serve all the tests here, because a build takes seconds: one holds a match for
every edge of the window, the other one for every case of the reschedule flag. Every match has
its own id, so the scenarios do not disturb each other.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from dbt_helpers import NOW, Payloads, build, query

from ubi_ludus.pipeline.export import export_matches
from ubi_ludus.pipeline.validate import validate_file

pytestmark = pytest.mark.dbt

SERIE_A = "brasileirao-serie-a"
COPA = "copa-do-brasil"  # the stand-in for a competition with a 1-day horizon


def fixture_match(match_id: int, kickoff: str, status: str = "TIMED") -> dict[str, Any]:
    return {
        "id": match_id,
        "utcDate": kickoff,
        "status": status,
        "matchday": 1,
        "stage": "REGULAR_SEASON",
        "lastUpdated": "2026-11-02T00:00:00Z",
        "season": {"startDate": "2026-01-01", "endDate": "2026-12-01"},
        "homeTeam": {"id": 1, "name": "CR Flamengo", "shortName": "Flamengo", "tla": "FLA"},
        "awayTeam": {"id": 2, "name": "Grêmio FBPA", "shortName": "Grêmio", "tla": "GRE"},
    }


def only(competitions: dict[str, list[dict[str, Any]]]) -> Callable[[Payloads], None]:
    """A ``change`` for ``build`` that replaces every fixture response with these matches."""

    def replace(payloads: Payloads) -> None:
        payloads.clear()
        for competition_id, matches in competitions.items():
            payloads[competition_id] = {"matches": matches}

    return replace


def published_ids(database: Path) -> set[int]:
    return {
        int(row[0].removeprefix("football-data-"))
        for row in query(database, "select id from matches")
    }


# --- the window ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def windows(tmp_path_factory: pytest.TempPathFactory) -> Path:
    serie_a = [
        fixture_match(101, "2026-11-01T02:59:00Z"),  # 31 Oct 23:59 locally: before yesterday
        fixture_match(102, "2026-11-01T03:00:00Z"),  # 1 Nov 00:00: yesterday starts
        fixture_match(103, "2026-11-02T15:00:00Z"),  # today
        fixture_match(104, "2026-11-03T15:00:00Z"),  # tomorrow
        fixture_match(105, "2026-11-17T02:59:00Z"),  # 16 Nov 23:59: day 14 ends
        fixture_match(106, "2026-11-17T03:00:00Z"),  # 17 Nov 00:00: day 15
    ]
    cup = [
        fixture_match(201, "2026-11-01T02:59:00Z"),  # before yesterday
        fixture_match(202, "2026-11-01T03:00:00Z"),  # yesterday
        fixture_match(203, "2026-11-04T02:59:00Z"),  # 3 Nov 23:59: tomorrow ends
        fixture_match(204, "2026-11-04T03:00:00Z"),  # 4 Nov 00:00: the day after tomorrow
        fixture_match(205, "2026-11-10T15:00:00Z"),  # well beyond
    ]
    change = only({SERIE_A: serie_a, COPA: cup})
    return build(tmp_path_factory.mktemp("windows"), change)


def test_a_14_day_competition_publishes_yesterday_through_14_days_ahead(windows: Path) -> None:
    assert {i for i in published_ids(windows) if i < 200} == {102, 103, 104, 105}


def test_a_short_horizon_competition_publishes_only_until_tomorrow(windows: Path) -> None:
    assert {i for i in published_ids(windows) if i > 200} == {202, 203}


def test_without_a_previous_file_the_run_goes_on_with_no_flags(windows: Path) -> None:
    rows = query(windows, "select status, rescheduled_at from matches")
    assert set(rows) == {("scheduled", None)}


# --- the reschedule flag ------------------------------------------------------------------------


def published(
    match_id: int, kickoff: str, status: str = "scheduled", rescheduled_at: str | None = None
) -> dict[str, Any]:
    """One match as the previous run published it."""
    entry: dict[str, Any] = {
        "id": f"football-data-{match_id}",
        "competition_id": SERIE_A,
        "season": "2026",
        "round": "1",
        "kickoff_utc": kickoff,
        "home_team_id": "flamengo",
        "away_team_id": "gremio",
        "status": status,
        "broadcasts": [],
    }
    if rescheduled_at:
        entry["rescheduled_at"] = rescheduled_at
    return entry


OLD = "2026-11-03T22:30:00Z"
NEW = "2026-11-04T22:30:00Z"


@pytest.fixture(scope="module")
def flags(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The run is at 2 Nov 09:00Z. Each match below is one case, named in the tests."""
    current = [
        fixture_match(1, NEW),  # moved a day
        fixture_match(2, NEW),  # unchanged
        fixture_match(3, NEW),  # flagged 47 h 59 min ago
        fixture_match(4, NEW),  # flagged exactly 48 h ago
        fixture_match(5, NEW),  # flagged an hour ago
        fixture_match(6, "2026-11-05T22:30:00Z"),  # was flagged, moved again
        fixture_match(7, NEW, "POSTPONED"),  # kickoff differs, but the provider says postponed
        fixture_match(8, NEW, "CANCELLED"),
        fixture_match(9, NEW, "POSTPONED"),  # same kickoff as before
        fixture_match(10, NEW),  # not in the previous file at all
    ]
    previous = {
        "schema_version": "1.0",
        "generated_at": "2026-11-01T09:00:00Z",
        "matches": [
            published(1, OLD),
            published(2, NEW),
            published(3, NEW, "rescheduled", "2026-10-31T09:01:00Z"),
            published(4, NEW, "rescheduled", "2026-10-31T09:00:00Z"),
            published(5, NEW, "rescheduled", "2026-11-02T08:00:00Z"),
            published(6, OLD, "rescheduled", "2026-10-31T10:00:00Z"),
            published(7, OLD),
            published(8, OLD),
            published(9, NEW),
            published(99, NEW),  # a match that is no longer fetched: ignored
        ],
    }
    return build(tmp_path_factory.mktemp("flags"), only({SERIE_A: current}), previous)


def statuses(database: Path) -> dict[str, tuple[str, str | None]]:
    rows = query(database, "select id, status, rescheduled_at from matches")
    return {row[0].removeprefix("football-data-"): (row[1], row[2]) for row in rows}


def test_a_changed_kickoff_is_flagged_rescheduled_with_the_time_it_was_noticed(
    flags: Path,
) -> None:
    found = statuses(flags)
    assert found["1"] == ("rescheduled", "2026-11-02T09:00:00Z")
    assert found["2"] == ("scheduled", None)


def test_the_flag_is_carried_from_run_to_run_for_48_hours_then_ends(flags: Path) -> None:
    found = statuses(flags)
    assert found["3"] == ("rescheduled", "2026-10-31T09:01:00Z")  # 47 h 59 min: still flagged
    assert found["4"] == ("scheduled", None)  # exactly 48 h: over
    assert found["5"] == ("rescheduled", "2026-11-02T08:00:00Z")


def test_moving_again_restarts_the_48_hours(flags: Path) -> None:
    assert statuses(flags)["6"] == ("rescheduled", "2026-11-02T09:00:00Z")


def test_postponed_and_cancelled_are_carried_through_and_not_overridden(flags: Path) -> None:
    found = statuses(flags)
    assert found["7"] == ("postponed", None)
    assert found["8"] == ("cancelled", None)
    assert found["9"] == ("postponed", None)


def test_a_match_missing_from_the_previous_file_is_never_flagged(flags: Path) -> None:
    assert statuses(flags)["10"] == ("scheduled", None)
    assert "99" not in statuses(flags)


def test_matches_json_shows_rescheduled_at_only_on_rescheduled_matches(
    flags: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out" / "matches.json"

    export_matches(flags, out, NOW)

    validate_file(out, "matches")
    by_id = {m["id"]: m for m in json.loads(out.read_text(encoding="utf-8"))["matches"]}
    assert by_id["football-data-1"]["status"] == "rescheduled"
    assert by_id["football-data-1"]["rescheduled_at"] == "2026-11-02T09:00:00Z"
    assert "rescheduled_at" not in by_id["football-data-2"]
