---
id: M4-03
title: Daily pipeline workflow and Pages deploy
milestone: M4
priority: Must
estimate_h: 3
status: todo
requirements: [FR-50]
depends_on: [M1-06, M2-02, M4-02]
---

# M4-03 · Daily pipeline workflow and Pages deploy

**Milestone:** M4 E-mail and operations (Dec 7-13) · **Priority:** Must · **Estimate:** 3 h

## Why

Run the whole chain automatically: fetch, normalise, enrich, validate, build, deploy, e-mail.

## Definition of done

- [ ] `pipeline.yml` scheduled at 09:00 UTC (06:00 BRT) with `workflow_dispatch` for manual runs.
- [ ] Site deployed with the Pages artifact action, not by committing generated data.
- [ ] If a provider fails, the previous good dataset stays published.
- [ ] Requires the repository to be public if Pages is not available on the private plan (see M0-06).

## Notes

_Add decisions, links and anything learned while doing the task._
