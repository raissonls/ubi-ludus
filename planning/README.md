# Planning

This folder turns the [PRD](../docs/PRD.md) into work you can do, in order. The PRD says *what* and *why*; this folder says *what to do next*.

```text
planning/
  README.md          this file: how it works and the task index
  traceability.md    which tasks implement which requirement (generated)
  requirements/      the PRD's requirements, split by area
  tasks/             one file per task, grouped by milestone (M0 to M5)
  tools/             build_index.py keeps the index and traceability up to date
```

## How to work

1. Open the current milestone in the index below and take the first task whose dependencies are `done`.
2. Set `status: in-progress` in the task's front matter.
3. Work through the **Definition of done** checklist, ticking boxes as you go. Write decisions and findings under **Notes**.
4. Set `status: done` when every box is ticked, then rebuild the index:

   ```bash
   python planning/tools/build_index.py
   ```

5. Commit the task file and the regenerated index together.

## Task file conventions

- **Name:** `M<milestone>-<nn>-<short-title>.md`, kept inside the milestone folder.
- **Front matter:** `id`, `title`, `milestone`, `priority`, `estimate_h`, `status`, `requirements`, `depends_on`.
- **Status:** `todo`, `in-progress`, `blocked` or `done`. Use `blocked` and say why in Notes.
- **Priority:** MoSCoW as in the PRD. If time runs short, cut **Should** tasks first, and **Could** items only live in [the backlog](../docs/backlog.md).
- **Requirements:** PRD IDs the task implements (FR for functional requirements, plus R risks, Q open questions, S success criteria and NFR areas). The traceability file is built from this.
- **Scope changes:** if the PRD changes, update the PRD first, then the requirement files and the affected tasks. New ideas that are not in the PRD go to the backlog, not into a task.

## Rules of thumb

- A task is small enough to finish in one or two sittings (1 to 5 hours). If a task grows, split it.
- If something is unclear, write it in Notes and raise it before building on it.
- Every **Must** requirement must have a task. `build_index.py` fails if one does not.

## Task index

<!-- INDEX:START -->

| Milestone | Window | Tasks | Done | Hours | Hours done |
|---|---|---|---|---|---|
| M0 Discovery spike | Nov 2-8 | 6 | 0 | 12 | 0 |
| M1 Data pipeline | Nov 9-15 | 6 | 0 | 18 | 0 |
| M2 Rights engine | Nov 16-22 | 5 | 0 | 16 | 0 |
| M3 Website core | Nov 23 - Dec 6 | 12 | 0 | 36 | 0 |
| M4 E-mail and operations | Dec 7-13 | 6 | 0 | 14 | 0 |
| M5 Hardening and launch | Dec 14-20 | 6 | 0 | 14 | 0 |
| **Total** | | **41** | **0** | **110** | **0** |

### M0 Discovery spike (Nov 2-8)

| ID | Task | Pri | Hours | Status | Depends on |
|---|---|---|---|---|---|
| M0-01 | [Provider comparison spike](tasks/M0-discovery/M0-01-provider-comparison-spike.md) | Must | 4 | todo | - |
| M0-02 | [Review provider terms of use](tasks/M0-discovery/M0-02-review-provider-terms-of-use.md) | Must | 2 | todo | M0-01 |
| M0-03 | [Repository scaffold and tooling](tasks/M0-discovery/M0-03-repository-scaffold-and-tooling.md) | Must | 2 | todo | - |
| M0-04 | [CI skeleton](tasks/M0-discovery/M0-04-ci-skeleton.md) | Must | 2 | todo | M0-03 |
| M0-05 | [ADR-001 architecture and docs skeleton](tasks/M0-discovery/M0-05-adr-001-architecture-and-docs-skeleton.md) | Must | 1 | todo | M0-01, M0-02 |
| M0-06 | [Visibility and repository security plan](tasks/M0-discovery/M0-06-visibility-and-repository-security-plan.md) | Must | 1 | todo | - |

### M1 Data pipeline (Nov 9-15)

| ID | Task | Pri | Hours | Status | Depends on |
|---|---|---|---|---|---|
| M1-01 | [JSON Schemas for the data model](tasks/M1-data-pipeline/M1-01-json-schemas-for-the-data-model.md) | Must | 2 | todo | M0-05 |
| M1-02 | [Provider adapter interface and config](tasks/M1-data-pipeline/M1-02-provider-adapter-interface-and-config.md) | Must | 3 | todo | M1-01 |
| M1-03 | [First provider adapter with recorded fixtures](tasks/M1-data-pipeline/M1-03-first-provider-adapter-with-recorded-fixtures.md) | Must | 4 | todo | M1-02, M0-01 |
| M1-04 | [Normalisation, team mapping and time handling](tasks/M1-data-pipeline/M1-04-normalisation-team-mapping-and-time-handling.md) | Must | 4 | todo | M1-03 |
| M1-05 | [Response cache, rate limiting and call logging](tasks/M1-data-pipeline/M1-05-response-cache-rate-limiting-and-call-logging.md) | Must | 2 | todo | M1-03 |
| M1-06 | [Rolling window and reschedule detection](tasks/M1-data-pipeline/M1-06-rolling-window-and-reschedule-detection.md) | Must | 3 | todo | M1-04 |

### M2 Rights engine (Nov 16-22)

