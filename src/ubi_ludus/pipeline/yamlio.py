"""Read hand-edited YAML the way our schemas expect it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_TIMESTAMP = "tag:yaml.org,2002:timestamp"


class _TextDatesLoader(yaml.SafeLoader):
    """A safe loader that leaves ``2026-11-02`` as text.

    Plain YAML turns an unquoted date into a date object, which JSON (and so our schemas and the
    warehouse) cannot hold. Keeping it as text lets the owner write dates without quotes.
    """


_TextDatesLoader.yaml_implicit_resolvers = {
    first_character: [(tag, pattern) for tag, pattern in resolvers if tag != _TIMESTAMP]
    for first_character, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def read_yaml(path: Path) -> Any:
    """The contents of a YAML file, with dates as text. Raises ``OSError`` or ``yaml.YAMLError``."""
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_TextDatesLoader)  # noqa: S506 - a SafeLoader
