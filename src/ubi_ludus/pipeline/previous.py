"""Download the previously published ``matches.json``, to spot matches whose kickoff moved."""

from __future__ import annotations

import json
import logging
from typing import Any

from ubi_ludus.pipeline.providers.base import ProviderError
from ubi_ludus.pipeline.providers.http import HttpGet, urllib_get
from ubi_ludus.pipeline.validate import validate

logger = logging.getLogger(__name__)


def fetch_previous_matches(url: str, get: HttpGet = urllib_get) -> dict[str, Any] | None:
    """Return the published matches document, or ``None`` if it cannot be used.

    Never raises: without the previous file the run goes on and just cannot flag rescheduled
    matches (FR-05). A file that fails its schema is treated like a missing one, so a damaged
    publication cannot poison the next run.
    """
    try:
        reply = get(url, {})
    except (ProviderError, ValueError) as exc:
        logger.warning("Previous matches.json not downloaded, no reschedule flags: %s", exc)
        return None
    if reply.status != 200:
        logger.warning(
            "Previous matches.json answered HTTP %s, no reschedule flags this run", reply.status
        )
        return None
    try:
        document = json.loads(reply.body)
        validate(document, "matches")
    except ValueError as exc:  # bad JSON, bad encoding, or SchemaValidationError
        logger.warning("Previous matches.json is not usable, no reschedule flags: %s", exc)
        return None
    assert isinstance(document, dict)  # noqa: S101 - narrowing: the schema says it is an object
    return document
