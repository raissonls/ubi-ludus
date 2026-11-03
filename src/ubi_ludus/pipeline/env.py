"""Read a local ``.env`` file into the environment, for running the pipeline on your own machine.

The file holds the provider keys (see ``.env.example``). It is git-ignored. In CI the same
variables come from GitHub Secrets, and this module is not used. Values are never printed.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[3] / ".env"


def load_env_file(path: Path = DEFAULT_PATH) -> list[str]:
    """Set the variables of ``path`` that are not already set. Returns the names it set.

    A missing file is fine (nothing is set). Lines that are blank, comments or without ``=`` are
    skipped, and a value may be wrapped in quotes. A variable already in the environment wins, so
    a real secret is never replaced by a file.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    names: list[str] = []
    for line in lines:
        if line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("\"'")
        if name and value and name not in os.environ:
            os.environ[name] = value
            names.append(name)
    return names
