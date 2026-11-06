# The morning e-mail

What it says and how it is made. Rendering is M4-01 (#30, PRD FR-40 and FR-43); sending, secrets and the quiet-day rule are M4-02 (#31, FR-40 to FR-42). The daily workflow that runs it is M4-03 (#32).

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

An empty day still renders ("Hoje não há jogos"); whether it is sent is the `email.quiet_days` choice below.

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

`tests/unit/test_email_briefing.py` (which matches, order, access, staleness), `tests/unit/test_email_render.py` (words, escaping of hostile names, nothing to load, structure, text and HTML agree) and `tests/unit/test_email_send.py` (secrets, the skip rule both ways, the message, TLS and login order, errors that hide credentials, the command) and `tests/browser/test_email.py` (axe in light and dark, no sideways scroll down to 320 px, long names wrap).

## Sending (M4-02)

**Method (PRD Q3, decided 2026-11-06):** plain SMTP through Brevo's free relay (300 e-mails a day; we send one). The code (`send.py`, standard library only) does not know Brevo: it connects to `SMTP_HOST`, upgrades to TLS with the default certificate checks (or uses TLS from the start on port 465), logs in and sends. A different provider is a different set of secrets. The sender is a dedicated address, not your personal mailbox, and nothing in the code limits it to one recipient except that `EMAIL_TO` holds one: sending to other people later is a decision for Phase 2 (consent and LGPD, PRD Q6), not a rewrite.

**The secrets.** The address and the credentials exist only as GitHub Secrets (and in your own git-ignored `.env`), never in a file in the repository, a log or an error message (the settings object hides them even when printed; tests check that).

| Name | What it is | Secret? |
| --- | --- | --- |
| `SMTP_USER` | the SMTP login Brevo gives you | yes |
| `SMTP_PASSWORD` | the SMTP key (not your Brevo account password) | yes |
| `EMAIL_FROM` | the verified sender address | yes (an address) |
| `EMAIL_TO` | where the e-mail goes: yours | yes |
| `SMTP_HOST`, `SMTP_PORT` | default `smtp-relay.brevo.com` and `587` | no |

If any of the first four is missing or empty the job fails and says which ones, before anything is sent and **even on a day with nothing to send**, so a lost secret is found the day it is lost. An address that is a list, has a name, or has a line break in it is refused (a line break could add a header such as `Bcc`).

**Setting it up** (once; you do these, I never see the values):

1. Create a free account at brevo.com. Under *SMTP & API* make an SMTP key and note the SMTP login. Under *Senders, domains & dedicated IPs* add the address you want the e-mail to come from and confirm it from the message Brevo sends there. (Check Brevo's own pages for the exact screens and current limits.)
2. Add the four secrets to the repository, typing each value when asked so it is not left in your shell history:

   ```bash
   gh secret set SMTP_USER
   gh secret set SMTP_PASSWORD
   gh secret set EMAIL_FROM
   gh secret set EMAIL_TO
   ```

3. To try it on your machine, put the same four in `.env` (see `.env.example`) and run:

   ```bash
   python -m ubi_ludus.email.send --data site/data --dry-run   # renders, sends nothing, needs no secret
   python -m ubi_ludus.email.send --data site/data             # sends today's e-mail
   ```

   Add `--now 2026-11-03T11:00:00Z` to pretend it is another moment, `--site-url https://…` for the footer link.

**A day with nothing to list (FR-42).** `config/owner.yml` has

```yaml
email:
  quiet_days: skip   # or: note
```

`skip` (the default, as you chose) sends nothing, so an e-mail always means there is something to see. `note` sends the short "Hoje não há jogos" e-mail, so you know the job ran. A day with any match to list is always sent. The command says which it did ("No e-mail today…" or "E-mail sent.") and exits 0; a missing secret or a refused login exits 1 with the reason, which fails the workflow.

If the mail server refuses the login, the message says to check `SMTP_USER`, `SMTP_PASSWORD` and that `EMAIL_FROM` is verified with the provider. It never repeats the server's reply, which could echo a credential.

**Not yet:** running it every morning is the workflow of M4-03 (#32), which will pass the four secrets as environment variables and `SITE_URL`.
