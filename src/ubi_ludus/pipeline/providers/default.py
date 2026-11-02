"""The adapters that ship with the project."""

from __future__ import annotations

from ubi_ludus.pipeline.providers.api_football import ApiFootballAdapter
from ubi_ludus.pipeline.providers.football_data import FootballDataAdapter
from ubi_ludus.pipeline.providers.registry import AdapterRegistry


def default_registry() -> AdapterRegistry:
    """A registry with every adapter written so far."""
    registry = AdapterRegistry()
    registry.register(ApiFootballAdapter.name, ApiFootballAdapter)
    registry.register(FootballDataAdapter.name, FootballDataAdapter)
    return registry
