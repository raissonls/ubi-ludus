# Requirements: Broadcast resolution

Source: [PRD section 6.2](../../docs/PRD.md). The PRD is the source of truth; if it changes, update this file.
Which tasks implement each requirement is in [traceability](../traceability.md).

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-10 | M | Maintain a **rights table** (`data/rights/rights.yml`) mapping *competition + season (+ optional round or stage)* to one or more broadcasters. | Table is human-readable YAML, validated by schema in CI, with `valid_from` / `valid_to` per rule. |
| FR-11 | M | Support **match-level overrides** (`data/rights/overrides.yml`) that win over rules. Overrides can add, replace or remove broadcasters. | Override precedence is covered by unit tests. |
| FR-12 | M | Tag every broadcast with a **confidence level**: `confirmed` (override or provider data), `rule` (from the rights table) or `unknown`. | The UI shows a different visual state for each level. No match is shown with a broadcaster without a confidence tag. |
| FR-13 | M | When nothing is known, show "Broadcast not confirmed yet" instead of guessing. | Matches with `unknown` never display a broadcaster name. |
| FR-14 | S | Produce a weekly **review report** (GitHub issue or Markdown artifact) listing matches of followed teams that are `unknown`, plus rights rules expiring within 30 days. | Report generated automatically every Thursday. |
| FR-15 | C | Optional lookups from secondary sources to propose overrides (never auto-applied). | Proposals appear only in the review report. |
