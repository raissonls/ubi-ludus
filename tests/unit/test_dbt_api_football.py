"""API-Football fixtures go through dbt, and a match both providers know is published once.

Every dbt build takes seconds, so the tests that only read share a few builds.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from dbt_helpers import (
    Payloads,
    api_football_fixture,
    api_football_response,
    build,
    query,
)

from ubi_ludus.pipeline.dbt_runner import DbtBuildError
from ubi_ludus.pipeline.providers.base import RawResponse

pytestmark = pytest.mark.dbt

COPA = 73  # Copa do Brasil: served by API-Football only, one-day horizon
SERIE_A = 71  # served by both providers

Change = Callable[[Payloads], list[RawResponse] | None]

STATUSES = {
    "NS": "scheduled",
    "1H": "live",
    "HT": "live",
    "2H": "live",
    "ET": "live",
    "BT": "live",
    "P": "live",
    "LIVE": "live",
    "INT": "live",
    "FT": "finished",
    "AET": "finished",
    "PEN": "finished",
    "AWD": "finished",
    "WO": "finished",
    "PST": "postponed",
    "SUSP": "postponed",
    "ABD": "postponed",
    "CANC": "cancelled",
}
ROUNDS = {
    "Regular Season - 33": "33",
    "Group Stage - 6": "6",
    "Round of 16": "round-of-16",
    "Quarter-finals": "quarter-finals",
    "1st Round": "1st-round",
    "Play-offs": "play-offs",
    "Final": "final",
}


def only(*responses: list[dict[str, Any]]) -> Change:
    """A ``change`` for ``build``: no football-data responses, just these API-Football ones.

    Each argument is the fixture list of one response, the first being the freshest-fetched.
    """

    def change(payloads: Payloads) -> list[RawResponse]:
        payloads.clear()
        return [
            api_football_response(fixtures, fetched_hour=9 - n)
            for n, fixtures in enumerate(responses)
        ]

    return change


def add(*fixtures: dict[str, Any]) -> Change:
    """A ``change`` that keeps the football-data fixtures and adds these API-Football ones."""

    def change(_payloads: Payloads) -> list[RawResponse]:
        return [api_football_response(list(fixtures))]

    return change


def at(hour: int = 15, day: int = 2) -> str:
    """A kickoff in Brazil's time (-03:00), inside the one-day window of the Copa do Brasil."""
    return f"2026-11-{day:02d}T{hour:02d}:00:00-03:00"


def published(database: Path, like: str) -> list[tuple[Any, ...]]:
    sql = f"select id, kickoff_utc, status from matches where id like '{like}' order by id"  # noqa: S608
    return query(database, sql)


# --- from fixture to match ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One build with a fixture per status code and per round label, shared by the reads."""
    fixtures = [
        api_football_fixture(
            1000 + n, COPA, at(), "Flamengo", "Gremio", status=code, round_label=None
        )
        for n, code in enumerate(STATUSES)
    ]
    fixtures += [
        api_football_fixture(2000 + n, COPA, at(), "Palmeiras", "Flamengo", round_label=label)
        for n, label in enumerate(ROUNDS)
    ]
    fixtures += [
        api_football_fixture(3000, 999, at(), "Flamengo", "Gremio"),  # a league we do not follow
        api_football_fixture(3001, COPA, at(), "Flamengo", "Gremio", status="TBD"),
        api_football_fixture(3002, COPA, "2026-11-02T21:30:00-03:00", "Gremio", "Palmeiras"),
        api_football_fixture(3003, COPA, at(), "Estudiantes L.P.", "Palmeiras"),
        api_football_fixture(3004, COPA, at(), "Gremio", "Flamengo", round_label=None),
    ]
    # The same fixture fetched twice; the later fetch says the match was postponed and moved.
    stale = [api_football_fixture(4000, COPA, at(15), "Flamengo", "Gremio")]
    fresh = [api_football_fixture(4000, COPA, at(16), "Flamengo", "Gremio", status="PST")]
    return build(
        tmp_path_factory.mktemp("api-football"),
        only(fresh, fixtures, stale),  # fetched 9h, 8h, 7h
    )


