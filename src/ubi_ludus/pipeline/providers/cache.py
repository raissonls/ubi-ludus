"""A file cache for provider responses, so a repeated run does not spend the provider's quota again.

The cache is a directory of small JSON files, one per request, grouped by provider::

    <directory>/<provider>/<sha256 of "<provider>\\n<url>">.json

* **Key:** the provider name and the full request URL (path and query). Keys and tokens travel in
  headers, never in URLs, so no secret reaches a file name or a file.
* **Expiry:** an entry is used while it is younger than ``ttl_seconds`` (one hour by default) and
  ignored after that. Old entries are removed by :meth:`ResponseCache.prune`.
* **What is stored:** only an HTTP 200 whose body is a JSON object without an ``errors`` entry. A
  refusal such as "the free plan cannot see this date" is never replayed. Rate-limit headers are
  not stored either, because they describe the moment of the call, not the replay.
* **Failures:** a missing, damaged or unwritable cache never fails a run. It is just a miss.

Provider data is the provider's, so the directory is git-ignored and never published.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ubi_ludus.pipeline.providers.http import HttpResponse

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 3600.0
CACHE_HIT_HEADER = "x-ubi-ludus-cache"


def is_cacheable(reply: HttpResponse) -> bool:
    """Only a successful answer that carries data: HTTP 200 and no ``errors`` in the body."""
    if reply.status != 200:
        return False
    try:
        body = json.loads(reply.body)
    except ValueError:
        return False
    return isinstance(body, dict) and not body.get("errors")


@dataclass(frozen=True)
class _Entry:
    stored_at: float
    body: str  # base64, so any bytes survive


class ResponseCache:
    def __init__(
        self,
        directory: Path,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._directory = directory
        self._ttl = ttl_seconds
        self._now = now

    def get(self, provider: str, url: str) -> HttpResponse | None:
        """The stored reply if there is a fresh one."""
        entry = self._read(self._path(provider, url))
        if entry is None or self._now() - entry.stored_at >= self._ttl:
            return None
        return HttpResponse(200, {CACHE_HIT_HEADER: "hit"}, base64.b64decode(entry.body))

    def put(self, provider: str, url: str, reply: HttpResponse) -> bool:
        """Store ``reply`` if it is worth replaying. Returns whether it was stored."""
        if not is_cacheable(reply):
            return False
        path = self._path(provider, url)
        entry = {"stored_at": self._now(), "body": base64.b64encode(reply.body).decode("ascii")}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(entry), encoding="utf-8")
            os.replace(temporary, path)  # a reader never sees half a file
        except OSError as exc:
            logger.warning("Could not write the response cache (%s)", exc)
            return False
        return True

    def prune(self) -> int:
        """Delete entries that have expired or cannot be read. Returns how many were removed."""
        removed = 0
        for path in self._directory.glob("*/*.json"):
            entry = self._read(path)
            if entry is None or self._now() - entry.stored_at >= self._ttl:
                try:
                    path.unlink()
                    removed += 1
                except OSError as exc:
                    logger.warning(
                        "Could not remove %s from the response cache (%s)", path.name, exc
                    )
        return removed

    def _path(self, provider: str, url: str) -> Path:
        digest = hashlib.sha256(f"{provider}\n{url}".encode()).hexdigest()
        return self._directory / provider / f"{digest}.json"

    @staticmethod
    def _read(path: Path) -> _Entry | None:
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            return _Entry(float(entry["stored_at"]), str(entry["body"]))
        except (OSError, ValueError, KeyError, TypeError):
            return None
