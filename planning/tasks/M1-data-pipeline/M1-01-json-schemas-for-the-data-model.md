---
id: M1-01
title: JSON Schemas for the data model
milestone: M1
priority: Must
estimate_h: 2
status: todo
requirements: [FR-02]
depends_on: [M0-05]
---

# M1-01 · JSON Schemas for the data model

**Milestone:** M1 Data pipeline (Nov 9-15) · **Priority:** Must · **Estimate:** 2 h

## Why

Pipeline output must be validated so bad data never reaches the site (PRD section 8).

## Definition of done

- [ ] `schemas/*.schema.json` for Team, Competition, Match, Broadcaster, Service, Broadcast and the published files (`matches.json`, `teams.json`, `competitions.json`, `broadcasters.json`, `status.json`).
- [ ] A validator helper that fails the pipeline on invalid output.
- [ ] Schema version field included in every published file.
- [ ] Unit tests with one valid and one invalid example per schema.

## Notes

_Add decisions, links and anything learned while doing the task._
