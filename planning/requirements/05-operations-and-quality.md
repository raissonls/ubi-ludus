# Requirements: Operations and quality

Source: [PRD section 6.5](../../docs/PRD.md). The PRD is the source of truth; if it changes, update this file.
Which tasks implement each requirement is in [traceability](../traceability.md).

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-50 | M | A scheduled GitHub Actions workflow runs the full pipeline daily (fetch → normalise → enrich → validate → build → deploy → e-mail). | Scheduled run at 09:00 UTC (06:00 BRT); manual trigger available (`workflow_dispatch`). |
| FR-51 | M | Failure notification to the owner (GitHub notification and/or e-mail). | A forced failure produces a notification within 15 minutes. |
| FR-52 | M | **Keep-alive** so GitHub does not disable the scheduled workflow after 60 days without repository activity. | Documented mechanism, verified by a dry-run. |
| FR-53 | M | CI on every pull request: lint, type-check, unit tests, schema validation, secret scan, front-end accessibility and Lighthouse checks. | Required status checks block merging. |
| FR-54 | S | Structured logs and a small `status.json` (last success, record counts, unknown ratio) published with the site. | Used by FR-30 and by the success metrics. |
