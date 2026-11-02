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
- Stay inside the provider's rate limits. Make every call through the `http_get` you were given (the guard counts, limits and caches it). Read API keys from environment variables and never log them.
- Raise `ProviderError` when the provider cannot be used. Let real bugs raise normally.
- Never write recorded provider data into the repository. Trim test fixtures by hand.

## Adapters that exist

| Name | Module | Key (environment variable) | Notes |
|---|---|---|---|
| `football-data` | `football_data.py` | `FOOTBALL_DATA_TOKEN` | One call per competition. Waits when the per-minute allowance is used up and retries once after an HTTP 429. A competition the plan does not serve (403 or 404) is skipped and listed in `adapter.skipped`. |
| `api-football` | `api_football.py` | `API_FOOTBALL_KEY` | The free plan sees only yesterday to tomorrow, and one call for a date returns every league. So a run reads `status` (the daily quota, 100) and then makes one `fixtures?date=...` call per day, three at most, today first. Days are asked for in Brazil's calendar (`timezone=America/Sao_Paulo`). Only the leagues listed in `config/competitions.yml` are kept. A day the plan refuses (an `errors.plan` answer with HTTP 200) is skipped and listed in `adapter.skipped`; the provider fails only when no day could be served. If the quota cannot cover all days, yesterday is dropped first. A rate-limit answer waits a minute and retries once. |

`default_registry()` in `default.py` registers all of them. Put the key in a local `.env` file (git-ignored) or in GitHub Secrets. If the key is missing, that provider shows up as a failed `FetchOutcome` and the others still run.

Tests use hand-written fixtures in `tests/fixtures/football_data/` and `tests/fixtures/api_football/` and a fake HTTP function, so they never touch the network.

## Cache, rate limit and call count (FR-03)

Adapters do not call the network directly. They call an `HttpGet` function, and `default_registry()` hands each one a `GuardedHttp` (`guard.py`) that sits in front of the real one:

1. **Cache** (`cache.py`). A request already answered less than an hour ago is answered from disk, for free.
   - **Key:** the provider name plus the full request URL. Keys and tokens travel in headers, so no secret is ever in a file name or a file.
   - **Expiry:** one hour (`cache_ttl_seconds`). Older entries are ignored, and deleted when the registry is built.
   - **What is stored:** only an HTTP 200 whose body is a JSON object with no `errors` in it, so a refusal ("this date is outside the free plan") is never replayed. Rate-limit headers are not stored; a replay carries none.
   - **Never cached:** API-Football's `status` call, because today's quota is exactly what must be fresh.
   - **Where:** `cache_dir`, off unless given. The scheduled workflow (M4-03) keeps it between runs with the Actions cache. The default location, `.cache/`, is git-ignored: provider data is not ours to commit.
   - A missing, damaged or unwritable cache is a miss, never a failed run.
2. **Call budget.** A limit on *real* calls per provider per run, checked before the call leaves the machine. Football-data has a fuse of 40 (a run needs about 13). API-Football's budget is replaced, once the run has read `status`, by the quota the provider says is left, and retries count against it. Over budget, an adapter stops asking, keeps what it already has, and lists the rest in `adapter.skipped`.
3. **Rate limiter.** At most 10 calls in any 60 seconds per provider (both providers' documented limit), by waiting. A sliding window is stricter than the fixed minute the providers count.
4. **Call log.** Every call is logged at INFO with its path and query (never a header), and `fetch_all(requests, registry, call_log)` logs the run's total at the end, even when a provider failed:
   `Provider calls this run: api-football 4 (4 over the network, 0 from cache); football-data 13 (11 over the network, 2 from cache). Total over the network: 15`

The adapters still read the provider's own signals (rate-limit headers, plan errors). The guard is the floor under them: it does not depend on the provider telling the truth.

```python
log = CallLog()
registry = default_registry(cache_dir=Path(".cache/provider-responses"), call_log=log)
outcomes = fetch_all(plan_fetches(competitions, today), registry, log)
```

## Two providers, one match

A competition can list both providers in `config/competitions.yml` (Série A and Libertadores do). The adapters do not care: each fetches its own. The merge happens in dbt (`int_matches_merged`, see the [dbt README](../../../../dbt/README.md)), so a match both know is published once.
