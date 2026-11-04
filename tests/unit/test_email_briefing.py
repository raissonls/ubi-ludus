"""What the morning e-mail lists (FR-40): which matches, in what order, what the owner can watch."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ubi_ludus.email.briefing import (
    MAX_NOTABLE,
    Documents,
    accessible_broadcasters,
    build_briefing,
    load_documents,
)
from ubi_ludus.pipeline.owner import OwnerConfig
from ubi_ludus.pipeline.validate import SchemaValidationError

# The files the site's own tests use: committed, unlike site/data, which the pipeline makes.
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "site" / "data"
NOW = datetime(2026, 11, 3, 11, 0, tzinfo=UTC)  # 08:00 in Brazil, 3 November


def team(identifier: str, name: str, colour: str = "#006437") -> dict[str, Any]:
    return {
        "id": identifier,
        "name": name,
        "short_name": name,
        "colors": {"primary": colour, "secondary": "#ffffff"},
    }


def broadcaster(
    identifier: str, name: str, kind: str, service: str | None = None
) -> dict[str, Any]:
    return {"id": identifier, "name": name, "kind": kind, "service_id": service, "url": None}


def broadcast(identifier: str | None, confidence: str = "rule") -> dict[str, Any]:
    return {"broadcaster_id": identifier, "confidence": confidence, "source": "x"}


def match(
    identifier: str,
    home: str | None,
    away: str | None,
    kickoff: str = "2026-11-03T22:00:00Z",
    *,
    competition: str = "serie-a",
    status: str = "scheduled",
    broadcasts: list[dict[str, Any]] | None = None,
    round_: str | None = "34",
) -> dict[str, Any]:
    return {
        "id": identifier,
        "competition_id": competition,
        "round": round_,
        "kickoff_utc": kickoff,
        "home_team_id": home,
        "away_team_id": away,
        "status": status,
        "broadcasts": broadcasts if broadcasts is not None else [broadcast("globo")],
    }


def documents(matches: list[dict[str, Any]], last_success_at: datetime | None = None) -> Documents:
    teams = [
        team("palmeiras", "Palmeiras"),
        team("flamengo", "Flamengo", "#c3281e"),
        team("brasil", "Brasil", "#ffdc02"),
        team("chelsea", "Chelsea", "#034694"),
        team("inter", "Inter"),
        team("psg", "PSG"),
    ]
    broadcasters = [
        broadcaster("globo", "TV Globo", "free_tv"),
        broadcaster("cazetv", "CazéTV", "youtube"),
        broadcaster("sportv", "SporTV", "pay_tv"),
        broadcaster("premiere", "Premiere", "ppv", "premiere"),
        broadcaster("espn", "ESPN", "pay_tv"),
        broadcaster("hbo-max", "HBO Max", "streaming", "hbo-max"),
    ]
    return Documents(
        matches=matches,
        teams={t["id"]: t for t in teams},
        competitions={
            "serie-a": {"id": "serie-a", "name": "Série A"},
            "champions": {"id": "champions", "name": "Champions League"},
            "copa": {"id": "copa", "name": "Copa"},
        },
        broadcasters={b["id"]: b for b in broadcasters},
        services={"disney-plus": {"id": "disney-plus", "includes_broadcasters": ["espn"]}},
        last_success_at=last_success_at,
    )


def owner(**changes: Any) -> OwnerConfig:
    base: dict[str, Any] = {
        "teams": ("palmeiras", "brasil"),
        "services": ("disney-plus",),
        "notable_competitions": ("champions",),
        "preferred_broadcasters": (),
        "preferred_kinds": (),
    }
    return OwnerConfig(**{**base, **changes})


def ids(items: Any) -> list[str]:
    return [item.id for item in items]


# --- which day ---------------------------------------------------------------------------------


def test_the_day_is_the_day_in_brazil_not_in_utc() -> None:
    late = match("late", "palmeiras", "flamengo", "2026-11-04T02:30:00Z")  # 23:30 on the 3rd
    next_day = match("next", "palmeiras", "flamengo", "2026-11-04T03:00:00Z")  # 00:00 on the 4th
    early = match("early", "palmeiras", "flamengo", "2026-11-03T02:59:00Z")  # 23:59 on the 2nd
    briefing = build_briefing(documents([late, next_day, early]), owner(), NOW)
    assert ids(briefing.mine) == ["late"]
    assert briefing.day.isoformat() == "2026-11-03"
    assert briefing.mine[0].kickoff.strftime("%H:%M") == "23:30"


def test_a_naive_moment_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_briefing(documents([]), owner(), datetime(2026, 11, 3, 11, 0))  # noqa: DTZ001


# --- which matches, in what order -----------------------------------------------------------


def test_the_owners_teams_come_first_by_time_and_notable_matches_after() -> None:
    matches = [
        match("big", "inter", "psg", "2026-11-03T17:00:00Z", competition="champions"),
        match("night", "palmeiras", "flamengo", "2026-11-03T22:00:00Z"),
        match("noon", "chelsea", "brasil", "2026-11-03T15:00:00Z", competition="copa"),
        match("other", "inter", "psg", "2026-11-03T19:00:00Z", competition="serie-a"),
    ]
    briefing = build_briefing(documents(matches), owner(), NOW)
    assert ids(briefing.mine) == ["noon", "night"]
    assert ids(briefing.notable) == ["big"]  # "other" is neither a team's nor a notable one's


def test_the_team_the_owner_likes_best_breaks_a_tie_in_time() -> None:
    same = "2026-11-03T22:00:00Z"
    matches = [match("second", "brasil", "inter", same), match("first", "palmeiras", "psg", same)]
    assert ids(build_briefing(documents(matches), owner(), NOW).mine) == ["first", "second"]


def test_a_match_of_a_team_in_a_notable_competition_is_listed_once() -> None:
    both = match("both", "palmeiras", "inter", competition="champions")
    briefing = build_briefing(documents([both]), owner(), NOW)
    assert ids(briefing.mine) == ["both"]
    assert briefing.notable == ()


def test_a_long_night_of_notable_matches_is_cut_and_counted() -> None:
    many = [
        match(
            f"n{i}",
            "inter",
            "psg",
            f"2026-11-03T{12 + i // 2:02d}:{30 * (i % 2):02d}:00Z",
            competition="champions",
        )
        for i in range(MAX_NOTABLE + 3)
    ]
    briefing = build_briefing(documents(many), owner(), NOW)
    assert len(briefing.notable) == MAX_NOTABLE
    assert briefing.notable_more == 3
    assert ids(briefing.notable) == [f"n{i}" for i in range(MAX_NOTABLE)]  # the earliest


def test_finished_matches_are_left_out_and_postponed_ones_are_told() -> None:
    matches = [
        match("done", "palmeiras", "flamengo", status="finished"),
        match("later", "brasil", "inter", status="postponed"),
        match("off", "chelsea", "palmeiras", status="cancelled"),
        match("live", "palmeiras", "psg", status="live"),
        match("big-off", "inter", "psg", competition="champions", status="postponed"),
    ]
    briefing = build_briefing(documents(matches), owner(), NOW)
    assert sorted(ids(briefing.mine)) == ["later", "live", "off"]
    assert {m.id: m.access for m in briefing.mine}["later"] is None  # nothing to watch
    assert {m.id: m.access for m in briefing.mine}["live"] == "yes"
    assert briefing.notable == ()  # a notable match that is not on is not worth a line


def test_no_matches_is_an_empty_briefing() -> None:
    briefing = build_briefing(documents([]), owner(), NOW)
    assert briefing.is_empty
    assert (briefing.mine, briefing.notable, briefing.notable_more) == ((), (), 0)


# --- what is said about each match -----------------------------------------------------------


def test_a_match_says_its_teams_competition_round_and_a_team_colour() -> None:
    briefing = build_briefing(documents([match("a", "flamengo", "palmeiras")]), owner(), NOW)
    [item] = briefing.mine
    assert (item.home, item.away) == ("Flamengo", "Palmeiras")
    assert (item.competition, item.round) == ("Série A", "34")
    assert item.accent == "#006437"  # the followed side's colour, not Flamengo's


def test_teams_not_decided_have_no_name() -> None:
    briefing = build_briefing(documents([match("a", "palmeiras", None)]), owner(), NOW)
    assert (briefing.mine[0].home, briefing.mine[0].away) == ("Palmeiras", None)


@pytest.mark.parametrize(
    ("broadcasts", "services", "expected"),
    [
        ([broadcast("globo")], (), "yes"),  # free TV is for everybody
        ([broadcast("cazetv")], (), "yes"),  # so is YouTube
        ([broadcast("sportv")], ("disney-plus",), "no"),
        ([broadcast("espn")], ("disney-plus",), "yes"),  # a service includes it
        ([broadcast("premiere")], ("premiere",), "yes"),  # a broadcaster of a service
        ([broadcast("premiere")], (), "no"),
        ([broadcast("sportv"), broadcast("globo")], (), "yes"),  # one is enough
        ([broadcast(None, "unknown")], (), "unknown"),
        ([], (), "unknown"),
    ],
)
def test_the_marker_says_whether_the_owner_can_watch(
    broadcasts: list[dict[str, Any]], services: tuple[str, ...], expected: str
) -> None:
    given = documents([match("a", "palmeiras", "flamengo", broadcasts=broadcasts)])
    briefing = build_briefing(given, owner(services=services), NOW)
    assert briefing.mine[0].access == expected


def test_the_accessible_set_is_free_ones_and_those_of_the_services() -> None:
    found = accessible_broadcasters(owner(services=("disney-plus", "hbo-max")), documents([]))
    assert found == {"globo", "cazetv", "espn", "hbo-max"}


def test_a_match_with_no_known_broadcaster_names_none() -> None:
    unknown = [broadcast(None, "unknown"), broadcast("globo", "unknown")]
    briefing = build_briefing(
        documents([match("a", "palmeiras", "flamengo", broadcasts=unknown)]), owner(), NOW
    )
    assert briefing.mine[0].broadcasters == ()
    assert briefing.mine[0].access == "unknown"


def test_broadcasters_the_owner_can_watch_come_first_then_favourites_then_confirmed() -> None:
    mixed = [
        broadcast("sportv", "confirmed"),
        broadcast("globo", "rule"),
        broadcast("cazetv", "rule"),
        broadcast("espn", "confirmed"),
        broadcast("globo", "confirmed"),  # a repeat is dropped (the first stays)
    ]
    given = documents([match("a", "palmeiras", "flamengo", broadcasts=mixed)])
    plain = build_briefing(given, owner(), NOW).mine[0].broadcasters
    assert [b.name for b in plain] == ["ESPN", "CazéTV", "TV Globo", "SporTV"]
    assert [b.accessible for b in plain] == [True, True, True, False]
    liked = owner(preferred_broadcasters=("cazetv",))
    assert [b.name for b in build_briefing(given, liked, NOW).mine[0].broadcasters][0] == "CazéTV"


# --- how old the data is ---------------------------------------------------------------------


def test_data_older_than_36_hours_is_said_to_be_old() -> None:
    old = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)  # 49 hours before
    stale = build_briefing(documents([], old), owner(), NOW).stale_since
    assert stale is not None
    assert stale.strftime("%d/%m %H:%M") == "01/11 07:00"  # in Brazil's time
    fresh = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)  # 23 hours before
    assert build_briefing(documents([], fresh), owner(), NOW).stale_since is None
    assert build_briefing(documents([], None), owner(), NOW).stale_since is None


# --- reading the published files -------------------------------------------------------------


def test_the_published_files_are_read_and_the_briefing_builds_from_them() -> None:
    loaded = load_documents(FIXTURES)
    assert loaded.matches and loaded.teams and loaded.broadcasters and loaded.services
    assert loaded.last_success_at is not None
    briefing = build_briefing(loaded, owner(teams=("palmeiras",), services=("globoplay",)), NOW)
    assert ids(briefing.mine) == ["fx-1"]  # Palmeiras x Flamengo, 3 November
    assert all(item.kickoff.date() == briefing.day for item in briefing.mine)


def test_a_file_that_breaks_its_schema_is_refused(tmp_path: Path) -> None:
    for name in ("matches", "teams", "competitions", "broadcasters", "status"):
        (tmp_path / f"{name}.json").write_text(
            (FIXTURES / f"{name}.json").read_text("utf-8"), "utf-8"
        )
    (tmp_path / "status.json").write_text('{"schema_version": "1.0"}', encoding="utf-8")
    with pytest.raises(SchemaValidationError):
        load_documents(tmp_path)
