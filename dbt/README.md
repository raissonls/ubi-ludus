# dbt project

The transformation and data-quality layer of the pipeline. Python loads raw data into a DuckDB file, dbt turns it into the published shape and tests it, and Python exports and validates the result. The reasons are in [ADR-002](../docs/adr/ADR-002-dbt-duckdb.md).

## Layers

| Layer | Folder | Materialized as | What lives here |
|---|---|---|---|
| **raw** | not in dbt | tables `raw_*` | Loaded by Python from provider responses, YAML and JSON. Never published as they are. Declared in `models/staging/_sources.yml`. |
| **staging** | `models/staging/` | views | One model per raw table: type, rename, nothing else. Named `stg_<thing>`. |
| **intermediate** | `models/intermediate/` | views | Matching team names, merging providers, windows, rights rules. Named `int_<verb>_<thing>`. |
| **marts** | `models/marts/` | tables | One model per published file, shaped like its schema in `schemas/`. Named after the file, for example `teams`. |

Everything lives in one DuckDB schema (`main`), so layers are told apart by prefix and folder, not by schema.

## Conventions

- **Tests live next to the models** in a `_<layer>.yml` file. Every model has a unique and not-null test on its key, and every reference to another model has a `relationships` test.
- **Generic tests take their parameters under `arguments:`** (the older bare form is deprecated):

  ```yaml
  - relationships:
      arguments:
        to: ref('teams')
        field: id
  ```

- **A mart must match its schema.** dbt tests check consistency between tables; the JSON Schema checks the published shape. Python runs the schema check when it exports, so both must pass.
- **Avoid SQL keywords as column names** (`primary`, `inner`, `order`). Where a published field has such a name, use a struct literal such as `{'primary': color_primary}`.
- **No secrets in this folder.** The profile only points at a local file.

## How provider matches become `matches.json`

```text
raw_provider_responses  -> stg_football_data_matches ┐
                        -> stg_api_football_matches  ┴-> int_matches_normalised
raw_teams               -> stg_teams -> stg_team_aliases -> int_team_name_keys
int_matches_normalised + int_team_name_keys -> int_match_sides -> int_unmapped_teams
int_matches_normalised + int_match_sides    -> int_matches
int_matches                                 -> int_matches_merged   (one row per real match)
raw_previous_matches    -> stg_previous_matches
int_matches_merged + stg_previous_matches   -> int_matches_flagged
raw_rights_rules        -> stg_rights_rule_broadcasters ┐
int_matches_merged                                      ┴-> int_rule_broadcasts -> int_broadcasts
raw_broadcasters        -> stg_broadcasters  (the catalogue ids that rules must use)
int_matches_flagged + int_broadcasts + stg_competitions -> matches   (window, unmapped teams, broadcasts)
raw_competitions        -> stg_competitions  -> competitions
```

