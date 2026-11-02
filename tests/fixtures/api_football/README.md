# API-Football test fixtures

Hand-written files in the same shape as the provider's responses, with made-up fixtures and a trimmed set of fields. They are **not** recordings of real responses: the provider's terms and our own rule (see the [provider comparison](../../../docs/research/provider-comparison.md)) say raw provider data stays out of this repository.

- `fixtures_day.json`: `fixtures?date=...` for one day. Three fixtures: Copa do Brasil (league 73), Sul-Americana (11) and a league we do not follow (999).
- `status.json`: the `status` endpoint, with 5 of the 100 daily requests used.
- `plan_error.json`: what the free plan answers (with HTTP 200) for a date outside yesterday-to-tomorrow.
