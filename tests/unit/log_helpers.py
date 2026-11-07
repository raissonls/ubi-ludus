"""Helpers for the tests that run a command which installs the JSON log handler."""

import logging
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def leave_logging_as_found() -> Iterator[None]:
    """``configure_logging`` writes to the stream of the test that called it, which is closed
    afterwards, so take the handler off again. Import this fixture into a test module to use it."""
    root = logging.getLogger()
    before = list(root.handlers)
    level = root.level
    yield
    for handler in [h for h in root.handlers if h not in before]:
        root.removeHandler(handler)
    root.setLevel(level)
