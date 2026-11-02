---
id: M0-01
title: Provider comparison spike
milestone: M0
priority: Must
estimate_h: 4
status: todo
requirements: [FR-01, FR-03, FR-04, R1, Q2]
depends_on: []
---

# M0-01 · Provider comparison spike

**Milestone:** M0 Discovery spike (Nov 2-8) · **Priority:** Must · **Estimate:** 4 h

## Why

No free provider is guaranteed to cover every competition in PRD section 5.1 (risk R1). Make real calls against the candidate providers (for example football-data.org, API-Football free tier, TheSportsDB; these are candidates to evaluate, not decisions) and find out what each one actually returns.

## Definition of done

- [ ] Written comparison in `docs/research/provider-comparison.md`: one row per competition in section 5.1, one column per provider (covered / partial / not covered).
- [ ] Free-tier rate limits and request quotas recorded; one daily pipeline run fits inside them with margin.
- [ ] Notes on which fields each provider returns (teams, kickoff, status, round) and whether any broadcast info exists.
- [ ] Real responses saved as sanitized samples for later recorded-fixture tests (no API keys inside).
- [ ] Recommendation: which provider(s) to use, and which competitions will be shown as "not covered yet".

## Notes

_Add decisions, links and anything learned while doing the task._