| ID | Task | Pri | Hours | Status | Depends on |
|---|---|---|---|---|---|
| M2-01 | [Rights schemas and broadcaster/service catalogue](tasks/M2-rights-engine/M2-01-rights-schemas-and-broadcaster-service-catalogue.md) | Must | 3 | todo | M1-01 |
| M2-02 | [Rights resolution engine](tasks/M2-rights-engine/M2-02-rights-resolution-engine.md) | Must | 4 | todo | M2-01, M1-06 |
| M2-03 | [Match-level overrides](tasks/M2-rights-engine/M2-03-match-level-overrides.md) | Must | 2 | todo | M2-02 |
| M2-04 | [Curate initial rights data and owner config](tasks/M2-rights-engine/M2-04-curate-initial-rights-data-and-owner-config.md) | Must | 4 | todo | M2-01 |
| M2-05 | [Weekly review report](tasks/M2-rights-engine/M2-05-weekly-review-report.md) | Should | 3 | todo | M2-02 |

### M3 Website core (Nov 23 - Dec 6)

| ID | Task | Pri | Hours | Status | Depends on |
|---|---|---|---|---|---|
| M3-01 | [Site scaffold, design tokens, themes and security baseline](tasks/M3-website-core/M3-01-site-scaffold-design-tokens-and-themes.md) | Must | 4 | todo | M1-01 |
| M3-02 | [Data loading and preferences store](tasks/M3-website-core/M3-02-data-loading-and-preferences-store.md) | Must | 3 | todo | M3-01 |
| M3-03 | [Onboarding: teams picker](tasks/M3-website-core/M3-03-onboarding-teams-picker.md) | Must | 4 | todo | M3-02 |
| M3-04 | [Onboarding: services picker](tasks/M3-website-core/M3-04-onboarding-services-picker.md) | Must | 2 | todo | M3-02 |
| M3-05 | [Match card component and all states](tasks/M3-website-core/M3-05-match-card-component-and-all-states.md) | Must | 5 | todo | M3-02 |
| M3-06 | [Home views: today, this week, my teams](tasks/M3-website-core/M3-06-home-views-today-this-week-my-teams.md) | Must | 4 | todo | M3-05, M3-03 |
| M3-07 | [Watchable with my services](tasks/M3-website-core/M3-07-watchable-with-my-services.md) | Must | 2 | todo | M3-04, M3-05 |
| M3-08 | [Freshness indicator and report-a-problem link](tasks/M3-website-core/M3-08-freshness-indicator-and-report-a-problem-link.md) | Must | 2 | todo | M3-02 |
| M3-09 | [Filters and shareable URL state](tasks/M3-website-core/M3-09-filters-and-shareable-url-state.md) | Should | 3 | todo | M3-06 |
| M3-10 | [Loading, offline, empty and error states](tasks/M3-website-core/M3-10-loading-offline-empty-and-error-states.md) | Must | 3 | todo | M3-02 |
| M3-11 | [Live-now indicator and kickoff countdown](tasks/M3-website-core/M3-11-live-now-indicator-and-kickoff-countdown.md) | Should | 2 | todo | M3-05 |
| M3-12 | [Add to calendar (.ics)](tasks/M3-website-core/M3-12-add-to-calendar-ics.md) | Should | 2 | todo | M3-05 |

### M4 E-mail and operations (Dec 7-13)

| ID | Task | Pri | Hours | Status | Depends on |
|---|---|---|---|---|---|
| M4-01 | [Daily e-mail rendering](tasks/M4-email-and-operations/M4-01-daily-e-mail-rendering.md) | Must | 4 | todo | M2-02, M1-06 |
| M4-02 | [E-mail sending, secrets and skip logic](tasks/M4-email-and-operations/M4-02-e-mail-sending-secrets-and-skip-logic.md) | Must | 3 | todo | M4-01 |
| M4-03 | [Daily pipeline workflow and Pages deploy](tasks/M4-email-and-operations/M4-03-daily-pipeline-workflow-and-pages-deploy.md) | Must | 3 | todo | M1-06, M2-02, M4-02 |
| M4-04 | [Failure alerts and keep-alive](tasks/M4-email-and-operations/M4-04-failure-alerts-and-keep-alive.md) | Must | 2 | todo | M4-03 |
| M4-05 | [Status file and structured logs](tasks/M4-email-and-operations/M4-05-status-file-and-structured-logs.md) | Should | 1 | todo | M1-06, M4-03 |
| M4-06 | [Runbook](tasks/M4-email-and-operations/M4-06-runbook.md) | Must | 1 | todo | M4-04 |

### M5 Hardening and launch (Dec 14-20)

| ID | Task | Pri | Hours | Status | Depends on |
|---|---|---|---|---|---|
| M5-01 | [Accessibility audit and fixes](tasks/M5-hardening-and-launch/M5-01-accessibility-audit-and-fixes.md) | Must | 3 | todo | M3-12 |
| M5-02 | [Performance tuning](tasks/M5-hardening-and-launch/M5-02-performance-tuning.md) | Must | 3 | todo | M3-12 |
| M5-03 | [Usability sessions](tasks/M5-hardening-and-launch/M5-03-usability-sessions.md) | Must | 3 | todo | M5-01 |
| M5-04 | [Security checklist sign-off](tasks/M5-hardening-and-launch/M5-04-security-checklist-sign-off.md) | Must | 2 | todo | M0-06, M4-04 |
| M5-05 | [Provider outage drill](tasks/M5-hardening-and-launch/M5-05-provider-outage-drill.md) | Must | 1 | todo | M4-06 |
| M5-06 | [Launch and start the 14-day measurement](tasks/M5-hardening-and-launch/M5-06-launch-and-start-the-14-day-measurement.md) | Must | 2 | todo | M5-01, M5-02, M5-03, M5-04, M5-05 |

<!-- INDEX:END -->
