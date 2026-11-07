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

A failed run is red on the Actions page and GitHub e-mails the owner about failed scheduled runs. Proper failure alerts and the keep-alive that stops GitHub disabling the schedule after 60 days of inactivity are M4-04.

## Setting it up (once)

1. **Turn on Pages from Actions.** Repository *Settings > Pages > Build and deployment > Source: GitHub Actions*. (Or `gh api -X POST repos/<owner>/<repo>/pages -f build_type=workflow`.) The site then lives at `https://<owner>.github.io/<repo>/`. The repository must be public, or on a plan that has Pages for private ones.
2. **Secrets** (*Settings > Secrets and variables > Actions*, or `gh secret set NAME`):

   | Name | For |
   | --- | --- |
   | `FOOTBALL_DATA_TOKEN`, `API_FOOTBALL_KEY` | the providers |
   | `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO` | the e-mail (see [email.md](email.md); Brevo's IP blocking for SMTP keys must be off, because the runners change address on every run) |

3. **Try it without e-mailing:** *Actions > Daily pipeline > Run workflow* with "Send the morning e-mail" unticked, or

   ```bash
   gh workflow run pipeline.yml -f send_email=false
   ```

   Then open the run, check each job is green, and open the site. Run it once more with the e-mail on to see the whole chain.

The first run finds no earlier `matches.json` to compare with (the site does not exist yet) and goes on without it; from the second run on, a match whose kickoff moved is flagged.

## Time

A scheduled run can start late when GitHub is busy, usually by minutes. The chain takes a few minutes, which leaves the e-mail well before 08:00 in Brazil (FR-40).
