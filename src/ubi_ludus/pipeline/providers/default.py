"""The adapters that ship with the project."""

from __future__ import annotations

from ubi_ludus.pipeline.providers.football_data import FootballDataAdapter
from ubi_ludus.pipeline.providers.registry import AdapterRegistry


def default_registry() -> AdapterRegistry:
    """A registry with every adapter written so far. API-Football is added in M1-07."""
    registry = AdapterRegistry()
    registry.register(FootballDataAdapter.name, FootballDataAdapter)
    return registry
