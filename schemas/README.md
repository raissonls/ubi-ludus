# Schemas

JSON Schemas (draft 2020-12) that describe our data. The pipeline validates everything it is about to publish against them, so invalid data fails the run and never reaches the site (PRD FR-02). The data model they implement is in [PRD section 8](../docs/PRD.md#8-data-model).

## The schemas

| Schema | Describes |
|---|---|
| `team`, `competition`, `match`, `broadcaster`, `service`, `broadcast` | One record of each kind |
| `matches`, `teams`, `competitions`, `broadcasters`, `status` | The published files `matches.json`, `teams.json`, `competitions.json`, `broadcasters.json` and `status.json` |
| `common` | Shared building blocks: ids, UTC timestamps, hex colours |

## Rules baked into the schemas

- **Only the minimum is published.** Records reject unknown fields, so a raw provider payload, a crest URL or a typo cannot slip through.
- **Times are UTC** with a trailing `Z`. Conversion to America/Sao_Paulo is for display only (PRD FR-06).
- **Every published file carries `schema_version`** and `generated_at`.
- **Broadcasts say how sure we are.** `confirmed` comes from an override or the provider, `rule` from the rights table. `unknown` never names a broadcaster (PRD FR-13).
- **`coverage` on a competition** says how far ahead we have data: `full` is up to 14 days, `short` is only until tomorrow, `none` is "not covered yet" (PRD FR-34).
- **A broadcast sits inside its match,** so `match_id` is not repeated. The PRD lists it as a separate entity, but the published shape nests it.
- **A team id can be `null`** on a match whose opponent is not decided yet.

## What schemas cannot check

A schema looks at one file's shape. It cannot tell that a match points to a team that is missing from `teams.json`, or that two matches share an id. Those cross-record checks are dbt tests, which run in the same pipeline step ([ADR-002](../docs/adr/ADR-002-dbt-duckdb.md)). A run publishes only when both the dbt tests and the schemas pass.

## Changing a schema

`schema_version` is `major.minor`. Change it in the file schemas (a `const`) and in every example under `tests/fixtures/schemas/valid/` when the format changes.

- **Minor** (for example 1.0 to 1.1): a new optional field. The site keeps working unchanged.
- **Major** (for example 1.1 to 2.0): removing or renaming a field, making a field required, or narrowing what is allowed. The site must be updated in the same change.

Because records reject unknown fields, adding any field means editing the schema on purpose.

## Checking data

```python
from ubi_ludus.pipeline.validate import validate, validate_file

validate(matches_document, "matches")  # raises SchemaValidationError
validate_file(Path("out/matches.json"), "matches")  # same, for a file on disk
```

`SchemaValidationError.errors` lists every problem with its location, for example `/matches/0/kickoff_utc: ...`.

## Examples and tests

Each schema has one valid and one invalid example in `tests/fixtures/schemas/`. The tests in `tests/unit/test_schemas.py` check that the valid ones pass, the invalid ones fail, and that the schemas themselves are valid. When you add a schema, add both examples or the tests fail.
