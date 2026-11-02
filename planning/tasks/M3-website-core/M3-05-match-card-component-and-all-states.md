---
id: M3-05
title: Match card component and all states
milestone: M3
priority: Must
estimate_h: 5
status: todo
requirements: [FR-24, FR-12, FR-13]
depends_on: [M3-02]
---

# M3-05 · Match card component and all states

**Milestone:** M3 Website core (Nov 23 - Dec 6) · **Priority:** Must · **Estimate:** 5 h

## Why

The match card is the core of the product. It must show teams, competition, local kickoff, broadcasters and confidence.

## Definition of done

- [ ] Card shows teams, competition, local kickoff time, broadcaster badges and confidence state.
- [ ] Visually distinct states for confirmed, rule, unknown, live and finished.
- [ ] Unknown matches show "Broadcast not confirmed yet" and no broadcaster name.
- [ ] Visual regression snapshots cover every state.
- [ ] Data rendered with safe DOM APIs (`textContent`), never raw `innerHTML`.

## Notes

_Add decisions, links and anything learned while doing the task._
