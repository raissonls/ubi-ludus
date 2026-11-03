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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ubi_ludus.pipeline import export
from ubi_ludus.pipeline.env import load_env_file
from ubi_ludus.pipeline.rights import RightsData, load_rights
from ubi_ludus.pipeline.run import build_warehouse

DEFAULT_DATABASE = Path(__file__).resolve().parents[3] / "dbt" / "target" / "ubi_ludus.duckdb"
DEFAULT_OUT = Path(__file__).resolve().parents[3] / "site" / "data"
FILES = ("matches", "teams", "competitions", "broadcasters", "status")


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
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    if args.run:
        load_env_file()
        build_warehouse(args.database, now=now, cache_dir=args.cache_dir)
    published = publish(args.database, args.out, rights=load_rights(), now=now)
    summary = ", ".join(f"{n} {name}" for name, n in published.counts.items())
    print(f"Wrote {len(FILES)} files to {args.out}: {summary}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
