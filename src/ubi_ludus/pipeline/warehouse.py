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

from ubi_ludus.pipeline.config import CompetitionConfig
from ubi_ludus.pipeline.rights import RightsData
from ubi_ludus.pipeline.yamlio import read_yaml

PROVIDER_RESPONSES_TABLE = "raw_provider_responses"
PREVIOUS_MATCHES_TABLE = "raw_previous_matches"
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
    document = read_yaml(path)  # dates stay text, so they survive the trip through JSON
    return load_records(con, table, _records(document, key, path))


def _records(document: Any, key: str | None, path: Path) -> list[Mapping[str, Any]]:
    records = document[key] if key is not None else document
    if not isinstance(records, list):
        where = f"under '{key}' in " if key else "in "
        raise ValueError(f"Expected a list of records {where}{path.name}")
    return records


def load_competitions(
    con: duckdb.DuckDBPyConnection, competitions: Sequence[CompetitionConfig]
) -> int:
    """Load the checked contents of ``config/competitions.yml`` into ``raw_competitions``.

    Horizon and coverage are the config's own rules (``CompetitionConfig``), loaded as they are.
    """
    return load_records(
        con,
        "raw_competitions",
        [
            {
                "id": c.id,
                "name": c.name,
                "country_or_region": c.country_or_region,
                "type": c.type,
                "coverage": c.coverage,
                "horizon_days": c.horizon_days,
                "sources": [
                    {
                        "provider": s.provider,
                        "provider_id": s.provider_id,
                        "horizon_days": s.horizon_days,
                    }
                    for s in c.sources
                ],
            }
            for c in competitions
        ],
    )


def load_previous_matches(
    con: duckdb.DuckDBPyConnection, document: Mapping[str, Any] | None
) -> int:
    """Load the matches of the previously published ``matches.json`` into ``raw_previous_matches``.

    ``None`` means the previous file could not be had. The table is created empty, so the
    models still run and simply find nothing to compare against.
    """
    con.execute(
        f"create or replace table {PREVIOUS_MATCHES_TABLE} ("  # noqa: S608 - constant name
        "id varchar, kickoff_utc varchar, status varchar, rescheduled_at varchar)"
    )
    matches = document["matches"] if document is not None else []
    rows = [(m["id"], m["kickoff_utc"], m["status"], m.get("rescheduled_at")) for m in matches]
    if rows:
        con.executemany(
            f"insert into {PREVIOUS_MATCHES_TABLE} values (?, ?, ?, ?)",  # noqa: S608
            rows,
        )
    return len(rows)


def _insert(con: duckdb.DuckDBPyConnection, sql: str, rows: Sequence[tuple[Any, ...]]) -> None:
    if rows:  # DuckDB refuses executemany with nothing to insert
        con.executemany(sql, rows)


def load_rights_tables(con: duckdb.DuckDBPyConnection, data: RightsData) -> None:
    """Load the checked rights files into ``raw_broadcasters``, ``raw_services`` and
    ``raw_rights_rules``. Tables are created even when empty, so the models always have them.

    ``rule_number`` is the rule's place in ``rights.yml`` (from 1), which is how a problem is
    traced back to the file.
    """
    con.execute(
        "create or replace table raw_broadcasters "
        "(id varchar, name varchar, kind varchar, service_id varchar, url varchar)"
    )
    con.execute(
        "create or replace table raw_services "
        "(id varchar, name varchar, includes_broadcasters varchar[])"
    )
    con.execute(
        "create or replace table raw_rights_rules "
        "(rule_number integer, competition_id varchar, season varchar, scope varchar, "
        "scope_value varchar, broadcasters varchar[], valid_from date, valid_to date, "
        "source varchar, notes varchar)"
    )
    _insert(
        con,
        "insert into raw_broadcasters values (?, ?, ?, ?, ?)",
        [(b.id, b.name, b.kind, b.service_id, b.url) for b in data.broadcasters],
    )
    _insert(
        con,
        "insert into raw_services values (?, ?, ?)",
        [(s.id, s.name, list(s.includes_broadcasters)) for s in data.services],
    )
    _insert(
        con,
        "insert into raw_rights_rules values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                number,
                r.competition_id,
                r.season,
                r.scope,
                r.scope_value,
                list(r.broadcasters),
                r.valid_from,
                r.valid_to,
                r.source,
                r.notes,
            )
            for number, r in enumerate(data.rules, start=1)
        ],
    )


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
