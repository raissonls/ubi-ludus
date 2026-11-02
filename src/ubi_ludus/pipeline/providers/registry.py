"""Finds the adapter for a provider name taken from the config."""

from __future__ import annotations

from collections.abc import Callable

from ubi_ludus.pipeline.providers.base import ProviderAdapter

AdapterFactory = Callable[[], ProviderAdapter]


class UnknownProviderError(LookupError):
    """The config names a provider that has no registered adapter."""


class AdapterRegistry:
    """Maps provider names to functions that build their adapters.

    A factory (not an instance) is stored so that API keys are only read when the adapter
    is actually used, and tests can register fakes.
    """

    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}

    def register(self, name: str, factory: AdapterFactory) -> None:
        if name in self._factories:
            raise ValueError(f"A provider named '{name}' is already registered")
        self._factories[name] = factory

    def names(self) -> list[str]:
        return sorted(self._factories)

    def __contains__(self, name: object) -> bool:
        return name in self._factories

    def create(self, name: str) -> ProviderAdapter:
        try:
            factory = self._factories[name]
        except KeyError:
            known = ", ".join(self.names()) or "none"
            raise UnknownProviderError(
                f"No adapter registered for provider '{name}'. Registered: {known}"
            ) from None
        adapter = factory()
        if adapter.name != name:
            raise ValueError(f"Adapter registered as '{name}' calls itself '{adapter.name}'")
        return adapter
