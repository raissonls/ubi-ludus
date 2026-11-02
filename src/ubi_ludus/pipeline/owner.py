"""Load and check ``config/owner.yml`` (PRD FR-41).

The schema checks the file's shape. This module checks it against the rest of the data: the
services and broadcasters exist, the competitions are ones we follow, and, once ``data/teams.yml``
exists, the teams are in it.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from ubi_ludus.pipeline.config import CompetitionConfig, load_competitions
from ubi_ludus.pipeline.rights import RightsData, load_rights
from ubi_ludus.pipeline.validate import SchemaValidationError, validate
from ubi_ludus.pipeline.yamlio import read_yaml

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "owner.yml"


class OwnerConfigError(ValueError):
    """The owner file is unreadable, invalid, or names something that does not exist."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = list(problems)
        lines = "\n".join(f"  - {problem}" for problem in self.problems)
        super().__init__(f"owner.yml has {len(self.problems)} problem(s):\n{lines}")


@dataclass(frozen=True)
class OwnerConfig:
    teams: tuple[str, ...]
    services: tuple[str, ...]
    notable_competitions: tuple[str, ...]
    preferred_broadcasters: tuple[str, ...]
    preferred_kinds: tuple[str, ...]


def load_owner(
    path: Path = DEFAULT_PATH,
    *,
    rights: RightsData | None = None,
    competitions: Sequence[CompetitionConfig] | None = None,
    team_ids: Collection[str] | None = None,
) -> OwnerConfig:
    """Read the file, check its schema, then check every id against the data it points to.

    ``rights`` and ``competitions`` default to the repository's own files. ``team_ids`` is the set
    of ids in ``data/teams.yml``; with ``None`` the teams are not checked (the file does not exist
    yet, issue #77). Raises :class:`OwnerConfigError` listing every problem found.
    """
    try:
        document = read_yaml(path)
    except (OSError, yaml.YAMLError) as exc:
        raise OwnerConfigError([f"cannot read {path.name} ({exc})"]) from exc
    try:
        validate(document, "owner-config")
    except SchemaValidationError as exc:
        raise OwnerConfigError(exc.errors) from exc

    data = rights if rights is not None else load_rights()
    known_competitions = {
        c.id for c in (competitions if competitions is not None else load_competitions())
    }
    owner = OwnerConfig(
        teams=tuple(document["teams"]),
        services=tuple(document["services"]),
        notable_competitions=tuple(document.get("notable_competitions", [])),
        preferred_broadcasters=tuple(document.get("preferred_broadcasters", [])),
        preferred_kinds=tuple(document.get("preferred_kinds", [])),
    )

    problems = _missing("service", owner.services, {s.id for s in data.services})
    problems += _missing(
        "broadcaster", owner.preferred_broadcasters, {b.id for b in data.broadcasters}
    )
    problems += _missing("competition", owner.notable_competitions, known_competitions)
    if team_ids is not None:
        problems += _missing("team", owner.teams, team_ids)
    if problems:
        raise OwnerConfigError(problems)
    return owner


def _missing(kind: str, wanted: Sequence[str], known: Collection[str]) -> list[str]:
    return [f"{kind} '{item}' does not exist" for item in wanted if item not in known]
