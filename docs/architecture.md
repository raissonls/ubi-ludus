# Architecture

How Ubi Ludus fits together. This is a living overview: it starts as a skeleton in M0 and gets filled in as each milestone lands. The reasons behind the big choices are in [ADR-001](adr/ADR-001-architecture.md), and the product behaviour is in the [PRD](PRD.md).

## In one paragraph

A scheduled GitHub Actions job runs once a day. Python fetches fixtures from the free data provider (football-data.org) and loads them into an embedded DuckDB database. dbt models then clean and merge them, add broadcast information from our own rights table, and run data quality tests. Python exports the result as static JSON, validates it against the schemas, and publishes it with a static website to GitHub Pages. It also sends the owner a morning e-mail. Visitors' browsers download the JSON and do all the personalisation locally, so there is no server and nothing personal is stored anywhere but the visitor's own browser. The split between Python and dbt is explained in [ADR-002](adr/ADR-002-dbt-duckdb.md). The daily workflow, what it does when something fails and how to set it up are in [pipeline.md](pipeline.md).

## Data flow

```mermaid
flowchart LR
    subgraph Sources
      FD["football-data.org<br/>up to 14 days ahead"]
      R["rights.yml + overrides.yml<br/>(maintained by hand)"]
      C["competitions.yml + owner.yml<br/>(config)"]
    end
    P["Previous published matches.json<br/>(for reschedule detection)"]
    subgraph "GitHub Actions (daily, 06:00 BRT)"
      F["Python: fetch + cache"] --> L["Python: load raw tables<br/>into DuckDB"]
      L --> T["dbt: staging, merge, window, rights<br/>+ data tests"]
      T --> X["Python: export JSON<br/>+ validate against schemas"]
      X --> B[Build static site]
    end
    FD --> F
    C --> F
    R --> L
    P --> L
    B --> D[Deploy to GitHub Pages]
    X --> M[Render + send owner e-mail]
    D --> U["Visitor browser:<br/>onboarding, filters, localStorage"]
```

Python does input, output and orchestration. dbt does the transformation and the data tests (unique ids, references between files, accepted values). If any test or schema check fails, the previous good data stays published and the site's freshness indicator warns the visitor.

DuckDB is embedded and the runners keep nothing between days, so each run starts from the raw inputs plus the previously published `matches.json`.

## Components

| Part | Where | What it does | Built in |
|---|---|---|---|
| Provider adapters | `src/ubi_ludus/pipeline/providers/` | One module per data source behind a common interface | M1 ([#8](../../../issues/8), [#9](../../../issues/9), [#53](../../../issues/53)) |
| Raw loader | `src/ubi_ludus/pipeline/` | Python loads provider responses, the rights YAML and the previous `matches.json` into DuckDB raw tables | M1 ([#63](../../../issues/63), [#10](../../../issues/10)) |
| Normalise and merge | `dbt/models/` (staging, intermediate) | Types and renames each provider's data, matches team names, removes duplicates across providers, converts times | M1 ([#10](../../../issues/10), [#53](../../../issues/53)) |
| Cache, rate limiting and call count | `src/ubi_ludus/pipeline/providers/` (`cache.py`, `guard.py`) | Avoids repeat calls, stays under each provider's limit and quota, logs the run's calls | M1 ([#11](../../../issues/11)) |
| Rolling window | `dbt/models/` | Keeps only each competition's allowed window; flags rescheduled matches by comparing with the previous run | M1 ([#12](../../../issues/12)) |
| Rights engine | `dbt/models/` | Resolves broadcasters per match with a confidence level; applies overrides; covered by dbt tests and unit tests | M2 ([#14](../../../issues/14), [#15](../../../issues/15)) |
| Rights data | `data/rights/` | Broadcasters, services, rules and overrides, edited by hand | M2 ([#13](../../../issues/13), [#16](../../../issues/16)) |
| Schemas | `schemas/` | JSON Schemas that validate every published file (the contract with the site) | M1 ([#7](../../../issues/7)) |
| dbt project | `dbt/` | Models, tests and docs that run on DuckDB; data quality checks between files (references, uniqueness, accepted values) | M1 ([#63](../../../issues/63)) |
| Export and validate | `src/ubi_ludus/pipeline/` | Python writes the final JSON from the dbt marts and validates it against the schemas | M1 ([#63](../../../issues/63)) |
| Website | `site/` | Static pages, onboarding, filters, match cards, calendar export | M3 ([#18](../../../issues/18) onwards) |
| Daily e-mail | `src/ubi_ludus/email/` | Renders and sends the morning briefing to the owner ([how it renders](email.md)) | M4 ([#30](../../../issues/30), [#31](../../../issues/31)) |
| Workflows | `.github/workflows/` | CI on pull requests now; the daily pipeline and review report later | M0 ([#4](../../../issues/4)), M4 ([#32](../../../issues/32)) |
| Config | `config/` | Which provider serves each competition and its horizon; the owner's teams and services | M1, M2 |

## Published files

Static JSON with a schema version, served next to the site: `matches.json`, `teams.json`, `competitions.json`, `broadcasters.json` and `status.json` (last success, record counts, unknown ratio). Only the fields the site needs are published: no raw provider payloads, no crests or logos. The data model is in [PRD section 8](PRD.md#8-data-model).

## Schedule and environments

- **CI** runs on every pull request and on `main` ([ci.yml](../.github/workflows/ci.yml)): lint, format, type-check, tests and a secret scan.
- **Daily pipeline** (from M4): 09:00 UTC (06:00 BRT) with a manual trigger, plus a keep-alive so GitHub does not disable the schedule after 60 days of inactivity.
- **Secrets** (provider keys, e-mail credentials) live only in GitHub Secrets and in a local `.env` that git ignores.
- **Local development:** see the README. Provider keys are optional for most work because tests use recorded fixtures, not live calls.

## Where the rest is documented

| Topic | Document |
|---|---|
| Why we chose this architecture | [ADR-001](adr/ADR-001-architecture.md) |
| Why dbt and Python together, on DuckDB | [ADR-002](adr/ADR-002-dbt-duckdb.md) |
| Why API-Football is not used | [ADR-003](adr/ADR-003-drop-api-football.md) |
| How fast the site is held to be, and how it is checked | [performance.md](performance.md) |
| Providers: coverage, limits, terms | [provider comparison](research/provider-comparison.md) |
| Security and the go-public plan | [security checklist](security-checklist.md) |
| How we plan and track work | [README](../README.md#how-we-plan-work) |

## To be written as the project grows

- Sequence of one daily run, with timings, once M4 exists.
- Rights resolution rules and override precedence (M2).
- Front-end structure, state handling and the pt-BR string file (M3).
- [Runbook](runbook.md): rotate a leaked secret, switch provider, disable the e-mail, roll back the site, the weekly routine ([#35](../../../issues/35)).
