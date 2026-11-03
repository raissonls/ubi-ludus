# Data

Hand-edited files that the pipeline reads. Everything here is checked in CI, so a typo fails the pull request instead of reaching the site.

| Path | What it is |
|---|---|
| `teams.yml` | The teams we show: ids, names, aliases, country and two colours |
| `rights/` | Who broadcasts what: see [rights/README.md](rights/README.md) |

## `teams.yml`

A **whitelist**. A match is published only when both of its teams are in this file. A match with a team that is not here is held back and reported (`unmapped_teams_are_reported`, and the weekly review), so the site never shows a name we did not choose.

```yaml
- id: sao-paulo                 # lower case, letters, digits and hyphens; used everywhere else
  name: "São Paulo"             # shown on the site
  short_name: "São Paulo"       # shown where space is short
  aliases: ["São Paulo FC"]     # every other spelling a provider uses
  country: "BR"                 # always in quotes (see below)
  colors: {primary: "#FE0000", secondary: "#000000"}
```

- **Aliases are how providers are matched.** football-data.org and API-Football spell clubs differently ("CA Mineiro" and "Atletico-MG" are Atlético Mineiro). Case, accents and punctuation do not matter, so `Sao Paulo` and `São Paulo` are the same. Two teams must never share a spelling; a test checks it.
- **To add a team** when the report shows an unmapped name: add the team, or add that exact spelling to the right team's `aliases`.
- **Colours** are text only: no crests or logos (PRD R5). They are the club's two main colours as known, not taken from a provider; white counts. Check them before the site relies on them.
- **`country`** is an ISO 3166-1 alpha-2 code, or `GB-ENG` for England. **Keep it in quotes**: YAML reads a bare `NO` (Norway) as the boolean false.
- Ids in `config/owner.yml` must exist here; a test checks that too.

The first version (2026-11-02) came from a real run: every team that plays in the next 14 days in the competitions of `config/competitions.yml`, the 20 Série A clubs, the cup clubs most likely to appear, and the owner's six teams. Teams of a cup draw or a promotion are added when the report shows them.
