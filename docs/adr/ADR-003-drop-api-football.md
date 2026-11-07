# ADR-003: Stop using API-Football in the daily job

- **Status:** Accepted
- **Date:** 2026-11-07
- **Related:** [ADR-001](ADR-001-architecture.md) (changes decision 5, the providers), [provider comparison](../research/provider-comparison.md), [PRD](../PRD.md) FR-01, FR-34, risk R1, issue [#104](../../../../issues/104)

## Context

ADR-001 chose two free providers: football-data.org for 14 days ahead, and API-Football for everything else (Copa do Brasil, Copa Sul-Americana, the state championships, the national team's qualifiers and friendlies), but only until tomorrow.

On 2026-11-07, after two successful runs of the new daily workflow, API-Football answered every request with `Your account is suspended`. The owner's account page showed the same notice, and its status endpoint still reported 99 of 100 requests left, so it was not the quota. API-Football's own support assistant gave the likely cause: **requests that leave from shared IP addresses, such as GitHub Actions, GitHub's runners being shared with many other people, can trip its anti-abuse protection even when our own traffic is three requests a day**. Its only remedies are a dedicated outbound IP or a paid dedicated proxy.

The daily pipeline writes nothing when a provider fails (so the data published last stays up), which is what it did. But it also meant the pipeline stayed blocked while the account was suspended, and reinstating the account would not stop it happening again.

## Options considered

| Option | Cost | Why not |
| --- | --- | --- |
| Ask for reinstatement and keep calling it from GitHub Actions | free | The cause is still there; it would be suspended again |
| Run that fetch from a dedicated address: a small server (for example Amazon Lightsail, about US$5 a month with a static IP) | about US$60 a year plus upkeep | Breaks the R$ 0 goal and the "no server" design (ADR-001) for three requests a day |
| API-Football Pro, about US$19 a month | money | Breaks the R$ 0 goal, and it is not known to avoid the problem |
| Run the fetch on the owner's own computer or a self-hosted runner | free | Only works when it is on, and the provider's raw responses cannot be stored in the repository |
| **Stop using it** | free | Chosen |

## Decision

1. `config/competitions.yml` no longer lists API-Football as a source. The daily job calls only football-data.org.
2. The competitions that only API-Football served stay in the file with `sources: []`: Copa do Brasil, Copa Sul-Americana, the four state championships, the World Cup qualifiers and the national-team friendlies. Their data coverage is `none`, and the site lists them as **"not covered yet"** instead of silently missing (PRD risk R1). The line that served each one is kept in a comment.
3. The API-Football key is no longer given to any workflow. The footer and the privacy notice no longer credit it.
4. The adapter, its dbt model and its tests stay in the repository, **switched off**. Nothing in the daily job refers to them.
5. Hand-maintained calendars (issue [#55](../../../../issues/55), to be widened to cover these competitions) are the way to give them data again.

## Consequences

- The pipeline is no longer exposed to a provider that cannot be reached from GitHub-hosted runners.
- **The Brazil national team's matches, the cups and the state championships have no data** until the calendars exist. The owner's e-mail will not list the national team.
- The "until tomorrow" notice (FR-34) is still in the code and its tests, with no competition using it now; it would apply again to any source with a short horizon.
- One provider is now a single point of failure. If football-data.org cuts a competition (Libertadores is a paid tier there and works only by tolerance), that competition becomes "not covered yet" by changing its sources to `[]`.

## How to bring it back

For a project with a dedicated outbound IP:

1. Put the `was:` lines in `config/competitions.yml` back as sources.
2. Add `API_FOOTBALL_KEY` as a repository secret and give it to the build step of `.github/workflows/pipeline.yml` (and to the weekly review).
3. Put the footer credit back (`footer.attribution.apiFootball`) and the notice in `PRIVACY.md`.
4. Run the pipeline by hand once and watch the first run.