def test_every_status_code_becomes_one_of_ours(database: Path) -> None:
    found = dict(query(database, "select id, status from matches where id like 'api-football-1%'"))
    assert {code: found[f"api-football-{1000 + n}"] for n, code in enumerate(STATUSES)} == STATUSES


def test_the_same_provider_listing_the_same_teams_twice_is_not_merged(database: Path) -> None:
    # 18 fixtures of Flamengo x Gremio at one time: all published, because only a worse-ranked
    # provider's copy of a match is dropped. (The no_match_is_listed_twice test only warns.)
    assert len(published(database, "api-football-1%")) == len(STATUSES)


def test_round_labels_become_matchdays_or_slugs(database: Path) -> None:
    rows = dict(query(database, "select id, round from matches where id like 'api-football-2%'"))
    assert {label: rows[f"api-football-{2000 + n}"] for n, label in enumerate(ROUNDS)} == ROUNDS


def test_a_fixture_without_a_round_has_none(database: Path) -> None:
    assert query(database, "select round from matches where id = 'api-football-3004'") == [(None,)]


def test_a_fixture_becomes_a_match_with_our_ids_utc_kickoff_and_season(database: Path) -> None:
    rows = query(
        database,
        "select id, competition_id, season, kickoff_utc, home_team_id, away_team_id "
        "from matches where id = 'api-football-3002'",
    )
    # 21:30 in Brazil is 00:30 the next day in UTC; the window counts it as 2 Nov.
    assert rows == [
        (
            "api-football-3002",
            "copa-do-brasil",
            "2026",
            "2026-11-03T00:30:00Z",
            "gremio",
            "palmeiras",
        )
    ]


def test_a_league_we_do_not_follow_is_dropped(database: Path) -> None:
    assert (
        query(database, "select 1 from stg_api_football_matches where match_id like '%3000'") == []
    )


def test_a_fixture_without_a_time_yet_waits(database: Path) -> None:
    assert (
        query(database, "select 1 from stg_api_football_matches where match_id like '%3001'") == []
    )


def test_a_club_spelled_differently_is_held_back_and_reported(database: Path) -> None:
    assert query(database, "select 1 from matches where id = 'api-football-3003'") == []
    assert query(database, "select team_name, resolution from int_unmapped_teams") == [
        ("Estudiantes L.P.", "unmapped")
    ]


def test_the_same_fixture_in_two_responses_keeps_the_freshest(database: Path) -> None:
    assert published(database, "api-football-4000") == [
        ("api-football-4000", "2026-11-02T19:00:00Z", "postponed")
    ]


def test_an_unknown_status_code_stops_the_build(tmp_path: Path) -> None:
    fixture = api_football_fixture(1, COPA, at(), "Flamengo", "Gremio", status="XX")
    with pytest.raises(DbtBuildError) as caught:
        build(tmp_path, only([fixture]))
    assert any("accepted_values_stg_api_football_matches" in n for n in caught.value.failed)


# --- a match both providers know ----------------------------------------------------------------
# football-data.org's fixtures (Série A) used below, with UTC kickoffs:
#   910002 Palmeiras x Flamengo, 3 Nov 22:30, scheduled
#   910003 Grêmio x Palmeiras,   3 Nov 02:30, live
#   910004 Flamengo x Palmeiras, 3 Nov 03:00, postponed


def serie_a(fixture_id: int, home: str, away: str, kickoff: str, **kw: Any) -> dict[str, Any]:
    return api_football_fixture(fixture_id, SERIE_A, kickoff, home, away, **kw)


