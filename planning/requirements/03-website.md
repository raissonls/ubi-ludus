# Requirements: Website

Source: [PRD section 6.3](../../docs/PRD.md). The PRD is the source of truth; if it changes, update this file.
Which tasks implement each requirement is in [traceability](../traceability.md).

| ID | Pri | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-20 | M | **Onboarding: "Which teams do you follow?"** First-time visitors see a friendly picker with type-ahead search and multi-select. | A new visitor can select teams and see their matches in ≤ 3 interactions. Works with keyboard and screen reader. |
| FR-21 | M | **Onboarding: "Which services do you have?"** Visitors select their subscriptions (for example free TV only, pay TV, specific streaming services). | Matches show whether they are watchable with the visitor's services. |
| FR-22 | M | Preferences are stored **only in the visitor's browser** (`localStorage`). They can be edited or cleared at any time. | No network request carries preferences. A "Reset my data" control exists. |
| FR-23 | M | **Home view**: "Today", "This week" and "Next matches of my teams", with followed teams highlighted and other notable matches below. | Followed-team matches always appear before other matches. |
| FR-24 | M | Each match card shows: teams, competition, local kickoff time, broadcaster badges and confidence state. | Visual regression snapshots cover all states (confirmed, rule, unknown, live, finished). |
| FR-25 | M | Mark broadcasters the visitor **can access** with their services; highlight matches they cannot watch. | Filter "only what I can watch" works and persists. |
| FR-26 | S | **Live-now** indicator and kickoff countdown. | Updates without page reload; correct around kickoff. |
| FR-27 | S | Filters by competition and broadcaster; free-text team search. | Filters combine (AND) and are reflected in the URL. |
| FR-28 | S | **Add to calendar** (`.ics`) per match and for all followed teams. | Generated file imports into Google Calendar and Apple Calendar. |
| FR-29 | S | Shareable view via URL parameters (teams and services), without personal data. | Opening the link reproduces the same view on another device. |
| FR-30 | M | Visible **data freshness** indicator ("Updated today at 06:12") and a link to report a wrong broadcast (pre-filled GitHub issue). | Indicator turns to a warning state if data is older than 36 hours. |
| FR-31 | M | Light and dark themes; respect `prefers-color-scheme` and `prefers-reduced-motion`. | Manual verification plus automated accessibility checks. |
| FR-32 | M | Clear, graceful states for loading, offline, empty data and errors. | Each state has a designed screen and a test. |
| FR-33 | C | Installable PWA with offline cache of the last data. | Passes PWA installability checks. |
