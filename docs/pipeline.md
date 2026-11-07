# The daily pipeline

`.github/workflows/pipeline.yml` runs every day at **09:00 UTC (06:00 in Brazil)** and can be started by hand (PRD FR-50). It is three jobs, each starting only if the one before worked:

| Job | What it does | Gets which secrets |
| --- | --- | --- |
| **build** | Fetches the matches from the providers, loads them, runs `dbt build` (a failing test stops the run), exports the five JSON files and checks every one against its schema, then stages the site | the two provider keys, on one step |
| **deploy** | Publishes the site and the data to GitHub Pages with the Pages actions (`upload-pages-artifact`, `deploy-pages`). Nothing generated is ever committed to the repository | none |
| **email** | Sends the morning e-mail from the data that was just published (see [email.md](email.md)) | the four e-mail secrets, on one step |

## If something fails, what stays published

The data published last stays up. Nothing is overwritten half way:

- **A provider fails** (it is down, its key is missing or wrong, the daily quota is used up): the build writes nothing and the job fails, naming the provider. A partial day never replaces a complete one. The price is that one provider's outage stops the update of all competitions until it is back; the site says its data is old after 36 hours (M3-08).
- **A dbt test or a schema check fails:** the job fails before the site is gathered. Bad data never reaches Pages.
- **The deploy fails:** Pages keeps serving what it had.
- **Only the e-mail fails** (a login refused, a secret missing): the site is already updated; the run is red so you hear about it.

## How you are told (FR-51)

- **A run fails.** The last job of the pipeline, `status`, opens an issue **assigned to you** ("Daily pipeline failed", label `pipeline-failure`) with the run's address, which jobs failed and what to do. GitHub e-mails the assignee as soon as it is created, so the notice comes within minutes of the failure. If another run fails while the issue is open, it adds a comment instead of opening a second one. The first run that works closes the issue by itself. This also catches a failed e-mail (a refused login, a missing secret) even though the site was updated.
- **A run never happens.** A failure job cannot report a run that did not start (a delayed, skipped or switched-off schedule), so `watchdog.yml` asks the published site from outside, at 11:00 UTC, when its data last came from a good run (`python -m ubi_ludus.pipeline.watchdog`). Older than 5 hours means today's run did not happen: it opens an issue assigned to you ("Published data is stale", label `stale-data`) and closes it when the data is fresh again. (The 5 hours is for you; the site's own "data may be old" notice waits 36 hours, because it is for visitors.)
- GitHub also e-mails you about failed scheduled runs by default. That is a third channel and not one to rely on alone.

**Testing the alert:** start a run that fails on purpose and time how long the notice takes (the target is 15 minutes):

```bash
gh workflow run pipeline.yml -f force_failure=true
```

An issue "Daily pipeline failed" should appear, assigned to you, with an e-mail from GitHub. The next run that works (a normal manual run) closes it.

## Keep-alive (FR-52)

GitHub switches off scheduled workflows in a public repository after 60 days with no repository activity, and this pipeline deliberately commits nothing. So `watchdog.yml` also has a **keep-alive** job: every day it runs `gh workflow enable` on every workflow that has a schedule (`pipeline.yml`, `review-report.yml` and `watchdog.yml` itself), with a token that can do nothing else (`actions: write`). A test fails if a new scheduled workflow is added and not put on that list.

What is verified and what is not, honestly: the **call** is verified (it works on a workflow that is already on, from your machine and from the run, see the dry run below). That re-enabling **restarts GitHub's 60-day clock** is what community keep-alive tools rely on; GitHub's documentation does not spell it out, and the only full proof is 60 days of quiet. The safety net if it does not hold is the watchdog above (a switched-off pipeline shows up as stale data the next day, as long as the watchdog itself is still on). A manual commit to the repository always counts as activity.

**Dry run:** *Actions > Keep-alive and freshness check > Run workflow* (or `gh workflow run watchdog.yml`). Both jobs should be green, the first listing each workflow as "Enabled (or already on)", the second printing "Fresh: last successful run ...".

## Permissions, reviewed (M4-04)

Every workflow starts with no permissions and each job asks for its own. Who can write what:

| Permission | Where | Why |
| --- | --- | --- |
| `issues: write` | `pipeline.yml` `status`, `watchdog.yml` `freshness`, `review-report.yml` `report` | to open, update and close the issues above and the weekly review |
| `pages: write`, `id-token: write` | `pipeline.yml` `deploy` | to deploy to Pages |
| `actions: write` | `watchdog.yml` `keep-alive` | to enable workflows |
| `contents: read` | the jobs that check out the code | nothing in the repository is ever written by a workflow |

No job has `contents: write`, nothing runs on `pull_request_target`, every action is pinned to a commit, and the secrets go to single steps (the provider keys to the build step, the four mail secrets to the send step). `tests/unit/test_workflows.py` fails if any of this changes: the table above is checked against the files.

## Setting it up (once)

1. **Turn on Pages from Actions.** Repository *Settings > Pages > Build and deployment > Source: GitHub Actions*. (Or `gh api -X POST repos/<owner>/<repo>/pages -f build_type=workflow`.) The site then lives at `https://<owner>.github.io/<repo>/`. The repository must be public, or on a plan that has Pages for private ones.
2. **Secrets** (*Settings > Secrets and variables > Actions*, or `gh secret set NAME`):

   | Name | For |
   | --- | --- |
   | `FOOTBALL_DATA_TOKEN` | the provider (football-data.org; API-Football is not used, see [ADR-003](adr/ADR-003-drop-api-football.md)) |
   | `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO` | the e-mail (see [email.md](email.md); Brevo's IP blocking for SMTP keys must be off, because the runners change address on every run) |

3. **Try it without e-mailing:** *Actions > Daily pipeline > Run workflow* with "Send the morning e-mail" unticked, or

   ```bash
   gh workflow run pipeline.yml -f send_email=false
   ```

   Then open the run, check each job is green, and open the site. Run it once more with the e-mail on to see the whole chain.

The first run finds no earlier `matches.json` to compare with (the site does not exist yet) and goes on without it; from the second run on, a match whose kickoff moved is flagged.

## Time

A scheduled run can start late when GitHub is busy, usually by minutes (the watchdog allows for it). The chain takes a few minutes, which leaves the e-mail well before 08:00 in Brazil (FR-40).