@pytest.fixture(scope="module")
def merged(tmp_path_factory: pytest.TempPathFactory) -> Path:
    fixtures = [
        # Same match as 910002, the clubs spelled the other provider's way.
        serie_a(500, "Palmeiras", "Flamengo", "2026-11-03T19:30:00-03:00"),
        # 40 minutes after 910004: a provider slow to follow a new kickoff. It also says "not
        # started" while football-data.org says postponed.
        serie_a(502, "Flamengo", "Palmeiras", "2026-11-03T00:40:00-03:00"),
        # Exactly 24 hours after 910003: the next round, not the same match.
        serie_a(503, "Gremio", "Palmeiras", "2026-11-03T23:30:00-03:00"),
        # 910002 with the sides swapped, three days on: a return leg.
        serie_a(504, "Flamengo", "Palmeiras", "2026-11-06T19:30:00-03:00"),
        # Same clubs and kickoff as 910002 in another competition.
        api_football_fixture(505, COPA, "2026-11-03T19:30:00-03:00", "Palmeiras", "Flamengo"),
        # A Série A match only API-Football has.
        serie_a(506, "Gremio", "Flamengo", "2026-11-04T19:30:00-03:00"),
    ]
    return build(tmp_path_factory.mktemp("merged"), add(*fixtures))


def test_a_match_both_providers_know_is_published_once_from_football_data(merged: Path) -> None:
    # The providers spell the clubs differently; our aliases make them the same teams.
    assert published(merged, "%-910002") == [
        ("football-data-910002", "2026-11-03T22:30:00Z", "scheduled")
    ]
    assert published(merged, "api-football-500") == []


def test_a_provider_slow_to_follow_a_new_kickoff_still_merges_and_the_better_ranked_one_wins(
    merged: Path,
) -> None:
    assert published(merged, "%-910004") == [
        ("football-data-910004", "2026-11-03T03:00:00Z", "postponed")
    ]
    assert published(merged, "api-football-502") == []


def test_a_kickoff_a_day_or_more_apart_is_another_match(merged: Path) -> None:
    assert len(published(merged, "%-910003")) == 1
    assert len(published(merged, "api-football-503")) == 1


def test_the_return_leg_with_the_sides_swapped_is_another_match(merged: Path) -> None:
    assert len(published(merged, "api-football-504")) == 1


def test_the_same_teams_in_another_competition_are_another_match(merged: Path) -> None:
    assert len(published(merged, "api-football-505")) == 1
    assert len(published(merged, "%-910002")) == 1


def test_a_match_only_api_football_knows_keeps_its_own_id(merged: Path) -> None:
    assert [row[0] for row in published(merged, "api-football-506")] == ["api-football-506"]


def test_ids_stay_unique_and_the_merge_dropped_exactly_the_two_copies(merged: Path) -> None:
    ids = [row[0] for row in query(merged, "select id from matches")]
    assert len(ids) == len(set(ids))
    [(before,)] = query(merged, "select count(*) from int_matches")
    [(after,)] = query(merged, "select count(*) from int_matches_merged")
    assert before - after == 2  # API-Football's 500 and 502


def test_an_unmapped_spelling_never_creates_a_duplicate(tmp_path: Path) -> None:
    def estudiantes(payloads: Payloads) -> list[RawResponse]:
        home = payloads["brasileirao-serie-a"]["matches"][1]["homeTeam"]
        home["name"], home["shortName"] = "Estudiantes de La Plata", "Estudiantes"
        fixture = serie_a(500, "Estudiantes L.P.", "Flamengo", "2026-11-03T19:30:00-03:00")
        return [api_football_response([fixture])]

    database = build(tmp_path, estudiantes)
    # football-data.org's spelling is known, API-Football's is not: only the first is published.
    assert [row[0] for row in published(database, "%-910002")] == ["football-data-910002"]
    assert published(database, "api-football-500") == []
    assert query(database, "select team_name from int_unmapped_teams order by 1") == [
        ("Clube Desconhecido",),
        ("Estudiantes L.P.",),
    ]
