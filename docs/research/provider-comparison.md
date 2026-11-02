# Provider comparison (M0-01)

**Status:** real calls done on 2026-11-01. One item is still open: the API-Football terms (see [Open items](#open-items)). Work item: issue [#1](../../../../issues/1).

**Question:** which free data provider can supply fixtures for the competitions in PRD section 5.1, within R$ 0/month, and may we show the data on a public site?

## Summary

| Provider | Free tier verdict | Why |
|---|---|---|
| **football-data.org** | **Primary provider** | Verified with real calls. 14-day fixtures for Série A, Libertadores, Champions League, top European leagues, World Cup and Euros. Terms allow a public site with attribution. |
| **API-Football** | **Second provider, short horizon only** | Covers every competition, including Copa do Brasil, Sul-Americana and state championships, but the free plan only returns fixtures for **yesterday, today and tomorrow**. |
| **TheSportsDB** | **Rejected** | The free key returns tiny result sets, so it cannot feed a daily pipeline. Paid plans break goal G3. |

**The gap:** no free provider gives fixtures **beyond tomorrow** for Copa do Brasil, Copa Sul-Americana, state championships and national-team qualifiers. This conflicts with PRD requirement FR-04 (14-day window) for those competitions. The options are in [Decision needed](#decision-needed).

**Broadcast data:** none of the providers gives Brazilian broadcast information. This confirms the PRD's design: broadcasters come from our own rights table.

## Coverage by competition (verified with real calls)

Legend: **14d** = fixtures up to 14 days ahead, **1d** = only yesterday to tomorrow, **No** = not available, **-** = not tested.

| Competition | football-data.org (free) | API-Football (free) | TheSportsDB (free key) |
|---|---|---|---|
| Brasileirão Série A | **14d** (code `BSA`) | 1d (league 71) | truncated |
| Copa do Brasil | **No** (not in competition list) | 1d (league 73) | - |
| Copa Libertadores | **14d** (code `CLI`, see note) | 1d (league 13) | - |
| Copa Sul-Americana | **No** (code not found) | 1d (league 11) | - |
| State championships | **No** (not in competition list) | 1d (for example Paulista A1 475, Carioca 624, Mineiro 629, Gaúcho 477) | partial |
| Champions League | **14d** (`CL`) | 1d | - |
| Top 5 European leagues | **14d** (`PL`, `PD`, `SA`, `BL1`, `FL1`) | 1d | truncated |
| World Cup | **14d** (`WC`) | 1d | truncated |
| World Cup qualifiers, other national-team matches | **No** (only the Euros, `EC`) | 1d | - |

**Note on Libertadores:** football-data.org's coverage page and its competition list mark `CLI` as a paid tier, but with the free token it returned 47 matches for April 2026 and the two upcoming final fixtures (28 Nov: Palmeiras x Estudiantes de La Plata). It works today. Treat it as something that may change without notice.

Other football-data.org competitions the free token can read: `ELC` (Championship), `DED` (Eredivisie), `PPL` (Primeira Liga).

## Provider details

### football-data.org

- **Real calls (2026-11-01):** token sees 13 competitions (12 free tier plus Libertadores). Fixtures by competition and date range work: 13 Série A matches for 31 Oct to 15 Nov, 18 Champions League matches.
- **Match fields:** id, kickoff in UTC (`utcDate`), status (for example `TIMED`, `FINISHED`), matchday, stage, `lastUpdated`, home and away team (id, name, short name, three-letter code, crest URL), score, referees. Odds are locked behind a paid package.
- **Limits:** 10 calls per minute. Responses carry `X-Requests-Available-Minute` and `X-RequestCounter-Reset` headers, so the client can throttle itself. One daily run for the 13 competitions is about 13 calls, which takes about 90 seconds if spaced at 7 seconds.
- **Delay:** the pricing page says "Schedules delayed" without a length. A match 24 hours ahead showed a `lastUpdated` timestamp from the same day, so the delay is not obvious in practice. To be watched during M1.
- **Terms** (General Terms and Conditions, last updated 2018-06-01, read from the [registration page](https://www.football-data.org/client/register)):
  - **Attribution (7.1):** the site must show "Football data provided by the Football-Data.org API" somewhere visible, for example in the footer.
  - **One application per key (2.3):** a key applies to a single application, and for a web app to a single domain.
  - **Keys in open-source repos (6.1):** credentials "may not be stored in code repositories of open source projects". Use GitHub Secrets, never commit the key.
  - **Fair use (3):** excessive use can be cancelled without notice.
  - **After cancelling (9.1):** you may no longer reference the data on your site. Irrelevant on the free tier unless we upgrade.
  - **Logos (9.2):** team logos belong to their owners. This matches our colours-only rule.
  - **Not stated:** no non-commercial restriction and no ban on showing fixtures on a public site. This is a reading of the terms, not legal advice.

### API-Football (api-football.com)

- **Real calls (2026-11-01), free plan, 100 requests per day and 10 per minute:**
  - Listing leagues works: 108 Brazilian competitions including Copa do Brasil, all state championships, and the CONMEBOL Libertadores (13) and Sudamericana (11).
  - **Seasons:** any query with `season=2026` returns the error "Free plans do not have access to this season, try from 2022 to 2024."
  - **The `next` parameter** is blocked on the free plan.
  - **Date queries** work only for a three-day window. Asking for 8 Nov returned the error "try from 2026-11-01 to 2026-11-03", which is yesterday through tomorrow (in UTC).
  - **One call per day returns every league:** `fixtures?date=2026-11-02` returned 231 matches in 115 leagues in one response, including Série A, Série B, state championships and Libertadores-level fixtures when played. Three calls (yesterday, today, tomorrow) cover everything the free plan allows.
- **Broadcast data:** none. Responses contain `fixture`, `goals`, `league`, `score` and `teams` only.
- **Terms: not read.** The site shows a Cloudflare bot check to automated fetches and to our browser pane, and we do not bypass bot checks. The owner needs to paste the text (see [Open items](#open-items)).

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

- **Verdict:** rejected. Paid plans start at $9/month, which breaks the R$ 0 goal.

## Decision needed

For Copa do Brasil, Copa Sul-Americana, state championships and national-team qualifiers, we can only know matches for **yesterday, today and tomorrow** from free providers. The options:

| Option | What the visitor sees | Cost to us |
|---|---|---|
| **A. Accept a short horizon** | These competitions appear only for today and tomorrow, marked as "short-term data". The daily e-mail (today's matches) is complete. | None. Simplest. |
| **B. Hand-maintained calendars (YAML)** for the cups only | Copa do Brasil and Sul-Americana matches appear up to 14 days ahead, like the rest. | The owner (or Claude, reviewed by the owner) updates dates from the CBF and CONMEBOL official calendars. These cups have few matches per round, so the weekly effort is small. |
| **C. Paid plan** (API-Football Pro, $19 per month) | Everything up to 14 days ahead. | Breaks goal G3 (R$ 0 per month). |

**Recommendation: A for launch, with B for the cups as a Should-have follow-up.** State championships run only from January to March, so a short horizon matters little for the rest of the year. Nothing needs to change in the PRD for A, but FR-04 should say that the 14-day window applies to competitions with a provider that allows it.

## Preliminary architecture implications

1. **Two providers behind the adapter interface (FR-01):** football-data.org for the 14-day window, API-Football for the daily "yesterday, today, tomorrow" sweep of everything else.
2. **API-Football budget:** 3 calls per run for the date sweep, out of 100 per day, leaving room for retries and extra lookups.
3. **Team names will differ between providers.** The team alias mapping in M1-04 needs to match them (for example "RB Bragantino" and "Bragantino").
4. **Deduplication:** a match covered by both providers (for example Série A tomorrow) must be merged, not shown twice.
5. **Rights table stays ours** for broadcasters, as the PRD says.

## Open items

- [ ] **API-Football terms:** the owner opens https://www.api-football.com/terms in their own browser and pastes the text. Needed to know whether a public site may show the data and whether attribution is required.
- [ ] **TheSportsDB terms** (502 on the last try). Not needed while the provider stays rejected.
- [ ] **Raw samples are not committed.** The real responses are saved locally and ignored by git, because raw provider data should not go into a repo that will be public until the terms allow it. Issue [#2](../../../../issues/2) covers that decision.
