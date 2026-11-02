---
id: M0-04
title: CI skeleton
milestone: M0
priority: Must
estimate_h: 2
status: todo
requirements: [FR-53, S10, R7]
depends_on: [M0-03]
---

# M0-04 · CI skeleton

**Milestone:** M0 Discovery spike (Nov 2-8) · **Priority:** Must · **Estimate:** 2 h

## Why

Pull requests must be checked automatically from the beginning. Front-end checks (accessibility, Lighthouse) are added later when the site exists (M3-01, M5-02).

## Definition of done

- [ ] `.github/workflows/ci.yml` runs lint, type-check and unit tests on every pull request.
- [ ] Secret scan step (for example gitleaks) runs in CI.
- [ ] Workflow `permissions:` set to the minimum; third-party actions pinned to commit SHAs.
- [ ] Dependabot configured for GitHub Actions and Python.
- [ ] A deliberately failing check was tried once to confirm CI blocks it.

## Notes

_Add decisions, links and anything learned while doing the task._
