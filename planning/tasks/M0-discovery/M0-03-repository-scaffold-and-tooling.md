---
id: M0-03
title: Repository scaffold and tooling
milestone: M0
priority: Must
estimate_h: 2
status: todo
requirements: [FR-53, NFR-maintainability]
depends_on: []
---

# M0-03 · Repository scaffold and tooling

**Milestone:** M0 Discovery spike (Nov 2-8) · **Priority:** Must · **Estimate:** 2 h

## Why

Give the project a consistent base so every later task starts from the same tooling.

## Definition of done

- [ ] Directory layout from PRD section 9 created (`src/`, `site/`, `data/`, `schemas/`, `tests/`, `config/`).
- [ ] Python 3.12 project file with ruff (lint and format), mypy (type-check) and pytest configured.
- [ ] Pre-commit hooks installed (format, lint, secret scan).
- [ ] Open-source licence chosen by the owner (for example MIT or Apache-2.0) and `LICENSE` added.
- [ ] `CONTRIBUTING.md` stub and a short top-level `README.md` describing how to run the tooling.

## Notes

_Add decisions, links and anything learned while doing the task._
