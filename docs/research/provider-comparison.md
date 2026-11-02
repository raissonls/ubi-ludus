# Provider comparison (M0-01)

**Status:** draft, 2026-11-01. Work in progress for issue [#1](../../../../issues/1). Sections marked **not verified** need a real API call with a free key, which the owner has to register for.

**Question:** which free data provider can supply fixtures for the competitions in PRD section 5.1, within R$ 0/month, and may we show the data on a public site?

## Summary so far

| Provider | Free tier verdict | Why |
|---|---|---|
| **football-data.org** | **Good primary candidate** | Free forever; covers Série A, Champions League, top European leagues, World Cup and Euros. Terms allow a public site with attribution. Does **not** cover Copa do Brasil, Libertadores, Sul-Americana, state championships or World Cup qualifiers. |
| **API-Football** | **Best candidate for the gaps, unverified** | Provider says every plan includes all competitions, which would include the South American cups. Its website blocks automated reads, so coverage, season limits and terms are not verified. |
| **TheSportsDB** | **Rejected for the free tier** | Real calls show the free key returns tiny result sets (see below), so it cannot feed a daily pipeline. Paid plans cost money, which breaks goal G3. |

**Broadcast data:** none of the three gives a usable Brazilian broadcast listing. TheSportsDB has TV endpoints, but in the sampled days the only rows were MLS ones for an "International" audience. This confirms the PRD's approach: broadcasters come from our own rights table, not from the provider.

## Coverage by competition

Legend: **Yes** = confirmed, **No** = confirmed not on the free tier, **?** = not verified.

| Competition | football-data.org (free) | API-Football (free) | TheSportsDB (free key) |
|---|---|---|---|
| Brasileirão Série A | **Yes** (Série A Brazil) | ? | Yes (league 4351), but truncated results |
| Copa do Brasil | **No** | ? | ? (free key cannot list all leagues) |
| Copa Libertadores | **No** | ? | ? |
| Copa Sul-Americana | **No** | ? | ? |
| State championships | **No** | ? | Partial: Acreano, Alagoano, Amapaense appeared in a list cut at 5 rows |
| Champions League | **Yes** | ? | ? |
| Top 5 European leagues | **Yes** | ? | Yes |
| World Cup | **Yes** | ? | Yes (league 4429) |
| World Cup qualifiers | **No** | ? | ? |
| Other national-team matches | Partial: only the European Championship | ? | ? |

Sources for the football-data.org column: [coverage page](https://www.football-data.org/coverage) (the "Free Tier" section lists 12 competitions) and [pricing page](https://www.football-data.org/pricing). The coverage table has no free/paid marker per row, so only the Free Tier list counts as proof that something is free.

## Provider details

### football-data.org

- **Free plan:** 12 competitions, **10 calls per minute**, "Scores delayed", "Schedules delayed" (the delay length is not stated). Lineups, goal scorers and cards are paid. Free tier access is "free forever".
- **Fits our budget?** A daily run for around 12 competitions needs about 12 calls, so it fits easily if calls are spaced at least 6 seconds apart. To be confirmed with real calls.
- **Broadcast data:** none found in the docs.
- **Terms** (General Terms and Conditions, last updated 2018-06-01, read from the registration page):
  - **Attribution (7.1):** the site must show "Football data provided by the Football-Data.org API" somewhere visible, for example in the footer.
  - **One application per key (2.3):** a key applies to a single application, and for a web app to a single domain. Our one site fits.
  - **Keys in open-source repos (6.1):** "Developer credentials ... may not be stored in code repositories of open source projects." Use GitHub Secrets, never commit the key.
  - **Fair use (3):** usage must stay in line with the plan; excessive use can be cancelled without notice.
  - **After cancelling (9.1):** you may no longer reference the data on your site. The free tier has no cancellation fee, but this matters if we ever move to paid.
  - **Logos (9.2):** team logos and photos belong to their owners. This matches our rule of text and colours only.
  - **Not stated:** no non-commercial restriction and no ban on showing fixtures publicly. This is a reading of the terms, not legal advice.

### API-Football (api-football.com)

- **Not verified.** Every automated fetch of the pricing, coverage and terms pages returned 403 and the browser pane hit a bot check. We do not bypass bot checks.
- **From third-party sources (unconfirmed):** free plan has 100 requests per day and 10 per minute, resets at 00:00 UTC, and the provider says all plans include all competitions and endpoints.
- **Still to check with a key:** whether the free plan can read the current season, which leagues are present (list via the leagues endpoint), the exact limits, and the terms for publishing data on a public site.

### TheSportsDB

- **Free key** `123`, 30 requests per minute per its documentation. The terms page returned HTTP 502, so republishing terms are **not verified**.
- **Real calls on 2026-11-01** with the free key:

| Call | Returned | What a daily pipeline needs |
|---|---|---|
| All leagues | 10 soccer leagues | Every league we cover |
| Leagues in Brazil | 5 rows (Women's league, Série D, three state championships) | Full list |
| Next events, Série A | **1** match | Next 14 days |
| 2026 season schedule, Série A | **15** matches (late Jan to early Feb only) | Whole season |
| Day schedule, 8 Nov, all soccer | **3** matches (all Argentine) | Every match that day |
| TV events, 8 Nov | 1 row (MLS, "International") | Brazilian channels |

- **Verdict:** the free key is too limited. Paid plans start at $9/month, which breaks the R$ 0 goal.

## Preliminary recommendation

1. **football-data.org as the primary provider** for the competitions it covers for free (Série A, Champions League, top 5 European leagues, World Cup, Euros). It has readable terms and a simple attribution rule.
2. **API-Football as the second provider, if it passes verification,** for Copa do Brasil, Libertadores, Sul-Americana and state championships. This is why the pipeline uses a provider adapter interface (FR-01).
3. **Fallback if API-Football does not cover them:** hand-maintained YAML calendars for those competitions, as PRD risk R1 anticipates. The UI shows "not covered yet" for anything we still miss.
4. **Rights table stays ours** for broadcasters, as the PRD says.

## What is left to do for M0-01

- [ ] Owner registers for free keys at football-data.org and API-Football and saves them locally in a `.env` file (see below).
- [ ] Real calls to football-data.org: confirm competition codes, fixtures fields (kickoff, status, round), the schedule delay and the rate limit.
- [ ] Real calls to API-Football: list leagues, check the Brazilian and South American competitions, current-season access and limits.
- [ ] Read the API-Football terms (owner can open the page in their own browser if the bot check blocks us).
- [ ] Retry the TheSportsDB terms page (not needed if the provider stays rejected).
- [ ] Fill the **?** cells above and settle the recommendation.
- [ ] Sanitized sample responses for later recorded-fixture tests. **Not committed yet:** raw provider data should not be added to a repo that will be public until the terms allow it. Issue [#2](../../../../issues/2) covers that decision.

### Local keys

Create `.env` in the repository root. It is already ignored by git. Never paste keys into chat, issues or commits.

```text
FOOTBALL_DATA_TOKEN=...
API_FOOTBALL_KEY=...
```
