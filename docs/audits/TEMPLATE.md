# Weekly audit YYYY-MM-DD

Copy this file to `docs/audits/YYYY-MM-DD.md` (the Thursday of the review) and fill it in. It takes about 30 minutes with the review issue open ([the weekly routine](../runbook.md#the-weekly-routine)). During the 14-day measurement (21 December 2026 to 3 January 2027) there are two of these; they are the evidence for the [closure review](../closure-review.md).

Window covered: from YYYY-MM-DD to YYYY-MM-DD.

## 1. Broadcast accuracy (S1: 85% or more right, stretch 90%)

Check a sample of **at least 10 matches of followed teams** that were played this week, against the official source (the club, the league or the broadcaster's own page), after the match.

| Match | Competition | What the site said | What was true | Right? |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

**Right:** _ of _ (_ %). **Action:** (override this week in `data/rights/overrides.yml`, or the rule that needs changing in `data/rights/rights.yml`; "none" if all right)

## 2. The other numbers

Read them from the review issue, from `status.json` and from the Actions history; do not estimate.

| Measure | Target | This week | Where to read it |
| --- | --- | --- | --- |
| S2 Coverage: upcoming matches of the owner's teams with a known broadcast | 90% or more | _ % | the review issue, "Summary": matches minus unknown, over matches |
| S2 Coverage: all listed matches with a known broadcast | 70% or more | _ % | 100 minus `unknown_ratio` x 100 in `status.json` (`curl -s https://raissonls.github.io/ubi-ludus/data/status.json`) |
| S3 Freshness: days published by 07:00 BRT (10:00 UTC) | 95% or more | _ of 7 | `status.json` `generated_at` per run, or the run times in *Actions, Daily pipeline* |
| S4 E-mail reliability: days delivered by 08:00 BRT, on days with matches | 95% or more | _ of _ | the "Send the morning e-mail" job and the inbox |
| S5 Pipeline reliability: scheduled runs that succeeded | 95% or more | _ of 7 | `gh run list --workflow pipeline.yml --event schedule --limit 7` |
| S8 Site quality: Lighthouse on the deployed site (all four, mobile) | 90 or more | _ / _ / _ / _ | the summary of the Lighthouse run "The deployed site" after the deploy |
| S9 Cost: money spent this week | R$ 0 | R$ _ | the accounts: GitHub, football-data.org, Brevo |

## 3. What went wrong or surprised me

(Failed runs and their issues, a wrong channel that took long to find, an e-mail that came late, a visitor report from the "Reportar transmissão errada" link.)

## 4. Time spent (S11: 30 minutes a week or less once launched)

This audit: _ min. Everything else on the project this week: _ min. (Also in the [effort log](effort-log.md).)

## 5. Decisions

(What changes next week, and which issue it is in.)
