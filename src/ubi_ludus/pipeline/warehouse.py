"""Load sources into DuckDB ``raw_*`` tables, the starting point for the dbt models.

Raw tables keep the shape of what was loaded. Cleaning, typing and merging happen in dbt
(ADR-002), never here.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb
import yaml

PROVIDER_RESPONSES_TABLE = "raw_provider_responses"
_TABLE_NAME = re.compile(r"^raw_[a-z][a-z0-9_]*$")


def connect(path: Path) -> duckdb.DuckDBPyConnection:
    """Open (and create if needed) the DuckDB file. Close the connection before running dbt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def _check_table_name(table: str) -> str:
    if not _TABLE_NAME.match(table):
        raise ValueError(f"Raw table names look like 'raw_something', got '{table}'")
    return table


def load_records(
    con: duckdb.DuckDBPyConnection, table: str, records: Sequence[Mapping[str, Any]]
) -> int:
    """Replace ``table`` with one row per record. Nested values become structs and lists."""
    _check_table_name(table)
    if not records:
        raise ValueError(f"Nothing to load into {table}: the record list is empty")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "records.json"
        source.write_text(json.dumps(list(records)), encoding="utf-8")
        con.execute(
            f"create or replace table {table} as "  # noqa: S608 - the name is checked above
            "select * from read_json(?, format = 'array')",
            [str(source)],
        )
    return len(records)


def load_json_file(
    con: duckdb.DuckDBPyConnection, table: str, path: Path, key: str | None = None
) -> int:
    """Load a JSON file holding a list of records, or an object with that list under ``key``."""
    document = json.loads(path.read_text(encoding="utf-8"))
    return load_records(con, table, _records(document, key, path))


def load_yaml_file(
    con: duckdb.DuckDBPyConnection, table: str, path: Path, key: str | None = None
) -> int:
    """Load a YAML file holding a list of records, or a mapping with that list under ``key``."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return load_records(con, table, _records(document, key, path))


def _records(document: Any, key: str | None, path: Path) -> list[Mapping[str, Any]]:
    records = document[key] if key is not None else document
    if not isinstance(records, list):
        where = f"under '{key}' in " if key else "in "
        raise ValueError(f"Expected a list of records {where}{path.name}")
    return records


def load_provider_responses(con: duckdb.DuckDBPyConnection, responses: Sequence[Any]) -> int:
    """Store raw provider responses (``RawResponse`` objects), payload untouched as JSON."""
    con.execute(
        f"create or replace table {PROVIDER_RESPONSES_TABLE} ("  # noqa: S608 - constant name
        "provider varchar, resource varchar, params json, fetched_at timestamptz, "
        "competition_id varchar, payload json)"
    )
    rows = [
        (
            r.provider,
            r.resource,
            json.dumps(dict(r.params), sort_keys=True),
            r.fetched_at,
            r.competition_id,
            json.dumps(r.payload),
        )
        for r in responses
    ]
    if rows:
        con.executemany(
            f"insert into {PROVIDER_RESPONSES_TABLE} values (?, ?, ?, ?, ?, ?)",  # noqa: S608
            rows,
        )
    return len(rows)
