---
id: M1-05
title: Response cache, rate limiting and call logging
milestone: M1
priority: Must
estimate_h: 2
status: todo
requirements: [FR-03]
depends_on: [M1-03]
---

# M1-05 · Response cache, rate limiting and call logging

**Milestone:** M1 Data pipeline (Nov 9-15) · **Priority:** Must · **Estimate:** 2 h

## Why

Never exceed the provider's limits and avoid refetching what has not changed.

## Definition of done

- [ ] Responses cached between runs (cache key and expiry documented).
- [ ] A rate limiter enforces the provider's documented limit.
- [ ] Total calls per run logged.
- [ ] Test proves the pipeline stops calling when the quota would be exceeded.

## Notes

_Add decisions, links and anything learned while doing the task._
