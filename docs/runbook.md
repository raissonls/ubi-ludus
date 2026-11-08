# Runbook

How to look after Ubi Ludus, for the owner. The goal is **under 30 minutes a week** (PRD S11). Everything here uses things the project already has; when a step needs a command it is written out, and where a step has not been tried for real it says so.

**In a hurry?**

| What you see | Go to |
| --- | --- |
| An issue "Daily pipeline failed" (label `pipeline-failure`) | [When something is red](#when-something-is-red) |
| An issue "Published data is stale" (label `stale-data`) | [When something is red](#when-something-is-red) |
| A key or password may have leaked | [Rotating a leaked secret](#rotating-a-leaked-secret) |
| A provider is down, cut a competition or suspended you | [Switching provider](#switching-provider) |
| You want the e-mail to stop | [Disabling the e-mail](#disabling-the-e-mail) |
| The site shows something wrong that was just published | [Rolling back the site](#rolling-back-the-site) |
| It is Thursday | [The weekly routine](#the-weekly-routine) |

## What runs, and where

| What | Where |
| --- | --- |
| The site | https://raissonls.github.io/ubi-ludus/ (GitHub Pages, deployed by the pipeline) |
| Daily pipeline | `.github/workflows/pipeline.yml`, 09:00 UTC (06:00 in Brazil): build, deploy, e-mail, alert. See [pipeline.md](pipeline.md). |
| Watchdog | `.github/workflows/watchdog.yml`, 11:00 UTC: keeps the schedules switched on and checks the data is fresh |
| Weekly review | `.github/workflows/review-report.yml`, Thursdays 12:00 UTC: opens an issue labelled `review` |
| Rules, overrides, teams | `data/rights/`, `data/teams.yml`, `config/` |
| Logs | the run pages under *Actions*; how to read them is in [pipeline.md](pipeline.md#the-logs-fr-54-fr-03) |

Changes to the repository go through a pull request: `main` is protected and needs the two checks (*Lint, types and tests* and *Secret scan*) to pass. Allow about ten minutes for a small fix.

## The weekly routine

About 30 minutes, on Thursday after the review issue appears:

1. **Look for alerts (2 min).** *Issues* with the labels `pipeline-failure` and `stale-data`. There should be none open. If there is one, handle it first.
2. **The review issue (10 to 15 min).** Open the newest issue labelled `review`. It lists:
   - *Unknown matches of your teams*: write an override for each one you can find out (`data/rights/overrides.yml`, format in [data/rights/README.md](../data/rights/README.md#writing-an-override-overridesyml)). Each entry has the match id to use.
   - *Rights rules ending within 30 days*: renew or replace them in `data/rights/rights.yml` before they end, or their matches silently become unknown.
   - *Rules that ended without a replacement*: a competition has lost its rule.
   Open a pull request with the change. `pytest tests/unit/test_rights.py` checks it and prints every problem at once. The next daily run publishes it.
3. **The audit (10 min).** After the matches are played, pick at least **10 matches of your teams** and check each one's broadcaster on the official source (club, league or broadcaster page) against what the site said. Write the result in `docs/audits/YYYY-MM-DD.md` (a table to copy is in [docs/audits](audits/README.md)): match, what the site said, what was true, right or wrong. The target is at least **85% right** (PRD S1). A wrong one is either an override (this week) or a rule that needs changing (note it).
4. **Dependabot (3 min).** Merge the pull requests it opened once their checks are green. Read what the update says if it is more than a patch number.
5. **The e-mail (1 min).** Did the morning e-mail arrive, and not in spam? If the site and the e-mail disagree, the site is right.

Once a month, also: re-read the providers' terms before any change that could affect them (ads, paid features, crests; see the [provider comparison](research/provider-comparison.md)), and check that GitHub still lists all your scheduled workflows as active: `gh workflow list --all`.

## Running the pipeline on your machine

Needs Python 3.12 and a `.env` file with the provider key and, to send e-mail, the mail secrets (`.env.example` lists the names; `.env` is git-ignored and never leaves your machine).

```bash
python -m pip install -e ".[dev]"
```

Run the whole thing (fetches, runs `dbt build`, exports and checks the five files), writing to a folder of your choice:

```bash
python -m ubi_ludus.pipeline.publish --run --require-all-providers --out site/data
```

It uses one call per competition to football-data.org, about 9 a run, and writes nothing if it fails. Without `--run` it only re-exports from a warehouse that already exists (`dbt/target/ubi_ludus.duckdb`). Add `--cache-dir .cache` to reuse answers for an hour while you experiment.

See the site with that data:

```bash
python -m http.server -d site 8000
```

then open http://localhost:8000/. To see the e-mail it would send, without sending it: `python -m ubi_ludus.email.send --dry-run` (and `python -m ubi_ludus.email.render` writes the HTML to look at).

### Reading a failing dbt test

`dbt build` runs inside the command above. When a model or a data test fails, the run stops before anything is written and says which:

```
error: dbt build failed: no_match_is_listed_twice
```

The names are those of the tests in `dbt/tests/` and the `_*.yml` files next to the models. Read the one that failed, then the detail in `dbt/logs/dbt.log` (search for the test's name). Some tests only **warn**: they never stop a run, they are for you to act on in the weekly routine, and they show up in `dbt/logs/dbt.log` and in the dbt output when you run it yourself.

| Test | Stops the run? | What it means | Fix |
| --- | --- | --- | --- |
| `unmapped_teams_are_reported` | warns | a provider spells a club in a way `data/teams.yml` does not know; the match is **left out of the site** | add that spelling to the team's `aliases` in `data/teams.yml` (the warning prints it) |
| `no_match_is_listed_twice` | warns | two matches of one competition with the same teams in the same order and kickoffs under a day apart: one match listed twice | usually two spellings of one club (an alias); the merge should have joined them |
| `overrides_for_matches_we_no_longer_have` | warns | an override whose match is no longer in the data | delete the override: the match was played, or the provider changed its id |
| `every_published_match_has_a_broadcast` | **stops** | a match has no broadcast at all, or lists the same broadcaster twice: a model upstream is broken | look at the last change to `dbt/models/` or to `data/rights/` |
| `unknown_broadcasts_name_no_broadcaster` | **stops** | a match "nothing known about" got a broadcaster, or a broadcast names one without saying how sure we are (FR-13) | the same: the rights or override logic |
| `rescheduled_matches_carry_their_stamp` | **stops** | a match is marked rescheduled without a rescheduled time, or the other way round | a change to the reschedule model |
| `matches_are_inside_their_window` | **stops** | a published match is outside its competition's window (yesterday to `horizon_days` ahead) | the mart and the test disagree: someone changed one of them, or a competition's `horizon_days` in `config/competitions.yml` |
| a `unique`, `not_null`, `relationships` or `accepted_values` test in a `_*.yml` file | **stops** | the data does not have the shape the model promises (for example two teams sharing an alias, or a match pointing to a team that is not listed) | the message names the model and column; fix the file it comes from (`data/teams.yml`, `data/rights/`, `config/`) |

To run dbt on its own, with the dates given by hand (instructions and an example are in [dbt/README.md](../dbt/README.md#running-it)). To run only the dbt tests of the project: `pytest -m dbt`.

## Rotating a leaked secret

**A secret is leaked if it has been in a commit, an issue, a log, a screenshot or a message, even for a minute.** Treat it as public. The order matters: **revoke first, replace second, clean last.**

| Secret | What it is | Revoke and create anew |
| --- | --- | --- |
| `FOOTBALL_DATA_TOKEN` | the football-data.org API token | football-data.org, in your account: get a new token and make sure the old one no longer works (look at their account page or write to them: I have not tried it) |
| `SMTP_PASSWORD` (and `SMTP_USER`) | Brevo's SMTP key and login | Brevo, *SMTP & API*, *SMTP keys*: delete the key, generate a new one. The login rarely changes. |
| `EMAIL_FROM`, `EMAIL_TO` | addresses, private but not credentials | nothing to revoke. If one leaked, you can only change the address (a new verified sender in Brevo, or another inbox). |
| your GitHub login | access to the repository | change the password, check *Settings, Security log*, and remove tokens you do not recognise (the two-factor setting stays on) |

1. **Revoke** it at the provider, as in the table. From this moment the leaked value is useless.
2. **Replace** it. Each command asks for the new value, so it never goes into your shell history:

   ```bash
   gh secret set FOOTBALL_DATA_TOKEN
   ```

   Do the same for the others (`SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`) and update your local `.env`.
3. **Prove it works:** run the pipeline by hand without the e-mail, then once with it:

   ```bash
   gh workflow run pipeline.yml -f send_email=false
   ```

4. **Clean up.** If it was in a commit: removing it in a new commit does not remove it from history, which is public. The old value is revoked, so history holding it is harmless; do not rewrite `main`. If it was in an issue or a comment, edit it out. GitHub's secret scanning and push protection, and the *Secret scan* check, are there to stop this before it happens: if one of them reported something, read it as an instruction.
5. **Look for use you did not make.** The provider's dashboard (calls) and Brevo's statistics (e-mails sent) should match what you expect: one e-mail a day, nine calls a run.

Logs cannot leak these by themselves: the pipeline replaces the value of anything named TOKEN, KEY, PASSWORD or SECRET in every log line, and GitHub masks secrets in its logs too.

## Switching provider

**If football-data.org cuts a competition** (Libertadores is a paid tier there and works only by tolerance): the run keeps going, and that competition's matches stop. Set its entry in `config/competitions.yml` to `sources: []`. The site then lists it as "not covered yet" instead of hiding it.

**If football-data.org is down for a while:** the daily run fails and the data published last stays up, getting older (the site says so after 36 hours). There is nothing to switch to today; wait, or add a provider (below). Do not turn off the "all providers must work" rule to force a run: it protects the site from a partial day.

**To add a provider:** write an adapter and register it, then list it in `config/competitions.yml` for the competitions it serves. [The providers' README](../src/ubi_ludus/pipeline/providers/README.md) has the steps and the rules (return the answers untouched, stay inside the limits, never log a key, never commit recorded data). Add the key as a secret and give it to the build step of `pipeline.yml`, and nowhere else. Check the provider's terms first, and from where it accepts calls: **API-Football suspended our account because GitHub's shared addresses look like abuse to it** ([ADR-003](adr/ADR-003-drop-api-football.md)). A provider that does not like shared addresses will fail the same way.

**To bring API-Football back** (only with a dedicated outbound IP): the steps are in ADR-003.

**To switch the e-mail provider:** nothing in the code changes. The sender is plain SMTP, so the new provider's host, port, login and key go into `SMTP_USER` and `SMTP_PASSWORD` (secrets), and its host and port into two repository *variables*, `gh variable set SMTP_HOST --body smtp.example.com` and `gh variable set SMTP_PORT --body 587` (left empty they mean Brevo's relay on 587). A sender address it accepts goes into `EMAIL_FROM`. Try it with `python -m ubi_ludus.email.send` on your machine first ([email.md](email.md)).

## Disabling the e-mail

**To stop it, for every run, at once:** set a repository variable. It needs no pull request and takes effect on the next run.

```bash
gh variable set EMAIL_ENABLED --body false
```

The e-mail job then shows as skipped on the run page, and the site is still updated. To turn it back on:

```bash
gh variable delete EMAIL_ENABLED
```

Other ways, for other needs:

| You want | Do |
| --- | --- |
| no e-mail on one manual run | start it with the box unticked, or `gh workflow run pipeline.yml -f send_email=false` |
| no e-mail on days with nothing to list | already so: `email.quiet_days: skip` in `config/owner.yml` (use `note` for a short "no matches" message) |
| the e-mail gone for good | set the variable as above, and later remove the `email` job and the four mail secrets in a pull request |

Do **not** disable it by deleting a secret: a missing secret fails the job on purpose, so the day it goes missing you hear about it, and it would open a failure issue every day.

## Rolling back the site

The data is rebuilt from the providers every morning and is not stored in the repository, so there are two different things to undo, and a third way to stop everything.

**1. Something wrong was just published (bad data, a broken page).** Run the deploy of an earlier good run again. The site's files of each run are kept for **14 days**, so any run in that time can be put back:

1. *Actions*, *Daily pipeline*, open the last good run (green, before the problem).
2. Open its job **Deploy to GitHub Pages** and choose **Re-run this job**. Or from the command line: `gh run view <run id> --json jobs` shows the job's id, then `gh run rerun <run id> --job <job id>`.
3. The site is back to that run's data and files within a minute.

> **Tried for real on 2026-11-08 (M5-05), and it works.** The owner re-ran the deploy job of the 02:07 UTC run (`gh run rerun 42437187362 --job 128598642903`, which made it attempt 2). The job took 11 seconds; the e-mail job was skipped because that original run had been started without the e-mail; GitHub's deployment record shows a new deployment at 11:58 UTC from the commit that run was built from (`0393e01`, while `main` had moved on), so the old files were what went up. Running the pipeline by hand afterwards put the fresh data back (`generated_at` 12:03:22). Things to know: re-running the job does not run the build, so the e-mail and the data checks are not repeated; and the site stays on the old data until a later run replaces it, so pause the schedules first if the cause is not fixed (below).

This puts old data up **until the next daily run, at 09:00 UTC, which replaces it with fresh data again**. So also fix the cause first: a wrong rule or override in `data/rights/`, a bad change on `main` (below). If the next run would publish the same fault, pause the schedules until it is fixed:

```bash
gh workflow disable pipeline.yml
gh workflow disable watchdog.yml
```

The watchdog is disabled too because it switches the pipeline back on every day at 11:00 UTC. When the fix is in: `gh workflow enable pipeline.yml`, `gh workflow enable watchdog.yml`, and run the pipeline by hand.

**2. A change to the code or the data files caused it.** Revert it: on the pull request that was merged, choose *Revert*, which opens a new pull request. Merge it once the checks pass, then run the pipeline by hand: `gh workflow run pipeline.yml -f send_email=false`. Do not force-push to `main`: it is protected on purpose.

**3. Take the site down altogether.** *Settings, Pages*: unpublish the site (the option sits in that page; I have not used it). Visitors then get a "not found" page. To bring it back, set the source to *GitHub Actions* and run the pipeline.

## When something is red

Every failed run opens an issue "Daily pipeline failed" for you (and later failures comment on it); the first run that works closes it. Open the run it links, find the first red step, and look it up here:

| The first red step says | What it means | Do |
| --- | --- | --- |
| `provider football-data failed: ... is not set` | the token secret is missing or empty | `gh secret set FOOTBALL_DATA_TOKEN` |
| `provider ... failed: ... HTTP 401` or `rejected the API token` | the token was revoked or is wrong | get a new one and set it (see [rotating](#rotating-a-leaked-secret)) |
| `... account is suspended` | the provider blocked the account (this is what happened with API-Football) | see [Switching provider](#switching-provider); contact the provider, and do not hammer it |
| `... HTTP 429` or `rate limit` | too many calls, or a shared address is limited | wait for the next run; check the call count in the log (about 9 a run) |
| `dbt build failed: <names>` | a data test failed | see [Reading a failing dbt test](#reading-a-failing-dbt-test) |
| a schema error naming a file (`matches`, `competitions`, ...) | the data does not match `schemas/`; nothing was published | read the lines it prints, they name the record |
| *Deploy to GitHub Pages* red | Pages is off, or its source is not *GitHub Actions* | *Settings, Pages*, source *GitHub Actions*; run again |
| the e-mail job red: `Missing secret(s): ...` | a mail secret is missing | set it ([email.md](email.md)) |
| the e-mail job red: `code 525` | Brevo is blocking the runner's address | Brevo, *Security*, switch IP blocking off for SMTP keys ([email.md](email.md)) |
| the e-mail job red: `code 535` | wrong login or key, or the sender is not verified | check `SMTP_USER`, `SMTP_PASSWORD` and the sender in Brevo |

The site is not hurt by a failed run: the data published last stays up.

**"Published data is stale"** means 11:00 UTC passed and the data is more than five hours old, so today's run did not happen (or failed, in which case you already have the other issue). Look at *Actions*: no run today means the schedule is off. `gh workflow list --all` shows disabled ones; switch them on with `gh workflow enable pipeline.yml` and run the pipeline by hand. GitHub switches scheduled workflows off after 60 days without activity in the repository; the keep-alive in `watchdog.yml` is there to stop that ([pipeline.md](pipeline.md#keep-alive-fr-52)).

### Simulating a provider outage (a drill you can do any time)

It touches nothing live. With the key blanked for one command:

```bash
FOOTBALL_DATA_TOKEN= python -m ubi_ludus.pipeline.publish --run --require-all-providers --out drill
```

It must end with `error: No provider gave any data (football-data: FOOTBALL_DATA_TOKEN is not set)`, exit status 1, a log line `"event": "run_summary", "outcome": "failed"`, and **no `drill` folder**. That is what a real outage does on GitHub, where the same failure also opens the issue and leaves the site as it was. (This drill ran on 2026-11-07, and found that the command used to end with a traceback and no log line; that is fixed.)

### The same drill on GitHub (live)

This one uses the real pipeline and the real site. It changes no secret and makes no provider call:

```bash
gh workflow run pipeline.yml -f simulate_outage=true -f send_email=false
```

The fetch step then runs with the provider token blanked for that run only. Expected, in order: the build job red with `No provider gave any data`, the deploy and e-mail jobs skipped, the site still serving the data it had, and an issue "Daily pipeline failed" assigned to you. Then start a normal run (`gh workflow run pipeline.yml -f send_email=false`); the issue closes by itself when it is green.

**Done for real on 2026-11-08 (M5-05).** Result:

| What | Result |
| --- | --- |
| Build job | red about a second after the fetch step started, with `error: No provider gave any data (football-data: FOOTBALL_DATA_TOKEN is not set)` and the log line `run_summary`, `outcome: failed` |
| Deploy and e-mail | skipped |
| Site data | untouched: `status.json` still said `generated_at 11:11:27`, the time of the run before the drill, and the 24 match cards were still there |
| Alert | issue "Daily pipeline failed" opened 8 seconds after the failure, assigned to the owner (GitHub then e-mails assignees) |
| Recovery | the next normal run was green and closed the issue by itself |
| Freshness warning | the data is called "possibly out of date" once it is more than 36 hours old, not before. On the live site, the freshness rule gave "fresh" up to 35 hours after the last good run and "stale" from 37 hours on; the page itself shows the warning in the browser tests (`tests/browser/test_freshness_report.py`). So after one missed day (up to 24 hours) the page shows no warning, which is deliberate: the data is still the day's. |

Gaps found: none. The site rollback was drilled the same day (see [Rolling back the site](#rolling-back-the-site)).

## Useful commands

```bash
gh run list --workflow pipeline.yml --limit 5      # the last runs
gh run view <id> --log-failed                       # only the failing step's log
gh workflow run pipeline.yml -f send_email=false    # a run by hand, without the e-mail
gh workflow run pipeline.yml -f force_failure=true  # fail on purpose, to test the alert
gh workflow run pipeline.yml -f simulate_outage=true -f send_email=false  # the outage drill, live
gh workflow run watchdog.yml                        # keep-alive and freshness check by hand
gh workflow list --all                              # are all schedules on?
gh secret list                                      # names only, never values
gh variable list                                    # EMAIL_ENABLED lives here
```
