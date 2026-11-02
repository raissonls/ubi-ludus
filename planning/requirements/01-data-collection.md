# Requirements: Data collection

Source: [PRD section 6.1](../../docs/PRD.md). The PRD is the source of truth; if it changes, update this file.
Which tasks implement each requirement is in [traceability](../traceability.md).

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-01 | M | Fetch fixtures for the covered competitions from one or more free providers through a **provider adapter interface**. | Adding a provider requires only a new adapter module and a config entry. Unit tests run adapters against recorded fixtures (no live calls in CI). |
| FR-02 | M | Normalise provider data into the internal model ([section 8](../../docs/PRD.md#8-data-model)). | Output validates against the JSON Schema in `schemas/`. Invalid output fails the pipeline. |
| FR-03 | M | Respect provider rate limits and terms. Cache responses between runs. | Pipeline never exceeds the provider's documented rate limit. Total calls per run are logged. |
| FR-04 | M | Keep a rolling window of matches: yesterday through the next 14 days. | `matches.json` contains only matches in the window. |
| FR-05 | S | Detect and report postponed, rescheduled or cancelled matches. | A match whose kickoff changes between runs is flagged `rescheduled` for 48 hours. |
| FR-06 | M | Convert all times to **America/Sao_Paulo** for display; store UTC. | Test cases around midnight show the correct local date. |
