---
id: M2-02
title: Rights resolution engine
milestone: M2
priority: Must
estimate_h: 4
status: todo
requirements: [FR-10, FR-12, FR-13]
depends_on: [M2-01, M1-06]
---

# M2-02 · Rights resolution engine

**Milestone:** M2 Rights engine (Nov 16-22) · **Priority:** Must · **Estimate:** 4 h

## Why

For every match, work out the broadcasters and how sure we are.

## Definition of done

- [ ] Matching by competition + season, with optional round, stage or team scope.
- [ ] Every broadcast carries a confidence tag: `confirmed`, `rule` or `unknown`.
- [ ] A match with `unknown` never carries a broadcaster name.
- [ ] Unit tests for rule matching and date validity windows.

## Notes

_Add decisions, links and anything learned while doing the task._
