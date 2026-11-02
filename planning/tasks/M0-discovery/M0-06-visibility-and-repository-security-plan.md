---
id: M0-06
title: Visibility and repository security plan
milestone: M0
priority: Must
estimate_h: 1
status: todo
requirements: [S10, R7, NFR-security]
depends_on: []
---

# M0-06 · Visibility and repository security plan

**Milestone:** M0 Discovery spike (Nov 2-8) · **Priority:** Must · **Estimate:** 1 h

## Why

The repo is private for now, but the PRD says public by design and GitHub Pages on the free plan normally needs a public repository. Decide when the repo goes public and what must be in place first. Verify in the GitHub settings: branch protection and secret scanning may not be available on private repos on the free plan.

## Definition of done

- [ ] Decision recorded: date or trigger for making the repo public (suggested: before the first deploy, when M3 starts producing a site).
- [ ] Checklist of settings to enable on the day it goes public: branch protection on `main`, required checks, no force pushes, secret scanning and push protection, Dependabot alerts, Pages.
- [ ] Two-factor authentication confirmed on the owner's GitHub account.
- [ ] Checklist saved in `docs/security-checklist.md` (reused in M5-04).

## Notes

_Add decisions, links and anything learned while doing the task._
