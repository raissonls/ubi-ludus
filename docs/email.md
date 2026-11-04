# The morning e-mail

What it says and how it is made. Sending, secrets and the skip rule are the next task (M4-02, #31); this is the rendering (M4-01, #30, PRD FR-40 and FR-43).

## What it lists

For the day of "now" in Brazil (`America/Sao_Paulo`, never UTC):

1. **Jogos dos seus times**: matches of the teams in `config/owner.yml`, by kickoff time; the team the owner likes best (first in the list) breaks a tie. A match that is postponed or cancelled is listed with that word instead of a time.
2. **Destaques do dia**: matches of `notable_competitions` that do not involve the owner's teams, by time, at most six (the rest are counted: "E mais 2 jogos nesta competição hoje.").

Finished matches are left out. Each match shows the kickoff in Brasília time, teams, competition and round, where to watch, and a marker:

| Marker | Meaning |
| --- | --- |
| ✔ Dá para assistir com os seus serviços | a listed broadcaster is free (free TV, YouTube) or comes with one of the owner's `services` |
| Fora dos seus serviços | broadcasters are listed and none is the owner's |
| Transmissão ainda não confirmada | no broadcaster is known, so none is named (FR-13) |

Broadcasters the owner can watch come first (marked ✔), then the favourites in `owner.yml`, then confirmed ones, then by name. "(confirmado)" is only on those a person checked; if any is from the rights table the e-mail says to check closer to the match. When the data is older than 36 hours the e-mail says so at the top, the same rule as the site.

An empty day still renders ("Hoje não há jogos"); whether to send it is M4-02's flag (FR-42).

## How it is made

- `briefing.py` is pure: the published files (`site/data`, checked against the schemas) and `OwnerConfig` in, a `Briefing` out. The rules above live here and are tested without a template.
- `render.py` fills the layouts in `templates/briefing.html` and `briefing.txt` (`$name` holes, standard library only). Everything from data goes through `html.escape` (HTML) or has its line breaks removed (subject, text). A team colour is used only if it is `#rrggbb`; a link only if it is `http(s)` with nothing that could end an attribute.
- The HTML is what mail clients accept: tables for layout, every colour inline, one `<style>` block only for dark mode, no script, no image, no external file. Nothing is loaded when it is opened, so there is no tracking pixel and no crest (PRD R5).

## Look at it

```bash
python -m ubi_ludus.email.render --out email-preview
```

writes `briefing.html` and `briefing.txt` for today from `site/data` (`--now 2026-11-03T11:00:00Z` for another moment, `--site-url https://…` for the footer link). Open the HTML in a browser, or send it to yourself, for the manual check in Gmail (web and mobile) and Apple Mail that FR-43 asks for before launch. That check has not been done yet.

## Tests

`tests/unit/test_email_briefing.py` (which matches, order, access, staleness), `tests/unit/test_email_render.py` (words, escaping of hostile names, nothing to load, structure, text and HTML agree) and `tests/browser/test_email.py` (axe in light and dark, no sideways scroll down to 320 px, long names wrap).
