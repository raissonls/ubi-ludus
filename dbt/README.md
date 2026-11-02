# dbt project

The transformation and data-quality layer of the pipeline. Python loads raw data into a DuckDB file, dbt turns it into the published shape and tests it, and Python exports and validates the result. The reasons are in [ADR-002](../docs/adr/ADR-002-dbt-duckdb.md).

## Layers

| Layer | Folder | Materialized as | What lives here |
|---|---|---|---|
| **raw** | not in dbt | tables `raw_*` | Loaded by Python from provider responses, YAML and JSON. Never published as they are. Declared in `models/staging/_sources.yml`. |
| **staging** | `models/staging/` | views | One model per raw table: type, rename, nothing else. Named `stg_<thing>`. |
| **intermediate** | `models/intermediate/` | views | Matching team names, merging providers, windows, rights rules. Named `int_<verb>_<thing>`. |
| **marts** | `models/marts/` | tables | One model per published file, shaped like its schema in `schemas/`. Named after the file, for example `teams`. |

Everything lives in one DuckDB schema (`main`), so layers are told apart by prefix and folder, not by schema.

## Conventions

- **Tests live next to the models** in a `_<layer>.yml` file. Every model has a unique and not-null test on its key, and every reference to another model has a `relationships` test.
- **Generic tests take their parameters under `arguments:`** (the older bare form is deprecated):

  ```yaml
  - relationships:
      arguments:
        to: ref('teams')
        field: id
  ```

- **A mart must match its schema.** dbt tests check consistency between tables; the JSON Schema checks the published shape. Python runs the schema check when it exports, so both must pass.
- **Avoid SQL keywords as column names** (`primary`, `inner`, `order`). Where a published field has such a name, use a struct literal such as `{'primary': color_primary}`.
- **No secrets in this folder.** The profile only points at a local file.

## Running it

From Python, which is how the pipeline does it (see `src/ubi_ludus/pipeline/dbt_runner.py`):

```python
from pathlib import Path

from ubi_ludus.pipeline.dbt_runner import run_dbt
from ubi_ludus.pipeline.warehouse import connect, load_yaml_file

database = Path("dbt/target/ubi_ludus.duckdb")  # git-ignored
con = connect(database)
load_yaml_file(con, "raw_teams", Path("data/teams.yml"), key="teams")
con.close()
run_dbt(database)  # raises DbtBuildError when a model or test fails
```

Or with the dbt command line, after loading the raw tables:

```bash
cd dbt
UBI_LUDUS_DB=target/ubi_ludus.duckdb dbt build --profiles-dir .
```

The database file, `dbt/target/` and `dbt/logs/` are git-ignored.

## Tests

`tests/unit/test_dbt_foundation.py` builds this project on small hand-written fixtures in `tests/fixtures/dbt/`. It runs inside the normal `pytest` run, so CI fails a pull request when a dbt model or test fails. To run only those tests: `pytest -m dbt`.

A deliberately broken fixture (two teams sharing one alias) proves that a failing dbt test stops the build.

## Adding a model

1. Put the SQL file in the right layer folder with the right prefix.
2. Add its tests to the `_<layer>.yml` next to it.
3. If it is a mart, make sure its columns match the schema in `schemas/`, then add an export function in `src/ubi_ludus/pipeline/export.py`.
4. Add a fixture and a test under `tests/`.
