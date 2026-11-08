# Broadcast audits

Each week, after the matches are played, the owner checks a sample of at least **10 matches of the followed teams** against the official source (the club, the league or the broadcaster's own page) and records what the site said and what was true (PRD S1: at least 85% right). One file per audit, named `YYYY-MM-DD.md`, in this folder. The routine is in the [runbook](../runbook.md#the-weekly-routine).

Copy this table:

```markdown
# Audit 2026-11-12

| Match | Competition | What the site said | What was true | Right? |
| --- | --- | --- | --- | --- |
| Palmeiras x Flamengo | Brasileirão | Globo, SporTV (rule) | Globo, SporTV, Premiere | no: missing Premiere |

**Right:** 9 of 10 (90%). **Action:** override for the match above; the rule for the Brasileirão needs Premiere.
```

A wrong match is either an override this week (`data/rights/overrides.yml`) or a rule that needs changing (`data/rights/rights.yml`); write which in the last line.
