# Phase 1 closure review

**Date: 4 January 2027.** This closes the 14-day measurement (21 December 2026 to 3 January 2027) and decides what Phase 1 delivered. It is a calendar date in the repository, and the issue [#41](https://github.com/raissonls/ubi-ludus/issues/41) stays open until the review is written below.

## Before the window opens (21 December)

- [ ] CI green on `main` and every Must requirement of the [PRD](PRD.md) implemented and tested. The open issues that are not Must are Phase 2 or Could/Should and can wait: #42, #43, #44, #46 to #51, #55, #70, #71.
- [x] The site is live and the daily pipeline, the e-mail, the alerts and the Lighthouse check are running ([pipeline](pipeline.md), [runbook](runbook.md)).
- [x] Weekly audit template: [audits/TEMPLATE.md](audits/TEMPLATE.md).
- [x] Owner effort log: [audits/effort-log.md](audits/effort-log.md).
- [ ] Usability sessions done and findings fixed ([usability kit](usability/README.md), #38).
- [ ] Screen-reader pass done ([accessibility audit](audits/accessibility-2026-11-07.md), #36).
- [x] Site rollback tried once, 2026-11-08 ([runbook](runbook.md#rolling-back-the-site)).
- [ ] The name checked before telling people about the site (#45).
- [ ] Owner steps of the [security sign-off](security-checklist.md#left-for-the-owner) done.

## During the window

Two weekly audits (Thursday 24 and 31 December), each from [the template](audits/TEMPLATE.md), and the effort log every day.

## The review (write this on 4 January)

Fill the "Result" column from the audits, the Actions history and the effort log. Say **met** or **not met** against the target, and for anything not met, what the cause was and which issue takes it on.

| Measure | Target | How to compute it | Result | Met? |
| --- | --- | --- | --- | --- |
| S1 Broadcast accuracy | 85% or more | right / audited, over both weekly audits (at least 20 matches) |  |  |
| S2 Coverage | 90% of followed-team matches, 70% of all | the two audits' coverage lines |  |  |
| S3 Freshness | published by 07:00 BRT on 95% of days | days (of 14) the run finished before 10:00 UTC: `gh run list --workflow pipeline.yml --limit 30 --json createdAt,conclusion,event` |  |  |
| S4 E-mail reliability | delivered by 08:00 BRT on 95% of days | days with matches the e-mail arrived in time, over days with matches |  |  |
| S5 Pipeline reliability | 95% of scheduled runs succeed | `--event schedule` runs, successes over total (13 of 14 is 93%: one failure fails this) |  |  |
| S6 Time to answer | first time 30 s or less, returning 10 s or less | [usability sheet](usability/README.md) |  |  |
| S7 Usability | 4 of 5 unaided | usability sheet |  |  |
| S8 Site quality | Lighthouse 90 or more in all four; no critical axe violation | the Lighthouse runs on the deployed site in the window; the accessibility tests in CI |  |  |
| S9 Cost | R$ 0 | the accounts, once |  |  |
| S10 Security hygiene | 0 secrets in history; no high/critical Dependabot alert open over 7 days; permissions least-privilege | [security sign-off](security-checklist.md), repeated: `gh api repos/raissonls/ubi-ludus/dependabot/alerts` |  |  |
| S11 Owner effort | 30 minutes a week or less | [effort log](audits/effort-log.md) |  |  |
| S12 Owner satisfaction | uses it 5 of 7 days in the final week; would not go back | the owner's yes/no at the end of the effort log |  |  |

### Decision

- [ ] Phase 1 is **closed**: all Must measures met.
- [ ] Phase 1 is **closed with exceptions**: list them and the issue for each.
- [ ] Phase 1 is **extended** by _ weeks: say what is not met and why.

What goes to Phase 2 first (from #46 to #51 and what the audits showed):

Notes:
