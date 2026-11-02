"""Write published files from the dbt marts, checking them against the schemas first."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from ubi_ludus.pipeline.validate import validate

SCHEMA_VERSION = "1.0"


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_mart(database: Path, table: str, order_by: str) -> list[dict[str, Any]]:
    # Same settings as dbt's own connection: DuckDB refuses to mix read-only and read-write
    # connections to one file inside one process.
    con = duckdb.connect(str(database))
    try:
        cursor = con.execute(f"select * from {table} order by {order_by}")  # noqa: S608 - constants
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()


def _build(name: str, generated_at: datetime, rows: list[dict[str, Any]]) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _timestamp(generated_at),
        name: rows,
    }
    validate(document, name)
    return document


def build_teams_document(database: Path, generated_at: datetime) -> dict[str, object]:
    """Read the ``teams`` mart and shape it like ``teams.json``. Raises if it breaks the schema."""
    rows = _read_mart(database, "teams", "id")
    return _build("teams", generated_at, rows)


def build_competitions_document(database: Path, generated_at: datetime) -> dict[str, object]:
    """Read the ``competitions`` mart and shape it like ``competitions.json``."""
    rows = _read_mart(database, "competitions", "id")
    return _build("competitions", generated_at, rows)


def build_matches_document(database: Path, generated_at: datetime) -> dict[str, object]:
    """Read the ``matches`` mart and shape it like ``matches.json``.

    ``broadcasts`` comes from the rights engine: every match has at least one, and a match
    nothing is known about has one ``unknown``. ``rescheduled_at`` is only present on matches
    that are flagged rescheduled.
    """
    rows = _read_mart(database, "matches", "kickoff_utc, id")
    for row in rows:
        if row["rescheduled_at"] is None:
            del row["rescheduled_at"]
    return _build("matches", generated_at, rows)


def _write(document: dict[str, object], key: str, out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    records = document[key]
    assert isinstance(records, list)  # noqa: S101 - narrowing for the type checker
    return len(records)


def export_teams(database: Path, out_path: Path, generated_at: datetime) -> int:
    """Write ``teams.json`` and return how many teams it holds.

    Nothing is written if validation fails.
    """
    return _write(build_teams_document(database, generated_at), "teams", out_path)


def export_competitions(database: Path, out_path: Path, generated_at: datetime) -> int:
    """Write ``competitions.json`` and return how many competitions it holds."""
    return _write(build_competitions_document(database, generated_at), "competitions", out_path)


def export_matches(database: Path, out_path: Path, generated_at: datetime) -> int:
    """Write ``matches.json`` and return how many matches it holds."""
    return _write(build_matches_document(database, generated_at), "matches", out_path)
