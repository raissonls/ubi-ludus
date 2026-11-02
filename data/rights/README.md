# Rights data

The files in this folder are edited by hand. They say **who can show a match in Brazil**. The pipeline reads them, checks them, and the site shows the result with how sure we are (PRD FR-10 to FR-13).

| File | What it holds | Who edits it |
|---|---|---|
| `broadcasters.yml` | Every channel, app and YouTube channel that can carry a match | when a new one appears |
| `services.yml` | The subscriptions a visitor can say they have, and which broadcasters each one includes | when a plan changes |
| `rights.yml` | The rights table: which broadcasters carry which competition, for which matches, and until when | every time a deal is announced |
| `overrides.yml` | Corrections for single matches | when one match is different from its rule |

Every file starts with `version: 1` and is checked against a schema in [`schemas/`](../../schemas/README.md) on every pull request. A typo fails the check with the file name and the place, so it never reaches the site. The checks across files are in `src/ubi_ludus/pipeline/rights.py`.

`broadcasters.yml` and `services.yml` are a **draft** until the owner checks them in M2-04. They only say what exists. They do not say who has the rights to what.

## Free, paid and "can I watch it?"

A visitor can watch a broadcaster when:

- it is **free**: `service_id: null` in `broadcasters.yml` (free TV, YouTube); or
- one of the visitor's **services** lists it in `includes_broadcasters`.

The two files must agree, and the check enforces it:

- a broadcaster with a `service_id` must be listed by that service;
- a broadcaster with `service_id: null` must not be listed by any service;
- a broadcaster may be listed by several services (ESPN is on pay TV and in Disney+).

Services are coarse on purpose, one entry per "I have X". Plans that include different things are separate entries (`globoplay` and `globoplay-canais`).

## Writing a rule (`rights.yml`)

```yaml
rules:
  - competition_id: brasileirao-serie-a   # an id from config/competitions.yml
    season: "2026"                        # as matches carry it: 2026 or 2026-27
    scope: all                            # all | round | stage | team
    broadcasters: [globo, sportv]         # ids from broadcasters.yml
    valid_from: 2026-01-28                # first day, inclusive, Brazil's calendar
    valid_to: 2026-12-31                  # last day, inclusive
    source: "Where you learned it, and when"
```

- **`scope`** says which matches of that competition and season the rule covers:
  - `all`: every match. Leave `scope_value` out.
  - `round`: one matchday. `scope_value: 33`.
  - `stage`: one knockout stage, as the match carries it. `scope_value: final` or `quarter-finals`.
  - `team`: the matches one team plays. `scope_value: flamengo` (a team id).
- **`valid_from` / `valid_to`** are real calendar days and both are required. A match is covered when its local date is inside them. Use the season's last day if you do not know when a deal ends.
- **`source`** is required: an announcement, a page, who told you. Next month you will want to know.
- **`notes`** is optional.
- Dates need no quotes. Seasons do (`"2026"`), or YAML turns them into a number.

### How the engine uses the rules

For each match, every rule that covers it counts: same competition and season, the match's local date (Brazil) between `valid_from` and `valid_to` (both included), and a scope that fits. **Rights add up**: the match gets the broadcasters of all the rules that cover it, each listed once. A rule never takes another rule's broadcasters away.

- Write the broadcasters every match of a competition has in an `all` rule. Add `round`, `stage` and `team` rules for what only some matches have.
- A `team` rule covers the matches that team plays at home or away. A match between two teams with their own rules gets both.
- When a deal changes hands in mid-season, write two rules with consecutive dates (to 30 June, from 1 July).
- When a match is the exception ("only on SporTV this time"), do not bend the rules. Write an override (M2-03).

Each broadcast in `matches.json` says how sure we are:

| `confidence` | Meaning | Where it comes from |
|---|---|---|
| `rule` | the rights table says so | a rule in `rights.yml` |
| `confirmed` | someone checked this match | an override (M2-03) |
| `unknown` | nothing is known; no broadcaster is named | no rule covers the match |

A match no rule covers carries a single `unknown` broadcast, and the site shows "Broadcast not confirmed yet" (FR-13). The pipeline checks that an `unknown` never carries a broadcaster and never sits next to one.

## Writing an override (`overrides.yml`)

```yaml
overrides:
  - match_id: football-data-910001
    action: replace                       # add | replace | remove
    broadcasters: [sportv]
    reason: "Moved to SporTV only, announced by Globo on 2026-11-01"
    added_at: 2026-11-01
```

- **`add`**: these broadcasters also carry the match.
- **`replace`**: only these broadcasters carry it.
- **`remove`**: these broadcasters do not carry it.
- `reason` and `added_at` are required. Remove an override once the match is played.

## Checking your changes

```bash
pytest tests/unit/test_rights.py
```

It loads the real files and prints every problem at once, for example `rights.yml, rule 3 (brasileirao-serie-a 2026): broadcaster 'ghost' is not in broadcasters.yml`.
