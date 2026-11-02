---
id: M1-06
title: Rolling window and reschedule detection
milestone: M1
priority: Must
estimate_h: 3
status: todo
requirements: [FR-04, FR-05]
depends_on: [M1-04]
---

# M1-06 · Rolling window and reschedule detection

**Milestone:** M1 Data pipeline (Nov 9-15) · **Priority:** Must · **Estimate:** 3 h

## Why

Publish only yesterday through the next 14 days and flag matches that move.

## Definition of done

- [ ] `matches.json` contains only matches in the window.
- [ ] A match whose kickoff changes between runs is flagged `rescheduled` for 48 hours.
- [ ] Postponed and cancelled statuses carried through.
- [ ] The `status.json` contract (last success, record counts, unknown ratio) defined here and filled in M4-05.

## Notes

_Add decisions, links and anything learned while doing the task._
