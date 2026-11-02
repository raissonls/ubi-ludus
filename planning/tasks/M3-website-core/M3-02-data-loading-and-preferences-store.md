---
id: M3-02
title: Data loading and preferences store
milestone: M3
priority: Must
estimate_h: 3
status: todo
requirements: [FR-22]
depends_on: [M3-01]
---

# M3-02 · Data loading and preferences store

**Milestone:** M3 Website core (Nov 23 - Dec 6) · **Priority:** Must · **Estimate:** 3 h

## Why

Load the published JSON and keep each visitor's choices only in their own browser.

## Definition of done

- [ ] Loader for `matches.json`, `teams.json`, `competitions.json`, `broadcasters.json` and `status.json`.
- [ ] Preferences saved in `localStorage` only, with a "Reset my data" control.
- [ ] No network request carries preferences (checked in the browser network tab).
- [ ] Handles `localStorage` being unavailable.

## Notes

_Add decisions, links and anything learned while doing the task._
