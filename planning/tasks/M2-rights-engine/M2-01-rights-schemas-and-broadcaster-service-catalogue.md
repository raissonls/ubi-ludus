---
id: M2-01
title: Rights schemas and broadcaster/service catalogue
milestone: M2
priority: Must
estimate_h: 3
status: todo
requirements: [FR-10]
depends_on: [M1-01]
---

# M2-01 · Rights schemas and broadcaster/service catalogue

**Milestone:** M2 Rights engine (Nov 16-22) · **Priority:** Must · **Estimate:** 3 h

## Why

Create the human-maintained data files that describe who can broadcast and what each subscription includes.

## Definition of done

- [ ] `data/rights/broadcasters.yml` and `services.yml` with the initial catalogue (free TV, pay TV, PPV, streaming, YouTube).
- [ ] Schemas for `rights.yml` (with `valid_from` / `valid_to`) and `overrides.yml`, validated in CI.
- [ ] Broadcaster-to-service relationships modelled (`includes_broadcasters`).

## Notes

_Add decisions, links and anything learned while doing the task._
