"""A tiny HTTP GET, so adapters can be tested without the network.

Adapters take an ``HttpGet`` function. Production code uses :func:`urllib_get`; tests pass a fake
that returns canned responses.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ubi_ludus.pipeline.providers.base import ProviderError

TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    """Header names in lower case."""
    body: bytes


HttpGet = Callable[[str, Mapping[str, str]], HttpResponse]


def urllib_get(url: str, headers: Mapping[str, str]) -> HttpResponse:
    """GET ``url`` over https. Any HTTP status is returned; only network failures raise."""
    if not url.startswith("https://"):
        raise ValueError("Only https URLs are allowed")
    request = urllib.request.Request(url, headers=dict(headers))  # noqa: S310 - https only, checked above
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return HttpResponse(response.status, _lower(response.headers.items()), response.read())
    except urllib.error.HTTPError as exc:  # a non-2xx status still has headers and a body
        return HttpResponse(exc.code, _lower(exc.headers.items()), exc.read())
    except (urllib.error.URLError, OSError) as exc:
        raise ProviderError(f"Network error: {exc}") from exc


def _lower(items: object) -> dict[str, str]:
    return {str(name).lower(): str(value) for name, value in items}  # type: ignore[attr-defined]
