---
id: M4-04
title: Failure alerts and keep-alive
milestone: M4
priority: Must
estimate_h: 2
status: todo
requirements: [FR-51, FR-52, R6]
depends_on: [M4-03]
---

# M4-04 · Failure alerts and keep-alive

**Milestone:** M4 E-mail and operations (Dec 7-13) · **Priority:** Must · **Estimate:** 2 h

## Why

Know when it breaks, and stop GitHub from disabling the schedule after 60 days of inactivity.

## Definition of done

- [ ] A forced failure produces a notification within 15 minutes.
- [ ] Keep-alive mechanism documented and verified by a dry run.
- [ ] Workflow `permissions:` reviewed for least privilege.

## Notes

_Add decisions, links and anything learned while doing the task._
