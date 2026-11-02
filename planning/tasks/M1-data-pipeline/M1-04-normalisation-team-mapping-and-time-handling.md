---
id: M1-04
title: Normalisation, team mapping and time handling
milestone: M1
priority: Must
estimate_h: 4
status: todo
requirements: [FR-02, FR-06]
depends_on: [M1-03]
---

# M1-04 · Normalisation, team mapping and time handling

**Milestone:** M1 Data pipeline (Nov 9-15) · **Priority:** Must · **Estimate:** 4 h

## Why

Turn provider payloads into the internal model, with stable team and competition IDs and correct local dates.

## Definition of done

- [ ] `normalise.py` outputs data that validates against the schemas.
- [ ] Team alias mapping so the same club has one ID across providers (`teams.json` with colours, no crests).
- [ ] Kickoff stored in UTC, displayed in `America/Sao_Paulo` using the IANA zone, not a fixed offset.
- [ ] Test cases around midnight show the correct local date.

## Notes

_Add decisions, links and anything learned while doing the task._
