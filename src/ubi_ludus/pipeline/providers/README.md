# Provider adapters

One adapter per data source. An adapter only **fetches**: it returns each provider response untouched, and the cleaning, merging and checking happen later in dbt ([ADR-002](../../../../docs/adr/ADR-002-dbt-duckdb.md)).

## How it fits together

1. `config/competitions.yml` says which provider serves each competition, with the provider's own id and how many days ahead it can tell us.
2. `plan_fetches` turns that into one `FetchRequest` per provider, with the right date window for each competition (`window.py`).
3. `fetch_all` looks each provider up in the `AdapterRegistry`, calls `adapter.fetch(request)`, and returns a `FetchOutcome` per provider. A provider that raises `ProviderError` is recorded as failed and does not stop the others.

## Adding a provider

1. Write a class that extends `ProviderAdapter` (see `base.py`) with a `name` and a `fetch` method.
2. Register it: `registry.register("my-provider", MyAdapter)`.
3. Add `sources` entries with `provider: my-provider` in `config/competitions.yml`.

If the config names a provider that has no adapter, the run stops before any call is made.

## Rules for an adapter

- Return `RawResponse` objects with the payload exactly as received and `fetched_at` in UTC.
- Stay inside the provider's rate limits. Read API keys from environment variables and never log them.
- Raise `ProviderError` when the provider cannot be used. Let real bugs raise normally.
- Never write recorded provider data into the repository. Trim test fixtures by hand.

## Adapters that exist

| Name | Module | Key (environment variable) | Notes |
|---|---|---|---|
| `football-data` | `football_data.py` | `FOOTBALL_DATA_TOKEN` | One call per competition. Waits when the per-minute allowance is used up and retries once after an HTTP 429. A competition the plan does not serve (403 or 404) is skipped and listed in `adapter.skipped`. |
| `api-football` | not yet | `API_FOOTBALL_KEY` | Planned in M1-07. |

`default_registry()` in `default.py` registers all of them. Put the key in a local `.env` file (git-ignored) or in GitHub Secrets. If the key is missing, that provider shows up as a failed `FetchOutcome` and the others still run.

Tests use hand-written fixtures in `tests/fixtures/football_data/` and a fake HTTP function, so they never touch the network.
