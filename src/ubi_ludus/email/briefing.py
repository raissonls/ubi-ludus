"""What the morning e-mail says, as plain data (PRD FR-40).

Pure: published documents and the owner's preferences in, a :class:`Briefing` out. Nothing here
writes HTML, so every rule (which day, which matches, in what order, what the owner can watch) is
tested without a template. The rules follow the site's, which has the same words for the same
things: free TV and YouTube need no subscription (FR-21), a match with no known broadcaster names
none (FR-13), and data older than 36 hours is said to be old.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from ubi_ludus.pipeline.owner import OwnerConfig
from ubi_ludus.pipeline.validate import validate
from ubi_ludus.pipeline.window import BRAZIL_TZ, today_in_brazil

Access = Literal["yes", "no", "unknown"]
Confidence = Literal["confirmed", "rule"]

#: The files the pipeline publishes and the e-mail reads (the site reads the same ones).
DOCUMENTS = ("matches", "teams", "competitions", "broadcasters", "status")

#: Past this many hours since the last successful run the e-mail says its data may be old.
STALE_AFTER = timedelta(hours=36)
#: Notable matches listed at most; the rest are counted. A Champions League night has eighteen.
MAX_NOTABLE = 6

# Free to everybody (FR-21).
_FREE_KINDS = frozenset({"free_tv", "youtube"})
# A match that is on, or still to come. Postponed and cancelled ones are told in a word.
_WATCHABLE = frozenset({"scheduled", "rescheduled", "live"})
_TOLD = frozenset({"postponed", "cancelled"})
_CONFIDENCE_ORDER = {"confirmed": 0, "rule": 1}


@dataclass(frozen=True)
class Documents:
    """The published files, as read."""

    matches: list[dict[str, Any]]
    teams: dict[str, dict[str, Any]]
    competitions: dict[str, dict[str, Any]]
    broadcasters: dict[str, dict[str, Any]]
    services: dict[str, dict[str, Any]]
    last_success_at: datetime | None


@dataclass(frozen=True)
class BroadcasterLine:
    name: str
    confidence: Confidence
    #: Whether the owner can watch on it: free, or on one of their services.
    accessible: bool


@dataclass(frozen=True)
class BriefingMatch:
    id: str
    home: str | None
    away: str | None
    #: The team colour of a followed side, for the accent bar; never a crest (PRD R5).
    accent: str | None
    competition: str
    round: str | None
    kickoff: datetime  # in Brazil's time
    status: str
    broadcasters: tuple[BroadcasterLine, ...]
    #: None for a match that is not on (postponed, cancelled): there is nothing to watch.
    access: Access | None


@dataclass(frozen=True)
class Briefing:
    day: date
    mine: tuple[BriefingMatch, ...]
    notable: tuple[BriefingMatch, ...]
    #: Notable matches not listed because of MAX_NOTABLE.
    notable_more: int
    #: Set when the data is older than STALE_AFTER: when it was last refreshed.
    stale_since: datetime | None

    @property
    def is_empty(self) -> bool:
        return not self.mine and not self.notable


def load_documents(directory: Path) -> Documents:
    """Read and check the published files in ``directory`` (``site/data``)."""
    raw: dict[str, Any] = {}
    for name in DOCUMENTS:
        document = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        validate(document, name)
        raw[name] = document
    stamp = raw["status"].get("last_success_at")
    return Documents(
        matches=list(raw["matches"]["matches"]),
        teams={t["id"]: t for t in raw["teams"]["teams"]},
        competitions={c["id"]: c for c in raw["competitions"]["competitions"]},
        broadcasters={b["id"]: b for b in raw["broadcasters"]["broadcasters"]},
        services={s["id"]: s for s in raw["broadcasters"]["services"]},
        last_success_at=_moment(stamp) if stamp else None,
    )


def _moment(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def accessible_broadcasters(owner: OwnerConfig, documents: Documents) -> frozenset[str]:
    """The broadcasters the owner can watch: the free ones and those of their services."""
    ticked = set(owner.services)
    found = {
        b["id"]
        for b in documents.broadcasters.values()
        if b["kind"] in _FREE_KINDS or b.get("service_id") in ticked
    }
    for service_id in ticked:
        found.update(documents.services.get(service_id, {}).get("includes_broadcasters", []))
    return frozenset(found)


def build_briefing(documents: Documents, owner: OwnerConfig, now: datetime) -> Briefing:
    """Today's matches of the owner's teams, then the notable ones, for the day of ``now``."""
    today = today_in_brazil(now)
    accessible = accessible_broadcasters(owner, documents)
    followed = {team: position for position, team in enumerate(owner.teams)}

    mine: list[tuple[BriefingMatch, int]] = []
    notable: list[BriefingMatch] = []
    for match in documents.matches:
        kickoff = _moment(match["kickoff_utc"]).astimezone(BRAZIL_TZ)
        if kickoff.date() != today:
            continue
        sides = [match.get("home_team_id"), match.get("away_team_id")]
        ranks = [followed[side] for side in sides if side in followed]
        status = match["status"]
        if ranks and (status in _WATCHABLE or status in _TOLD):
            mine.append(
                (_describe(match, kickoff, documents, owner, accessible, followed), min(ranks))
            )
        elif match["competition_id"] in owner.notable_competitions and status in _WATCHABLE:
            notable.append(_describe(match, kickoff, documents, owner, accessible, followed))

    # By time, as a day's agenda; the team the owner likes best breaks a tie.
    mine.sort(key=lambda pair: (pair[0].kickoff, pair[1], pair[0].id))
    notable.sort(key=lambda item: (item.kickoff, item.id))
    return Briefing(
        day=today,
        mine=tuple(item for item, _ in mine),
        notable=tuple(notable[:MAX_NOTABLE]),
        notable_more=max(0, len(notable) - MAX_NOTABLE),
        stale_since=_stale_since(documents.last_success_at, now),
    )


def _stale_since(last: datetime | None, now: datetime) -> datetime | None:
    if last is None:
        return None  # nothing to compare: the status file is for the site to judge
    return last.astimezone(BRAZIL_TZ) if now - last > STALE_AFTER else None


def _side(team_id: str | None, documents: Documents) -> str | None:
    team = documents.teams.get(team_id) if team_id else None
    return (team.get("short_name") or team["name"]) if team else None


def _describe(
    match: Mapping[str, Any],
    kickoff: datetime,
    documents: Documents,
    owner: OwnerConfig,
    accessible: frozenset[str],
    followed: Mapping[str, int],
) -> BriefingMatch:
    status = str(match["status"])
    lines = _broadcasters(match.get("broadcasts") or [], documents, owner, accessible)
    accent = next(
        (
            documents.teams[side]["colors"]["primary"]
            for side in (match.get("home_team_id"), match.get("away_team_id"))
            if side in followed and side in documents.teams
        ),
        None,
    )
    competition = documents.competitions.get(match["competition_id"])
    return BriefingMatch(
        id=str(match["id"]),
        home=_side(match.get("home_team_id"), documents),
        away=_side(match.get("away_team_id"), documents),
        accent=accent,
        competition=competition["name"] if competition else str(match["competition_id"]),
        round=match.get("round") or None,
        kickoff=kickoff,
        status=status,
        broadcasters=lines,
        access=_access(lines) if status in _WATCHABLE else None,
    )


def _access(lines: Sequence[BroadcasterLine]) -> Access:
    if not lines:
        return "unknown"  # no broadcaster is known, so nothing can be said (FR-13)
    return "yes" if any(line.accessible for line in lines) else "no"


def _broadcasters(
    broadcasts: Sequence[Mapping[str, Any]],
    documents: Documents,
    owner: OwnerConfig,
    accessible: frozenset[str],
) -> tuple[BroadcasterLine, ...]:
    """Named broadcasters: the owner's own first, then their favourites, confirmed ones, name."""
    found: list[tuple[tuple[int, int, int, int, str], BroadcasterLine]] = []
    seen: set[str] = set()
    for broadcast in broadcasts:
        broadcaster_id = broadcast.get("broadcaster_id")
        confidence = broadcast.get("confidence")
        if not broadcaster_id or confidence not in _CONFIDENCE_ORDER or broadcaster_id in seen:
            continue  # "unknown" or no broadcaster gives no line (FR-13)
        seen.add(broadcaster_id)
        broadcaster = documents.broadcasters.get(broadcaster_id)
        name = broadcaster["name"] if broadcaster else str(broadcaster_id)
        kind = broadcaster["kind"] if broadcaster else None
        liked = (
            owner.preferred_broadcasters.index(broadcaster_id)
            if broadcaster_id in owner.preferred_broadcasters
            else len(owner.preferred_broadcasters)
        )
        key = (
            0 if broadcaster_id in accessible else 1,
            liked,
            0 if kind in owner.preferred_kinds else 1,
            _CONFIDENCE_ORDER[confidence],
            name.casefold(),
        )
        line = BroadcasterLine(name, confidence, broadcaster_id in accessible)
        found.append((key, line))
    return tuple(line for _, line in sorted(found, key=lambda pair: pair[0]))
