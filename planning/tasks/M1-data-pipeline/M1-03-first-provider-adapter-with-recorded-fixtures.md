---
id: M1-03
title: First provider adapter with recorded fixtures
milestone: M1
priority: Must
estimate_h: 4
status: todo
requirements: [FR-01]
depends_on: [M1-02, M0-01]
---

# M1-03 · First provider adapter with recorded fixtures

**Milestone:** M1 Data pipeline (Nov 9-15) · **Priority:** Must · **Estimate:** 4 h

## Why

Implement the provider chosen in M0 and test it without live calls.

## Definition of done

- [ ] Adapter fetches fixtures for the competitions the provider covers.
- [ ] Unit tests run against recorded fixtures in `tests/fixtures/`; no live calls in CI.
- [ ] API key read from an environment variable and never logged.
- [ ] User-agent identifies the project.

## Notes

_Add decisions, links and anything learned while doing the task._
