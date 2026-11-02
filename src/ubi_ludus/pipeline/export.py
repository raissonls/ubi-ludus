"""Write published files from the dbt marts, checking them against the schemas first."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from ubi_ludus.pipeline.validate import validate

SCHEMA_VERSION = "1.0"


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_teams_document(database: Path, generated_at: datetime) -> dict[str, object]:
    """Read the ``teams`` mart and shape it like ``teams.json``. Raises if it breaks the schema."""
    # Same settings as dbt's own connection: DuckDB refuses to mix read-only and read-write
    # connections to one file inside one process.
    con = duckdb.connect(str(database))
    try:
        cursor = con.execute("select * from teams order by id")
        columns = [column[0] for column in cursor.description]
        teams = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()
    document: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _timestamp(generated_at),
        "teams": teams,
    }
    validate(document, "teams")
    return document


def export_teams(database: Path, out_path: Path, generated_at: datetime) -> int:
    """Write ``teams.json`` and return how many teams it holds.

    Nothing is written if validation fails.
    """
    document = build_teams_document(database, generated_at)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    teams = document["teams"]
    assert isinstance(teams, list)  # noqa: S101 - narrowing for the type checker
    return len(teams)
