"""Is the published data fresh? (PRD FR-51, R6)

The daily pipeline raises its own alarm when a run fails. That cannot catch a run that never
happens: a schedule GitHub delayed, skipped or disabled. This asks the site itself, from outside:
when did the data it serves last come from a successful run? The watchdog workflow runs it a couple
of hours after the pipeline is due and opens an issue when the answer is "too long ago".

``python -m ubi_ludus.pipeline.watchdog --url https://owner.github.io/repo/data/status.json``
prints what it found and exits 0 (fresh) or 1 (stale, unreachable or unreadable).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ubi_ludus.pipeline.providers.base import ProviderError
from ubi_ludus.pipeline.providers.http import HttpGet, urllib_get
from ubi_ludus.pipeline.validate import SchemaValidationError, validate

#: The pipeline runs at 09:00 UTC and takes minutes; the check runs at 11:00. Past this many hours
#: since the last good run, today's run did not happen (or failed). The site's own "data may be
#: old" notice is far more patient (36 hours): it is for visitors, this is for the owner.
DEFAULT_MAX_AGE_HOURS = 5.0


@dataclass(frozen=True)
class Verdict:
    fresh: bool
    message: str


def check(
    url: str,
    now: datetime,
    max_age: timedelta,
    get: HttpGet = urllib_get,
) -> Verdict:
    """Download ``status.json`` and say whether its last successful run is recent enough."""
    try:
        reply = get(url, {})
    except (ProviderError, ValueError) as exc:
        return Verdict(False, f"Could not reach {url}: {exc}")
    if reply.status != 200:
        return Verdict(False, f"{url} answered HTTP {reply.status}")
    try:
        document = json.loads(reply.body)
        validate(document, "status")
        last = datetime.fromisoformat(str(document["last_success_at"]).replace("Z", "+00:00"))
    except (ValueError, KeyError, SchemaValidationError) as exc:
        return Verdict(False, f"The status file at {url} cannot be read: {exc}")
    age = now - last
    if age > max_age:
        hours = age.total_seconds() / 3600
        limit = max_age.total_seconds() / 3600
        return Verdict(
            False,
            f"The published data is {hours:.1f} hours old (last successful run: "
            f"{last:%Y-%m-%d %H:%M} UTC). A run is due every 24 hours, and data more than "
            f"{limit:g} hours old at this time means today's run did not happen.",
        )
    return Verdict(True, f"Fresh: last successful run {last:%Y-%m-%d %H:%M} UTC.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that the published data is fresh.")
    parser.add_argument("--url", required=True, help="the address of the published status.json")
    parser.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS)
    args = parser.parse_args(argv)
    verdict = check(args.url, datetime.now(UTC), timedelta(hours=args.max_age_hours))
    print(verdict.message)  # noqa: T201
    return 0 if verdict.fresh else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
