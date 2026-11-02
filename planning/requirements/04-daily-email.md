# Requirements: Daily e-mail

Source: [PRD section 6.4](../../docs/PRD.md). The PRD is the source of truth; if it changes, update this file.
Which tasks implement each requirement is in [traceability](../traceability.md).

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-40 | M | Send one e-mail per day, in the morning, listing today's matches of the owner's teams first and notable matches after, with broadcasters, kickoff times (BRT) and a "watchable with my services" marker. | E-mail is sent by 08:00 BRT on at least 95% of days over a rolling 30-day window. |
| FR-41 | M | Owner preferences (teams, services, e-mail template options) live in `config/owner.yml`. The **e-mail address and credentials are GitHub Secrets**, never in the repo. | Secret scanning finds nothing; a missing secret fails the job with a clear message. |
| FR-42 | S | Skip the e-mail on days with no relevant matches, or send a short "no matches today" note (configurable). | Configurable flag with tests for both behaviours. |
| FR-43 | S | Plain-text alternative and an HTML layout that renders correctly in Gmail (web and mobile) and Apple Mail. | Checked manually with two clients before launch. |
| FR-44 | C | Alert when a match already included in a sent e-mail changes time or broadcaster. | Alert sent at most once per change. |
