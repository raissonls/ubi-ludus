"""Load and check ``config/competitions.yml``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from ubi_ludus.pipeline.validate import SchemaValidationError, validate

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "config" / "competitions.yml"
FULL_HORIZON_DAYS = 14

Coverage = Literal["full", "short", "none"]


class ConfigError(ValueError):
    """The config file is unreadable, invalid, or contradicts itself."""


@dataclass(frozen=True)
class SourceConfig:
    provider: str
    provider_id: str
    horizon_days: int


@dataclass(frozen=True)
class CompetitionConfig:
    id: str
    name: str
    country_or_region: str
    type: Literal["league", "cup"]
    sources: tuple[SourceConfig, ...]

    @property
    def horizon_days(self) -> int:
        """Days ahead we publish: the longest horizon of its sources, or 0 with no source."""
        return max((s.horizon_days for s in self.sources), default=0)

    @property
    def coverage(self) -> Coverage:
        """How far ahead we have data: full is 14 days, short is until tomorrow, none is no data."""
        if self.horizon_days >= FULL_HORIZON_DAYS:
            return "full"
        return "short" if self.horizon_days >= 1 else "none"


def load_competitions(path: Path = DEFAULT_PATH) -> list[CompetitionConfig]:
    """Read the YAML file, check it against its schema, and reject contradictions."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Cannot read {path.name}: {exc}") from exc
    try:
        validate(document, "competitions-config")
    except SchemaValidationError as exc:
        raise ConfigError(f"{path.name} does not match its schema.\n{exc}") from exc

    competitions = [
        CompetitionConfig(
            id=item["id"],
            name=item["name"],
            country_or_region=item["country_or_region"],
            type=item["type"],
            sources=tuple(
                SourceConfig(s["provider"], str(s["provider_id"]), s["horizon_days"])
                for s in item["sources"]
            ),
        )
        for item in document["competitions"]
    ]
    _reject_duplicates(path.name, competitions)
    return competitions


def _reject_duplicates(filename: str, competitions: list[CompetitionConfig]) -> None:
    seen_ids: set[str] = set()
    seen_sources: dict[tuple[str, str], str] = {}
    for competition in competitions:
        if competition.id in seen_ids:
            raise ConfigError(f"{filename}: competition id '{competition.id}' appears twice")
        seen_ids.add(competition.id)
        for source in competition.sources:
            key = (source.provider, source.provider_id)
            if key in seen_sources:
                raise ConfigError(
                    f"{filename}: {source.provider} id '{source.provider_id}' is used by both "
                    f"'{seen_sources[key]}' and '{competition.id}'"
                )
            seen_sources[key] = competition.id
