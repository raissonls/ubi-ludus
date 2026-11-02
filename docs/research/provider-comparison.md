# Provider comparison (M0-01)

**Status:** complete, 2026-11-01. Decision recorded (option A below). Work item: issue [#1](../../../../issues/1).

**Question:** which free data provider can supply fixtures for the competitions in PRD section 5.1, within R$ 0/month, and may we show the data on a public site?

## Decision

**Use two providers behind the adapter interface (FR-01), and accept a short horizon for the competitions only the second one covers.**

| Provider | Role | Horizon |
|---|---|---|
| **football-data.org** | Primary. Série A, Libertadores, Champions League, top 5 European leagues, World Cup, Euros (and Championship, Eredivisie, Primeira Liga). | Up to 14 days ahead |
| **API-Football** | Second. Everything else: Copa do Brasil, Copa Sul-Americana, state championships, national-team qualifiers and friendlies, plus a cross-check for the rest. | **Yesterday, today and tomorrow only** (free plan limit) |
| **TheSportsDB** | Rejected. | - |

**Rule for the website (owner decision, 2026-11-01):** for competitions that only have the short horizon, the site must state clearly that data is available **only until tomorrow**. It must never look like "no matches" when the real answer is "we don't know yet" (PRD FR-34).

Broadcasters are not available from any provider. They come from our own rights table (FR-10), as the PRD already says.

## Coverage by competition (verified with real calls, 2026-11-01)

Legend: **14d** = fixtures up to 14 days ahead, **1d** = only yesterday to tomorrow, **No** = not available, **-** = not tested.

| Competition | football-data.org (free) | API-Football (free) | TheSportsDB (free key) |
|---|---|---|---|
| Brasileirão Série A | **14d** (code `BSA`) | 1d (league 71) | truncated |
| Copa do Brasil | No (not in competition list) | **1d** (league 73) | - |
| Copa Libertadores | **14d** (code `CLI`, see note) | 1d (league 13) | - |
| Copa Sul-Americana | No (code not found) | **1d** (league 11) | - |
| State championships | No (not in competition list) | **1d** (for example Paulista A1 475, Carioca 624, Mineiro 629, Gaúcho 477) | partial |
| Champions League | **14d** (`CL`) | 1d | - |
| Top 5 European leagues | **14d** (`PL`, `PD`, `SA`, `BL1`, `FL1`) | 1d | truncated |
| World Cup | **14d** (`WC`) | 1d | truncated |
| World Cup qualifiers, other national-team matches | No (only the Euros, `EC`) | **1d** | - |

In bold: the provider that decides what the site can show for that competition.

**Libertadores note:** football-data.org's coverage page and its competition list mark `CLI` as a paid tier, but with the free token it returned 47 matches for April 2026 and the two upcoming final fixtures (28 Nov: Palmeiras x Estudiantes de La Plata). It works today. Treat it as something that may change without notice. If it stops working, Libertadores falls back to the short horizon like the other cups.

## Provider details

### football-data.org

- **Real calls:** the token sees 13 competitions (12 free tier plus Libertadores). Fixtures by competition and date range work: 13 Série A matches for 31 Oct to 15 Nov, 18 Champions League matches.
- **Match fields:** id, kickoff in UTC (`utcDate`), status (for example `TIMED`, `FINISHED`), matchday, stage, `lastUpdated`, home and away team (id, name, short name, three-letter code, crest URL), score, referees. Odds are locked behind a paid package.
- **Limits:** 10 calls per minute. Responses carry `X-Requests-Available-Minute` and `X-RequestCounter-Reset` headers, so the client can throttle itself. One daily run for the 13 competitions is about 13 calls, about 90 seconds if spaced at 7 seconds.
- **Delay:** the pricing page says "Schedules delayed" without a length. A match 24 hours ahead showed a `lastUpdated` timestamp from the same day, so the delay is not obvious in practice. To be watched during M1.
- **Terms** (General Terms and Conditions, last updated 2018-06-01, read from the [registration page](https://www.football-data.org/client/register)):
  - **Attribution (7.1):** the site must show "Football data provided by the Football-Data.org API" somewhere visible, for example in the footer.
  - **One application per key (2.3):** a key applies to a single application, and for a web app to a single domain.
  - **Keys in open-source repos (6.1):** credentials "may not be stored in code repositories of open source projects". Use GitHub Secrets, never commit the key.
  - **Fair use (3):** excessive use can be cancelled without notice.
  - **After cancelling (9.1):** you may no longer reference the data on your site. Irrelevant on the free tier unless we upgrade.
  - **Logos (9.2):** team logos belong to their owners. This matches our colours-only rule.
  - **Not stated:** no non-commercial restriction and no ban on showing fixtures on a public site.

### API-Football (api-football.com)

- **Real calls, free plan, 100 requests per day and 10 per minute:**
  - Listing leagues works: 108 Brazilian competitions including Copa do Brasil, all state championships, and the CONMEBOL Libertadores (13) and Sudamericana (11).
  - **Seasons:** any query with `season=2026` returns "Free plans do not have access to this season, try from 2022 to 2024."
  - **The `next` parameter** is blocked on the free plan.
  - **Date queries** work only for a three-day window. Asking for 8 Nov returned "try from 2026-11-01 to 2026-11-03", which is yesterday through tomorrow (UTC).
  - **One call per day returns every league:** `fixtures?date=2026-11-02` returned 231 matches in 115 leagues in one response. Three calls (yesterday, today, tomorrow) cover everything the free plan allows.
- **Broadcast data:** none. Responses contain `fixture`, `goals`, `league`, `score` and `teams` only.
- **Terms** (last updated 2025-05-21, pasted by the owner from the [terms page](https://www.api-football.com/terms), whose site blocks automated reads):
  - **Websites are an intended use.** The terms say the data is provided so users can build "applications, websites, fantasy soccer games etc."
  - **No resale.** Selling the data directly or reselling it to third parties is prohibited. We only display it for free.
  - **No licence to publish.** "We do not provide a 'license' for the use and publication of the data". Permission to publish "must be requested by the user from the competent authorities", and some competition data may be subject to rights held by leagues, federations or organizers. This is the main legal risk.
  - **Their right to cut us off.** On a formal complaint from a rights holder, they may suspend or terminate access without refund.
  - **Mass media.** Betting, television broadcasting, fantasy platforms or mass-media distribution may need extra licences. A small fan site is not that, but it is the reason to stay low-key and non-commercial.
  - **Rate limits are binding.** Exceeding the per-minute limit is a "material breach" and can lead to suspension. We must throttle to 10 per minute or less. Reaching the daily quota suspends the account for the rest of the day.
  - **Free plan can change at any time** without notice, including which data it returns.
  - **Accounts:** one per developer, no extra accounts to raise the free limit.
  - **Attribution:** none required. We will credit the source anyway (see below).
  - **Logos and images:** provided for identification only, with rights held by third parties. We do not use them (PRD R5).

### TheSportsDB

- **Free key** `123`, 30 requests per minute per its documentation. The terms page returned HTTP 502, so republishing terms are not verified. This does not matter while the provider stays rejected.
- **Real calls with the free key:**

| Call | Returned | What a daily pipeline needs |
|---|---|---|
| All leagues | 10 soccer leagues | Every league we cover |
| Leagues in Brazil | 5 rows (Women's league, Série D, three state championships) | Full list |
| Next events, Série A | **1** match | Next 14 days |
| 2026 season schedule, Série A | **15** matches (late Jan to early Feb only) | Whole season |
| Day schedule, 8 Nov, all soccer | **3** matches (all Argentine) | Every match that day |
| TV events, 8 Nov | 1 row (MLS, "International") | Brazilian channels |

- **Verdict:** rejected. Paid plans start at $9/month, which breaks the R$ 0 goal.

## What the terms mean for the design

These are practical conclusions, not legal advice. R2 and R5 in the PRD stay open until the owner is comfortable with them.

1. **Publish the minimum.** The public JSON files contain only what the site needs: team names, competition, kickoff time (UTC), status, and the broadcast we derive. No raw provider payloads, no crests or logos, no scores or lineups.
2. **Attribute both sources** in the site footer: "Football data provided by the Football-Data.org API" (required) and "API-Football" (courtesy).
3. **Throttle below the limits:** at most 10 calls per minute per provider, using the rate-limit headers where they exist, and read API-Football's `status` endpoint to watch the daily quota.
4. **Keys only in GitHub Secrets.** Neither provider allows keys in a public repo, and football-data.org forbids it explicitly.
5. **Stay non-commercial.** No ads, no paid tier, no selling data. Any change here means re-reading both terms.
6. **Providers can change or cut access.** football-data.org's Libertadores access and API-Football's free plan can change without notice. The adapter interface and the "not covered yet" state in the UI are the safety net.
7. **Raw samples stay out of git.** The real responses from this spike are saved locally in `research-samples/`, which git ignores. When M1-03 needs test fixtures, record a small trimmed set by hand.

## Architecture implications

1. **Two adapters (FR-01):** football-data.org for the 14-day window, API-Football for the daily "yesterday, today, tomorrow" sweep.
2. **Horizon per competition in config.** `config/competitions.yml` records which provider serves each competition and its horizon (14 days or "until tomorrow"). The pipeline and the site both read it, so the label required by FR-34 is driven by data, not hard-coded.
3. **API-Football budget:** 3 calls per run for the date sweep, out of 100 per day.
4. **Team names differ between providers** (for example "RB Bragantino" in football-data.org). The alias mapping in M1-04 has to match them.
5. **Merge, don't duplicate.** A match covered by both providers (for example Série A tomorrow) must appear once.
6. **Rights table stays ours** for broadcasters.

## Follow-ups from this decision

- **PRD:** FR-04 now allows a shorter window per competition, and a new FR-34 requires the "data only until tomorrow" label (done in this change).
- **Possible later improvement:** hand-maintained calendars for Copa do Brasil and Copa Sul-Americana, so those cups also reach 14 days. Not part of Phase 1 (option B in the earlier draft); it is in the backlog.
- **Paid plan** (API-Football Pro, $19/month) was rejected because it breaks goal G3.
