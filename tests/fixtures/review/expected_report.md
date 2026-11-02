# Weekly review: 2 Nov 2026

Generated 2026-11-02 09:00 UTC (06:00 in Brazil) from the latest pipeline run.

## Summary

- Upcoming matches of your teams: **3** (1 confirmed, 1 from rules, **1 unknown**)
- Rights rules ending within 30 days: **1**
- Rights rules that ended with nothing to replace them: **1**

## Unknown matches of your teams

Nothing is known about where these will be shown. Find out, then add an override to `data/rights/overrides.yml` (or add a rights rule if the whole competition is missing).

| When (Brazil) | Competition | Match | Match id |
|---|---|---|---|
| Thu 12 Nov, 17:00 | UEFA Champions League | Flamengo x Estudiantes | `football-data-920002` |

```yaml
# data/rights/overrides.yml
- match_id: <match id above>
  action: replace
  broadcasters: [<broadcaster ids from broadcasters.yml>]
  reason: "Where you found out, and when"
  added_at: 2026-11-02
```

## Rights rules ending within 30 days

| Last day | Days | Competition | Season | Covers | Broadcasters | Source |
|---|---|---|---|---|---|---|
| 2026-11-10 | in 8 | `uefa-champions-league` | 2026-27 | all matches | hbo-max | A made-up source for the tests |

## Rules that ended without a replacement

| Last day | Days | Competition | Season | Covers | Broadcasters | Source |
|---|---|---|---|---|---|---|
| 2026-10-20 | 13 ago | `copa-do-brasil` | 2026 | all matches | globo, prime-video | A made-up source for the tests |
