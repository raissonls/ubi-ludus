# ADR-002: dbt and Python together, on DuckDB

- **Status:** Accepted
- **Date:** 2026-11-02
- **Related:** [ADR-001](ADR-001-architecture.md) (extends decisions 2 and 7), [PRD](../PRD.md) FR-02, FR-04, FR-05, FR-10 to FR-13, [schemas](../../schemas/README.md), issue [#7](../../../../issues/7)

## Context

ADR-001 chose a static pipeline: Python fetches data, a validator checks the published JSON against JSON Schemas, and the site reads the files. After the schemas were built (M1-01) we found what they cannot check:

- **Shape only.** A schema checks that a file has the right fields, types and values. It cannot compare one record with another.
- **Gap found in the spike.** The valid test fixtures for `matches.json` and `teams.json` both pass their schemas, yet one match points to a team that is not in `teams.json`. JSON Schema accepts this. A dbt `relationships` test caught it.
- **More joins are coming.** Merging two providers (team names, duplicates), applying rights rules with validity dates and overrides, deciding each competition's window, and spotting rescheduled matches are all set-based problems that SQL expresses well.

The owner works with dbt and Python together in GitHub workflows professionally, wants to combine both tools here, and wants it at **R$ 0 per month** while keeping a clear path to scale.

**Spike (2026-11-02, throwaway project, Windows, Python 3.12.10):**

| Measure | Result |
|---|---|
| Install `dbt-core` 1.12 and `dbt-duckdb` 1.11 | about 90 seconds, about 180 MB |
| `dbt build` of 3 models and 10 tests over our JSON fixtures | 6 seconds |
| Result | 12 passed, 1 failed: the dangling team reference JSON Schema had accepted |
| Cost | none: dbt Core (Apache-2.0), dbt-duckdb and DuckDB are free and run inside GitHub Actions |

## Decision

1. **Split the work by what each tool is good at.**
   - **Python** does input, output and orchestration: calling the providers within their limits, caching, loading raw data into DuckDB, running dbt, exporting the final JSON, validating it against the schemas, rendering and sending the e-mail, and deploying.
   - **dbt (SQL on DuckDB)** does the transformation and the data quality checks: typing and renaming each provider's data, matching team names, merging and de-duplicating providers, applying each competition's window, flagging reschedules, resolving broadcasters with confidence levels and override precedence, and computing the status metrics.
2. **Layers.** `raw` (loaded by Python, never published) then `staging` (typed and renamed per source) then `intermediate` (mapped, merged, de-duplicated) then `marts` (one model per published file, shaped like its schema).
3. **Engine: DuckDB through `dbt-duckdb`, with dbt Core.** An embedded database in one file or in memory, with no server and no cost. Versions are pinned and Dependabot keeps them current. Volumes in Phase 1 are hundreds of rows, so the engine is far from a limit.
4. **Two kinds of checks, both must pass.**
   - **dbt tests (inside the pipeline):** unique ids, not null, `relationships` between files, accepted values, and custom tests for PRD rules such as FR-12 and FR-13.
   - **JSON Schema (the contract with the site):** the shape of the published files, as built in M1-01.
   - Any failure stops the run before anything is published, and the previous good data stays online.
5. **State between runs.** GitHub runners are temporary, so there is no persistent database. For reschedule detection (FR-05) the run downloads the **previously published** `matches.json` from the site and loads it as a raw table. The provider response cache (M1-05) uses the Actions cache.
6. **Human-edited sources stay YAML.** The rights table and overrides (FR-10, FR-11) remain readable YAML validated by schema. Python loads them into raw tables and dbt models resolve them.
7. **CI runs the SQL like code.** Every pull request runs `dbt build` against small recorded fixtures, next to ruff, mypy and pytest. Logic with precedence rules (overrides, rights windows) also gets dbt unit tests.
8. **Location:** the dbt project lives in `dbt/` at the repository root. Python code keeps its 80% line-coverage gate. SQL is covered by dbt tests instead.
9. **Scaling path.** To grow, change the dbt target to a hosted warehouse (for example MotherDuck, BigQuery or Snowflake) and move the raw data to object storage. The models, tests and Python I/O layer stay the same. This is a later decision with its own ADR, not part of Phase 1.

## Consequences

**Easier**

- The gap found in the spike is closed: references, uniqueness and cross-file consistency are tested on every run and every pull request.
- Set logic (provider merge, rights windows, overrides) is shorter and easier to review in SQL than in loops.
- Lineage and documentation come from dbt (`dbt docs`), and could be published later as an audit view.
- A familiar workflow for the owner, which supports goal G6 (a project that is enjoyable to maintain).

**Harder or accepted**

- **A second language and tool** to maintain, and a boundary to keep clean: Python must not grow transformation logic that belongs in a model.
- **Heavier CI:** about 180 MB and 90 seconds to install on a cold run, and a few seconds per run. The pip cache already used in CI softens this.
- **dbt moves quickly:** the spike already showed a deprecation (generic tests now take their arguments under `arguments:`). Pin versions and read release notes when Dependabot proposes an upgrade.
- **Plan impact:** about 7 extra hours across Phase 1, which uses most of the buffer in the 7-week plan (PRD risk R9). Should-have tasks are cut first if time runs short. The affected issues are updated alongside this decision.
- **Cold start every day** because runners keep nothing. Downloading the previous `matches.json` makes this work, but a failed download must degrade gracefully (no reschedule flags for that run), not fail the pipeline.

## Alternatives considered

- **Python-only integrity checks** (a function that checks uniqueness and references after the schema check). Smaller, with no new dependency, and a sound choice for a tiny project. Rejected because it grows into a hand-written, untested copy of what dbt tests provide, and because the owner wants to combine both tools and keep a scaling path.
- **Plain SQL scripts in DuckDB without dbt.** Gives the engine but not the test framework, lineage or conventions.
- **Python data-validation libraries** (for example Pandera or Great Expectations). Capable, but heavier or less natural than SQL tests for this shape of problem, and they give no lineage.
- **dbt Cloud.** Paid for what we need. dbt Core runs the same project for free in Actions.
- **A hosted warehouse from day one** (for example BigQuery's free tier). Adds credentials, an external dependency and a quota to watch. Deferred to the scaling path.
- **Transforming with pandas or Polars in Python.** Works, but moves the logic away from SQL tests and from a tool the owner already uses daily.
