# ADR-001: Static pipeline architecture and data providers

- **Status:** Accepted. Decision 5 is partly superseded by [ADR-003](ADR-003-drop-api-football.md): API-Football is no longer used.
- **Date:** 2026-11-02
- **Related:** [PRD](../PRD.md) sections 7 and 9, [provider comparison](../research/provider-comparison.md), [security checklist](../security-checklist.md), issue [#5](../../../../issues/5)

## Context

Phase 1 of Ubi Ludus answers "where can I watch my team's next matches in Brazil?" for the owner and for any visitor, under these constraints:

- **Cost:** R$ 0 per month. Only free tiers.
- **Public by design:** the repository and the site are public. No accounts, no cookies, no server-side user data.
- **One maintainer** with about 18 hours a week and at most 30 minutes a week of upkeep after launch.
- **Data is scarce:** no free provider covers every competition, none offers Brazilian broadcast information, and the free plans have tight limits (see the provider comparison).
- **Quality targets:** Lighthouse 90 or more on mobile, at most 100 KB of JavaScript, WCAG 2.2 AA.

## Decision

1. **No runtime backend.** A scheduled GitHub Actions job runs the whole pipeline once a day (fetch, normalise, enrich, validate, build, deploy, e-mail). It publishes static JSON files next to a static site. Everything personal (chosen teams and services) happens in the visitor's browser and stays there.
2. **Python 3.12 for the pipeline and the e-mail.** Code lives in the `ubi_ludus` package under `src/` (`pipeline`, `email`). Tooling is ruff, strict mypy and pytest, with an 80% coverage gate on pipeline code.
3. **Vanilla HTML, CSS and JavaScript (ES modules) for the site.** No UI framework and minimal build tooling. Assets are self-hosted, with a Content Security Policy set by a meta tag, because GitHub Pages cannot send headers.
4. **Deploy with the GitHub Pages artifact action,** not by committing generated data to the repository. This keeps the git history free of daily data commits. On the Free plan, Pages needs a public repository, so the repository goes public before M1 (see the security checklist).
5. **Provider adapters.** Each data source is an adapter behind one interface, so a provider can be added, replaced or dropped without touching the rest.
   - **football-data.org** is the primary provider: fixtures up to 14 days ahead for Série A, Libertadores, Champions League, the top five European leagues, the World Cup and the Euros.
   - **API-Football** is the second provider: Copa do Brasil, Copa Sul-Americana, state championships and national-team matches, but only **yesterday, today and tomorrow** on the free plan.
   - **TheSportsDB** is rejected: its free key returns too little data.
   - Which provider serves each competition, and for how many days ahead, is configuration (`config/competitions.yml`). The site shows a notice for competitions with the short horizon (PRD FR-34).
   - A match covered by both providers is merged, not duplicated.
6. **Broadcasters come from our own rights table,** not from providers. It is human-maintained YAML (`data/rights/`) with match-level overrides and a confidence level on every result (`confirmed`, `rule`, `unknown`). When nothing is known the site says so instead of guessing.
7. **Published data is versioned static JSON validated by JSON Schema** (`schemas/`). Invalid output fails the pipeline, and if the pipeline fails the previous good data stays published.
8. **Publish the minimum.** Only the fields the site needs, with no raw provider payloads and no crests or logos, and credit both sources in the footer. This follows the providers' terms (provider comparison, section "What the terms mean for the design").

## Consequences

**Easier**

- Hosting is free and scales to any number of visitors. There is no server to patch and little attack surface.
- Privacy is simple to explain and to prove: choices never leave the browser.
- Swapping or adding a provider is a contained change.

**Harder or accepted**

- **Data is at most a day old.** One scheduled run per day, and GitHub may delay scheduled workflows at busy times. The site shows its freshness and warns when data is older than 36 hours.
- **The short horizon for some competitions** (until tomorrow) is a product limitation we show openly. A hand-maintained calendar for the two cups is a backlog item.
- **Two providers mean merge logic** (team-name matching, duplicates) and two sets of limits and terms to respect.
- **Free tiers can change without notice.** Libertadores access in football-data.org's free tier and API-Football's free plan limits are both outside our control. The adapter interface and the "not covered yet" state are the safety net.
- **GitHub dependence.** Actions, Pages and Secrets are one vendor. A move would mean rewriting the workflow and the deploy step, not the data pipeline.
- **Scheduled workflows are disabled after 60 days without repository activity,** so a keep-alive is required (PRD FR-52).
- **A vanilla front end** means writing small pieces ourselves (type-ahead picker, state handling) instead of using a library. This is deliberate, to stay under the size and supply-chain budget.

## Alternatives considered

- **Serverless or small backend** (for example edge functions with a database). Rejected: cost risk, accounts and data to protect, more to maintain for one person, and nothing in Phase 1 needs it.
- **A front-end framework** such as React or Svelte. Rejected for Phase 1: larger bundle, larger dependency and supply-chain surface, and the interface is small enough to build without one.
- **Committing generated data to the repository** (or a `gh-pages` branch). Rejected: noisy history and a growing repository.
- **A single provider.** Rejected: no free provider covers the competitions we need.
- **Paid providers or plans** (for example API-Football Pro at about $19 a month). Rejected because it breaks the R$ 0 goal.
- **Scraping TV guide sites for broadcasts.** Rejected for Phase 1: terms and breakage risk (PRD risk R4). Secondary sources may only propose overrides for a human to review (FR-15, backlog).
