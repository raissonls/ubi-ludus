"""Rolling window (FR-04) and reschedule detection (FR-05), through the real dbt models.

Today is 2 Nov 2026 in Brazil (UTC-3) and the run happens at 09:00 UTC. A competition with a
14-day horizon publishes local dates from 1 Nov through 16 Nov; one with a 1-day horizon
publishes 1 Nov through 3 Nov.
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


def only(competition_id: str, matches: list[dict[str, Any]]) -> Callable[[Payloads], None]:
    """A ``change`` for ``build`` that replaces every fixture response with these matches."""

    def replace(payloads: Payloads) -> None:
        payloads.clear()
        payloads[competition_id] = {"matches": matches}

    return replace


def published_ids(database: Path) -> set[str]:
    return {row[0] for row in query(database, "select id from matches")}


def test_a_14_day_competition_publishes_yesterday_through_14_days_ahead(tmp_path: Path) -> None:
    matches = [
        fixture_match(1, "2026-11-01T02:59:00Z"),  # 31 Oct 23:59 locally: before yesterday
        fixture_match(2, "2026-11-01T03:00:00Z"),  # 1 Nov 00:00: yesterday starts
        fixture_match(3, "2026-11-02T15:00:00Z"),  # today
        fixture_match(4, "2026-11-03T15:00:00Z"),  # tomorrow
        fixture_match(5, "2026-11-17T02:59:00Z"),  # 16 Nov 23:59: day 14 ends
        fixture_match(6, "2026-11-17T03:00:00Z"),  # 17 Nov 00:00: day 15
    ]
    database = build(tmp_path, only("brasileirao-serie-a", matches))
    assert published_ids(database) == {f"football-data-{n}" for n in (2, 3, 4, 5)}


def test_a_short_horizon_competition_publishes_only_until_tomorrow(tmp_path: Path) -> None:
    matches = [
        fixture_match(1, "2026-11-01T02:59:00Z"),  # before yesterday
        fixture_match(2, "2026-11-01T03:00:00Z"),  # yesterday
        fixture_match(3, "2026-11-04T02:59:00Z"),  # 3 Nov 23:59: tomorrow ends
        fixture_match(4, "2026-11-04T03:00:00Z"),  # 4 Nov 00:00: the day after tomorrow
        fixture_match(5, "2026-11-10T15:00:00Z"),  # well beyond
    ]
    database = build(tmp_path, only("copa-do-brasil", matches))
    assert published_ids(database) == {f"football-data-{n}" for n in (2, 3)}


def published(
    match_id: int, kickoff: str, status: str = "scheduled", rescheduled_at: str | None = None
) -> dict[str, Any]:
    """One match as the previous run published it."""
    entry: dict[str, Any] = {
        "id": f"football-data-{match_id}",
        "competition_id": "brasileirao-serie-a",
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


def previous_file(*matches: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_at": "2026-11-01T09:00:00Z",
        "matches": list(matches),
    }


def statuses(database: Path) -> dict[str, tuple[str, str | None]]:
    rows = query(database, "select id, status, rescheduled_at from matches")
    return {row[0]: (row[1], row[2]) for row in rows}


def test_a_changed_kickoff_is_flagged_rescheduled_with_the_time_it_was_noticed(
    tmp_path: Path,
) -> None:
    current = [fixture_match(1, "2026-11-04T22:30:00Z"), fixture_match(2, "2026-11-04T22:30:00Z")]
    previous = previous_file(
        published(1, "2026-11-03T22:30:00Z"),  # moved a day
        published(2, "2026-11-04T22:30:00Z"),  # same
    )
    database = build(tmp_path, only("brasileirao-serie-a", current), previous)

    found = statuses(database)
    assert found["football-data-1"] == ("rescheduled", "2026-11-02T09:00:00Z")
    assert found["football-data-2"] == ("scheduled", None)


def test_the_flag_is_carried_from_run_to_run_for_48_hours_then_ends(tmp_path: Path) -> None:
    kickoff = "2026-11-04T22:30:00Z"
    current = [fixture_match(n, kickoff) for n in (1, 2, 3)]
    previous = previous_file(
        # The run is at 2 Nov 09:00Z. Noticed 47 h 59 min ago: still flagged. Exactly 48 h: over.
        published(1, kickoff, "rescheduled", rescheduled_at="2026-10-31T09:01:00Z"),
        published(2, kickoff, "rescheduled", rescheduled_at="2026-10-31T09:00:00Z"),
        # Noticed an hour ago.
        published(3, kickoff, "rescheduled", rescheduled_at="2026-11-02T08:00:00Z"),
    )
    database = build(tmp_path, only("brasileirao-serie-a", current), previous)

    found = statuses(database)
    assert found["football-data-1"] == ("rescheduled", "2026-10-31T09:01:00Z")
    assert found["football-data-2"] == ("scheduled", None)
    assert found["football-data-3"] == ("rescheduled", "2026-11-02T08:00:00Z")


def test_moving_again_restarts_the_48_hours(tmp_path: Path) -> None:
    previous = previous_file(
        published(1, "2026-11-03T22:30:00Z", "rescheduled", rescheduled_at="2026-10-31T10:00:00Z")
    )
    current = [fixture_match(1, "2026-11-05T22:30:00Z")]
    database = build(tmp_path, only("brasileirao-serie-a", current), previous)
    assert statuses(database)["football-data-1"] == ("rescheduled", "2026-11-02T09:00:00Z")


def test_postponed_and_cancelled_are_carried_through_and_not_overridden(tmp_path: Path) -> None:
    current = [
        fixture_match(1, "2026-11-04T22:30:00Z", "POSTPONED"),
        fixture_match(2, "2026-11-04T22:30:00Z", "CANCELLED"),
        fixture_match(3, "2026-11-04T22:30:00Z", "POSTPONED"),
    ]
    previous = previous_file(
        published(1, "2026-11-03T22:30:00Z"),  # kickoff differs, but the provider says postponed
        published(2, "2026-11-03T22:30:00Z"),
        published(3, "2026-11-04T22:30:00Z"),
    )
    database = build(tmp_path, only("brasileirao-serie-a", current), previous)

    found = statuses(database)
    assert found["football-data-1"] == ("postponed", None)
    assert found["football-data-2"] == ("cancelled", None)
    assert found["football-data-3"] == ("postponed", None)


def test_a_match_missing_from_the_previous_file_is_never_flagged(tmp_path: Path) -> None:
    previous = previous_file(published(99, "2026-11-04T22:30:00Z"))
    current = [fixture_match(1, "2026-11-04T22:30:00Z")]
    database = build(tmp_path, only("brasileirao-serie-a", current), previous)
    assert statuses(database)["football-data-1"] == ("scheduled", None)


def test_without_a_previous_file_the_run_goes_on_with_no_flags(tmp_path: Path) -> None:
    current = [fixture_match(1, "2026-11-04T22:30:00Z")]
    database = build(tmp_path, only("brasileirao-serie-a", current))
    assert statuses(database) == {"football-data-1": ("scheduled", None)}


def test_matches_json_shows_rescheduled_at_only_on_rescheduled_matches(tmp_path: Path) -> None:
    current = [fixture_match(1, "2026-11-04T22:30:00Z"), fixture_match(2, "2026-11-04T22:30:00Z")]
    previous = previous_file(
        published(1, "2026-11-03T22:30:00Z"), published(2, "2026-11-04T22:30:00Z")
    )
    database = build(tmp_path, only("brasileirao-serie-a", current), previous)
    out = tmp_path / "out" / "matches.json"

    export_matches(database, out, NOW)

    validate_file(out, "matches")
    by_id = {m["id"]: m for m in json.loads(out.read_text(encoding="utf-8"))["matches"]}
    assert by_id["football-data-1"]["status"] == "rescheduled"
    assert by_id["football-data-1"]["rescheduled_at"] == "2026-11-02T09:00:00Z"
    assert "rescheduled_at" not in by_id["football-data-2"]
