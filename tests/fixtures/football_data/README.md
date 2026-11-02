# football-data.org test fixtures

Hand-written files in the same shape as the provider's `competitions/{code}/matches` response, with made-up teams and competitions. They are **not** recordings of real responses: the provider's terms and our own rule (see the [provider comparison](../../../docs/research/provider-comparison.md)) say raw provider data stays out of this repository.

- `matches.json`: one finished and one scheduled match.
- `matches_teams_undecided.json`: a final whose teams are not decided yet. The provider sends `null` for every team field in that case.
