"""Write the five published files from a built warehouse (PRD section 8).

``matches.json``, ``teams.json`` and ``competitions.json`` come from the dbt marts,
``broadcasters.json`` from the rights catalogue, and ``status.json`` summarises the run. Every
document is checked against its schema **before anything is written**, so a bad run leaves the
previous files as they were (PRD FR-02).

The site loads these files from a ``data/`` folder next to it. On your machine:
``python -m ubi_ludus.pipeline.publish --run`` fills ``site/data/`` (git-ignored) with live data.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ubi_ludus.logs import configure_logging, event
from ubi_ludus.pipeline import export
from ubi_ludus.pipeline.dbt_runner import DbtBuildError
from ubi_ludus.pipeline.env import load_env_file
from ubi_ludus.pipeline.rights import RightsData, load_rights
from ubi_ludus.pipeline.run import PipelineError, build_warehouse
from ubi_ludus.pipeline.validate import SchemaValidationError

DEFAULT_DATABASE = Path(__file__).resolve().parents[3] / "dbt" / "target" / "ubi_ludus.duckdb"
DEFAULT_OUT = Path(__file__).resolve().parents[3] / "site" / "data"
FILES = ("matches", "teams", "competitions", "broadcasters", "status")

# Not __name__: run with -m, that is "__main__" in the log.
logger = logging.getLogger("ubi_ludus.pipeline.publish")


@dataclass(frozen=True)
class Published:
    out_dir: Path
    counts: dict[str, int]
    unknown_ratio: float | None


def publish(database: Path, out_dir: Path, *, rights: RightsData, now: datetime) -> Published:
    """Build the five documents, validate them all, then write them. Returns what was written."""
    documents = {
        "matches": export.build_matches_document(database, now),
        "teams": export.build_teams_document(database, now),
        "competitions": export.build_competitions_document(database, now),
        "broadcasters": export.build_broadcasters_document(rights, now),
    }
    documents["status"] = export.build_status_document(documents, now)
    for name in FILES:  # only now, with every document valid, is anything written
        export.write_document(documents[name], out_dir / f"{name}.json")
    counts = documents["status"]["record_counts"]
    assert isinstance(counts, dict)  # noqa: S101 - narrowing for the type checker
    ratio = documents["status"]["unknown_ratio"]
    assert ratio is None or isinstance(ratio, float)  # noqa: S101 - narrowing
    return Published(out_dir, dict(counts), ratio)


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m ubi_ludus.pipeline.publish``: write the published files for the site."""
    parser = argparse.ArgumentParser(description="Write the five published JSON files.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--run",
        action="store_true",
        help="run the pipeline first (calls the providers; keys from .env or the environment)",
    )
    parser.add_argument("--cache-dir", type=Path, default=None, help="reuse responses for an hour")
    parser.add_argument(
        "--previous-url",
        default=None,
        help="where the last published matches.json is, to flag matches whose kickoff moved",
    )
    parser.add_argument(
        "--require-all-providers",
        action="store_true",
        help="with --run, write nothing and exit 1 if any provider failed, so that whatever was "
        "published last stays up (the daily workflow uses this)",
    )
    args = parser.parse_args(argv)

    configure_logging()
    started = time.monotonic()
    now = datetime.now(UTC)
    network_calls: int | None = None
    failed: dict[str, str] = {}
    if args.run:
        load_env_file()
        try:
            result = build_warehouse(
                args.database, now=now, cache_dir=args.cache_dir, previous_url=args.previous_url
            )
        except (PipelineError, DbtBuildError) as exc:
            # No provider gave anything, or a dbt test failed: nothing is written, and the log says
            # so in the same event the other endings use.
            print(f"error: {exc}", file=sys.stderr)  # noqa: T201
            event(
                logger,
                f"Run failed, nothing written: {exc}",
                "run_summary",
                outcome="failed",
                error=str(exc),
                duration_seconds=round(time.monotonic() - started, 1),
            )
            return 1
        network_calls = result.call_log.network_calls
        failed = result.failed_providers
        if args.require_all_providers and failed:
            for provider, reason in sorted(failed.items()):
                print(f"error: provider {provider} failed: {reason}", file=sys.stderr)  # noqa: T201
            print(  # noqa: T201
                "Nothing was written: the data published last stays as it is.", file=sys.stderr
            )
            event(
                logger,
                f"Run stopped, nothing written: {len(failed)} provider(s) failed",
                "run_summary",
                outcome="stopped",
                failed_providers=failed,
                network_calls=network_calls,
                duration_seconds=round(time.monotonic() - started, 1),
            )
            return 1
    try:
        published = publish(args.database, args.out, rights=load_rights(), now=now)
    except SchemaValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        event(
            logger,
            "Run failed, a file did not match its schema: nothing was written",
            "run_summary",
            outcome="failed",
            error=str(exc),
            duration_seconds=round(time.monotonic() - started, 1),
        )
        return 1
    summary = ", ".join(f"{n} {name}" for name, n in published.counts.items())
    print(f"Wrote {len(FILES)} files to {args.out}: {summary}")
    event(
        logger,
        f"Run finished, {len(FILES)} files written: {summary}",
        "run_summary",
        outcome="published",
        record_counts=published.counts,
        unknown_ratio=published.unknown_ratio,
        failed_providers=failed,
        network_calls=network_calls,
        duration_seconds=round(time.monotonic() - started, 1),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
