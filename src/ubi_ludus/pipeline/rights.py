"""Load and check the hand-maintained rights data in ``data/rights/``.

Four files, each checked against its schema in ``schemas/``:

* ``broadcasters.yml``: the channels, apps and YouTube channels that can carry a match;
* ``services.yml``: the subscriptions a visitor can have, and the broadcasters each includes;
* ``rights.yml``: the rights table (PRD FR-10);
* ``overrides.yml``: match-level corrections (PRD FR-11).

A schema looks at one file. What it cannot see is checked here, across the files: every id used
exists, a service and the broadcasters it includes agree, dates are real and in order. A run that
reads bad rights data fails before it publishes anything (FR-02).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml

from ubi_ludus.pipeline.config import CompetitionConfig, load_competitions
from ubi_ludus.pipeline.validate import SchemaValidationError, validate
from ubi_ludus.pipeline.yamlio import read_yaml

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "rights"

Kind = Literal["free_tv", "pay_tv", "ppv", "streaming", "youtube"]
Scope = Literal["all", "round", "stage", "team"]
Action = Literal["add", "replace", "remove"]


class RightsDataError(ValueError):
    """The rights files are unreadable, invalid, or contradict each other.

    ``problems`` lists every one found, each starting with the file it is in.
    """

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = list(problems)
        lines = "\n".join(f"  - {problem}" for problem in self.problems)
        super().__init__(f"The rights data has {len(self.problems)} problem(s):\n{lines}")


@dataclass(frozen=True)
class Broadcaster:
    id: str
    name: str
    kind: Kind
    service_id: str | None
    url: str | None


@dataclass(frozen=True)
class Service:
    id: str
    name: str
    includes_broadcasters: tuple[str, ...]


@dataclass(frozen=True)
class RightsRule:
    competition_id: str
    season: str
    scope: Scope
    scope_value: str | None
    broadcasters: tuple[str, ...]
    valid_from: date
    valid_to: date
    source: str
    notes: str | None


@dataclass(frozen=True)
class Override:
    match_id: str
    action: Action
    broadcasters: tuple[str, ...]
    reason: str
    added_at: date


@dataclass(frozen=True)
class NotCovered:
    """A competition and season we looked into and cannot cover yet."""

    competition_id: str
    season: str
    reason: str
    checked_at: date


@dataclass(frozen=True)
class RightsData:
    broadcasters: tuple[Broadcaster, ...]
    services: tuple[Service, ...]
    rules: tuple[RightsRule, ...]
    overrides: tuple[Override, ...]
    not_covered: tuple[NotCovered, ...] = ()


# (file name, schema name, key that holds the list)
_FILES = (
    ("broadcasters.yml", "broadcasters-config", "broadcasters"),
    ("services.yml", "services-config", "services"),
    ("rights.yml", "rights-config", "rules"),
    ("overrides.yml", "overrides-config", "overrides"),
)


def load_rights(
    directory: Path = DEFAULT_DIR, competitions: Sequence[CompetitionConfig] | None = None
) -> RightsData:
    """Read the four files, check each against its schema, then check them against each other.

    ``competitions`` defaults to ``config/competitions.yml``. Raises :class:`RightsDataError`
    listing every problem found.
    """
    documents, problems = _read_documents(directory)
    if problems:
        raise RightsDataError(problems)

    broadcasters = tuple(
        Broadcaster(b["id"], b["name"], b["kind"], b["service_id"], b["url"])
        for b in documents["broadcasters"]
    )
    services = tuple(
        Service(s["id"], s["name"], tuple(s["includes_broadcasters"]))
        for s in documents["services"]
    )
    rules: list[RightsRule] = []
    overrides: list[Override] = []
    for number, item in enumerate(documents["rules"], start=1):
        parsed = _rule(item)
        if isinstance(parsed, str):
            problems.append(f"rights.yml, rule {number}: {parsed}")
        else:
            rules.append(parsed)
    for number, item in enumerate(documents["overrides"], start=1):
        override = _override(item)
        if isinstance(override, str):
            problems.append(f"overrides.yml, override {number}: {override}")
        else:
            overrides.append(override)

    not_covered: list[NotCovered] = []
    for number, item in enumerate(documents["not_covered"], start=1):
        checked_at = _date(item["checked_at"])
        if checked_at is None:
            problems.append(
                f"rights.yml, not_covered {number}: "
                f"checked_at {item['checked_at']} is not a real date"
            )
        else:
            not_covered.append(
                NotCovered(item["competition_id"], item["season"], item["reason"], checked_at)
            )

    known_competitions = {
        c.id for c in (competitions if competitions is not None else load_competitions())
    }
    problems += _check_catalogue(broadcasters, services)
    problems += _check_rules(rules, {b.id for b in broadcasters}, known_competitions)
    problems += _check_overrides(overrides, {b.id for b in broadcasters})
    problems += _check_not_covered(not_covered, rules, known_competitions)
    if problems:
        raise RightsDataError(problems)
    return RightsData(broadcasters, services, tuple(rules), tuple(overrides), tuple(not_covered))


def _read_documents(directory: Path) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    documents: dict[str, list[dict[str, Any]]] = {}
    problems: list[str] = []
    for filename, schema, key in _FILES:
        try:
            document = read_yaml(directory / filename)
        except (OSError, yaml.YAMLError) as exc:
            problems.append(f"{filename}: cannot read it ({exc})")
            continue
        try:
            validate(document, schema)
        except SchemaValidationError as exc:
            problems += [f"{filename}: {line}" for line in exc.errors]
            continue
        documents[key] = document[key]
        if key == "rules":
            documents["not_covered"] = document.get("not_covered", [])
    return documents, problems


def _date(text: str) -> date | None:
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _rule(item: dict[str, Any]) -> RightsRule | str:
    valid_from, valid_to = _date(item["valid_from"]), _date(item["valid_to"])
    if valid_from is None or valid_to is None:
        return f"{item['valid_from']} to {item['valid_to']} is not a pair of real dates"
    if valid_to < valid_from:
        return f"valid_to {valid_to} is before valid_from {valid_from}"
    return RightsRule(
        competition_id=item["competition_id"],
        season=item["season"],
        scope=item["scope"],
        scope_value=item.get("scope_value"),
        broadcasters=tuple(item["broadcasters"]),
        valid_from=valid_from,
        valid_to=valid_to,
        source=item["source"],
        notes=item.get("notes"),
    )


def _override(item: dict[str, Any]) -> Override | str:
    added_at = _date(item["added_at"])
    if added_at is None:
        return f"added_at {item['added_at']} is not a real date"
    return Override(
        match_id=item["match_id"],
        action=item["action"],
        broadcasters=tuple(item["broadcasters"]),
        reason=item["reason"],
        added_at=added_at,
    )


def _duplicates(ids: Sequence[str]) -> list[str]:
    return sorted({i for i in ids if ids.count(i) > 1})


def _check_catalogue(broadcasters: Sequence[Broadcaster], services: Sequence[Service]) -> list[str]:
    problems: list[str] = []
    problems += [
        f"broadcasters.yml: id '{i}' appears twice"
        for i in _duplicates([b.id for b in broadcasters])
    ]
    problems += [
        f"services.yml: id '{i}' appears twice" for i in _duplicates([s.id for s in services])
    ]

    by_id = {b.id: b for b in broadcasters}
    service_by_id = {s.id: s for s in services}
    for broadcaster in broadcasters:
        if broadcaster.service_id is None:
            listed = sorted(s.id for s in services if broadcaster.id in s.includes_broadcasters)
            if listed:
                problems.append(
                    f"broadcasters.yml: '{broadcaster.id}' is free (service_id null) but "
                    f"services.yml lists it in {', '.join(listed)}"
                )
            continue
        service = service_by_id.get(broadcaster.service_id)
        if service is None:
            problems.append(
                f"broadcasters.yml: '{broadcaster.id}' has service_id '{broadcaster.service_id}', "
                "which is not in services.yml"
            )
        elif broadcaster.id not in service.includes_broadcasters:
            problems.append(
                f"broadcasters.yml: '{broadcaster.id}' needs service '{service.id}', "
                "which does not list it in includes_broadcasters"
            )
    for service in services:
        problems += [
            f"services.yml: '{service.id}' includes '{missing}', which is not in broadcasters.yml"
            for missing in service.includes_broadcasters
            if missing not in by_id
        ]
    return problems


def _check_rules(
    rules: Sequence[RightsRule], broadcaster_ids: set[str], competition_ids: set[str]
) -> list[str]:
    problems: list[str] = []
    seen: set[tuple[str, str, str, str | None, date]] = set()
    for number, rule in enumerate(rules, start=1):
        where = f"rights.yml, rule {number} ({rule.competition_id} {rule.season})"
        if rule.competition_id not in competition_ids:
            problems.append(
                f"{where}: competition '{rule.competition_id}' is not in competitions.yml"
            )
        problems += [
            f"{where}: broadcaster '{b}' is not in broadcasters.yml"
            for b in rule.broadcasters
            if b not in broadcaster_ids
        ]
        key = (rule.competition_id, rule.season, rule.scope, rule.scope_value, rule.valid_from)
        if key in seen:
            problems.append(
                f"{where}: another rule has the same competition, season, scope and valid_from"
            )
        seen.add(key)
    return problems


def _check_overrides(overrides: Sequence[Override], broadcaster_ids: set[str]) -> list[str]:
    return [
        f"overrides.yml, override {number} ({o.match_id}): "
        f"broadcaster '{b}' is not in broadcasters.yml"
        for number, o in enumerate(overrides, start=1)
        for b in o.broadcasters
        if b not in broadcaster_ids
    ]


def _check_not_covered(
    not_covered: Sequence[NotCovered], rules: Sequence[RightsRule], competition_ids: set[str]
) -> list[str]:
    covered = {(r.competition_id, r.season) for r in rules}
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()
    for number, gap in enumerate(not_covered, start=1):
        where = f"rights.yml, not_covered {number} ({gap.competition_id} {gap.season})"
        key = (gap.competition_id, gap.season)
        if gap.competition_id not in competition_ids:
            problems.append(
                f"{where}: competition '{gap.competition_id}' is not in competitions.yml"
            )
        if key in covered:
            problems.append(f"{where}: listed as not covered, but a rule covers it")
        if key in seen:
            problems.append(f"{where}: listed twice")
        seen.add(key)
    return problems