- **One staging model per provider** (`stg_<provider>_matches`) translates that provider's codes (statuses, stages) into ours. A new provider adds its own staging model and one line in `int_matches_normalised`. An unknown provider status fails the build on purpose, so it gets translated deliberately.
- **API-Football** sends one response per day with the fixtures of every league, so `stg_api_football_matches` finds the competition by league id in `config/competitions.yml` and drops other leagues. Its status codes are translated like football-data.org's (an unknown one fails `accepted_values`). `TBD` fixtures (day known, time not) wait until the provider has a time. Its season is the year it starts in, which reads right for competitions inside a calendar year; a European league served only by API-Football would need a season rule. A round reads `"Regular Season - 33"` as `"33"` and a knockout label as a slug (`"quarter-finals"`).
- **One match, two providers** (`int_matches_merged`): two rows are the same match when, in one competition, the home and away team ids are equal in the same order and the kickoffs are less than 24 hours apart. The copy of the better-ranked provider is kept (`provider_rank`: football-data.org 1, API-Football 2), so its id, status and kickoff are the ones published. The comparison uses *our* team ids, so the providers may spell clubs differently; a spelling we cannot map is held back instead of duplicated. A match with an undecided team has no ids to compare and is not merged. A match whose winning provider changes from one run to the next changes id, so it cannot be flagged as rescheduled that day. The `no_match_is_listed_twice` test warns about any pair that slipped through.
- **Rights** (`int_rule_broadcasts`, `int_broadcasts`): Python loads `data/rights/` into `raw_rights_rules`, `raw_broadcasters` and `raw_services` (`load_rights_tables`). A rule covers a match of the same competition and season whose Brazil date is inside `valid_from..valid_to` (both included) and whose scope fits (`all`, `round`/`stage` equal to the match's round, `team` on either side). Rights add up: all covering rules contribute, a broadcaster is listed once. Each broadcast is tagged `rule`; a match no rule covers gets one `unknown` row with no broadcaster (FR-12, FR-13). Overrides (`confirmed`) come in M2-03. Rules and the catalogue are described for the owner in [data/rights/README.md](../data/rights/README.md).
- **dbt unit tests** (`models/intermediate/_unit_tests.yml`) give rows in and expect rows out, for rule matching, both ends of a validity window, a deal that changes hands on a given day, and the unknown fallback. They run in every `dbt build`, so a change that breaks them stops the pipeline.
- **Match ids** are `<provider>-<provider match id>` (for example `football-data-910001`). They stay the same when a match is rescheduled.
- **Team mapping** compares the provider's team name and short name with every name of every team (`name`, `short_name`, `aliases`), ignoring case, accents and punctuation (`name_key` macro). A slot ends up `mapped`, `undecided` (the provider has no team yet, so the id stays null), `unmapped` or `ambiguous`.
- **Unmapped and ambiguous teams never stop the pipeline.** The match is held back from `matches.json`, and the `unmapped_teams_are_reported` test warns with the provider's spelling. The fix is to add that spelling to the team's `aliases`. A name that fits two teams is never guessed.
- **Times are stored in UTC.** `int_matches` adds the local date and time using the `display_timezone` variable (`America/Sao_Paulo`, an IANA name, so any daylight saving rule applies). They are for the pipeline (daily e-mail, windows), not published.
- **The window** (FR-04) is applied in the `matches` mart: local dates from yesterday through `horizon_days` ahead. The horizon is the longest one among a competition's sources in `config/competitions.yml` (14, or 1 for API-Football-only competitions). The `matches_are_inside_their_window` test guards it.
- **Rescheduled matches** (FR-05): Python loads the previously published `matches.json` into `raw_previous_matches` (`fetch_previous_matches` downloads it and returns `None`, with a warning, if it cannot). `int_matches_flagged` compares kickoffs. A changed kickoff stamps the match with the run time, the stamp is carried from file to file, and the match shows as `rescheduled` for 48 hours (`reschedule_flag_hours`). Only a match the provider still calls `scheduled` is flagged; postponed, cancelled, live and finished keep their own status. Without a previous file nothing is flagged.
- **The clock is a variable.** `run_dbt()` passes `today` (Brazil's date) and `run_at` (UTC) to the models, so SQL never reads the machine clock and tests can fix the time.
- **Rounds** are the matchday for league-style stages (`"34"`) and the stage for knockouts (`"final"`, `"last-16"`).

## Running it

From Python, which is how the pipeline does it (see `src/ubi_ludus/pipeline/dbt_runner.py`):

```python
from pathlib import Path

from ubi_ludus.pipeline.dbt_runner import run_dbt
from ubi_ludus.pipeline.warehouse import connect, load_yaml_file

database = Path("dbt/target/ubi_ludus.duckdb")  # git-ignored
con = connect(database)
load_yaml_file(con, "raw_teams", Path("data/teams.yml"), key="teams")
con.close()
run_dbt(database)  # raises DbtBuildError when a model or test fails
```

Or with the dbt command line, after loading the raw tables:

```bash
cd dbt
UBI_LUDUS_DB=target/ubi_ludus.duckdb dbt build --profiles-dir . \
  --vars '{"today": "2026-11-02", "run_at": "2026-11-02T09:00:00Z"}'
```

The database file, `dbt/target/` and `dbt/logs/` are git-ignored.

## Tests

`tests/unit/test_dbt_foundation.py` builds this project on small hand-written fixtures in `tests/fixtures/dbt/`. It runs inside the normal `pytest` run, so CI fails a pull request when a dbt model or test fails. To run only those tests: `pytest -m dbt`.

A deliberately broken fixture (two teams sharing one alias) proves that a failing dbt test stops the build.

## Adding a model

1. Put the SQL file in the right layer folder with the right prefix.
2. Add its tests to the `_<layer>.yml` next to it.
3. If it is a mart, make sure its columns match the schema in `schemas/`, then add an export function in `src/ubi_ludus/pipeline/export.py`.
4. Add a fixture and a test under `tests/`.
