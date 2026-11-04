# The site

Static HTML, CSS and JavaScript (ES modules). **No framework, no build step, no dependencies** ([ADR-001](../docs/adr/ADR-001-architecture.md)). What is in `site/` is what gets published.

```text
index.html        the page: the Content Security Policy, then the markup
css/tokens.css    design tokens: colour (light and dark), type, space, shape, motion
css/base.css      reset, typography and the page frame; reads only tokens
js/main.js        entry point
js/i18n.js        loads i18n/pt-BR.json, translates, fills the page
js/data.js        loads the five published files from data/ and indexes them by id
js/preferences.js  the visitor's teams and services, in localStorage and nowhere else
js/search.js       finds a team as you type (no accents, aliases, ranked); pure
js/teams-picker.js  the "Which teams do you follow?" combobox and the chosen teams
js/services-picker.js  the "Which services do you have?" checkboxes
js/matches-preview.js  which matches of the followed teams are still to come; pure
js/match-model.js  turns a match and the data into what a card shows (state, confidence, badges); pure
js/match-card.js   draws one match card from that model
js/freshness.js     how old the data is, from status.json (today / yesterday / a date / stale after 36 h / unknown); pure
js/report.js        the pre-filled "report a wrong broadcast" GitHub issue links; pure
js/filters.js       which matches pass the competition, broadcaster and team-search filters; pure
js/filters-view.js  the "Filtros" box
js/url-state.js     reads and writes the view in the address, checked against allow-lists; pure
js/share.js         "Copiar link desta visão"
js/home-views.js   which matches each home list shows (my teams, today, this week), followed teams first; pure
js/matches-view.js  draws the chosen list as cards and switches between the lists
js/dom.js          safe element building and team colours as CSS variables
js/format.js      dates and times in Brazil's time zone (Intl)
i18n/pt-BR.json   every string the visitor reads
assets/           the icon
data/             the published JSON files (matches, teams, competitions, broadcasters, status); written by the pipeline, git-ignored
test/             unit tests for js/ (Node's built-in runner)
```

## Rules the checks enforce

| Rule | Where it is checked |
|---|---|
| **A Content Security Policy by meta tag**: nothing by default; scripts, styles, images, fonts and requests only from this origin; no `unsafe-*`, no host. No inline script, style block, `style=` attribute or event handler. | `tests/unit/test_site.py`, and in a real browser (`tests/browser`) that really blocks an inline script and a script from another host |
| **Nothing from outside**: no CDN, no web font, no `@import`; fonts are the system's. Every request stays on this origin. | the same two |
| **Safe DOM**: no `innerHTML`, `document.write`, `eval` or `new Function`. Text goes in with `textContent`. | `test_site.py` |
| **Strings** live in `i18n/pt-BR.json`, not in the HTML or the code. Dates and times come from `js/format.js` (`Intl`, zone `America/Sao_Paulo`). A missing string shows as `[key]`. | `test_site.py`, `site/test/` |
| **Themes and motion**: `prefers-color-scheme` and `prefers-reduced-motion`, through the tokens. | `test_site.py`, browser tests |
| **Contrast**: every text colour pair at least 4.5:1, borders and focus rings at least 3:1, in both themes. | `test_site.py` (computed from the tokens) |
| **Accessibility**: axe with the WCAG 2.2 AA rules, light and dark, at 1280, 375 and 320 px; focus rings; the skip link. | `tests/browser` |
| **Size**: JavaScript at most 100 KB gzipped (PRD), CSS 20 KB, the whole site 150 KB. | `test_site.py` |
| **Privacy**: no cookies; only `js/preferences.js` touches `localStorage`; the only requests are plain GETs of the site's own files, with no query string, body or cookie, and **no request carries the visitor's choices** (a browser test saves choices, loads the page, and reads every request); the footer notice and `PRIVACY.md` exist. | `test_site.py`, `tests/browser` |
| **Storage that fails**: blocked, missing or full, the page works and the choices live in memory for the visit. | `site/test/`, `tests/browser` |
| **Data that fails**: a file that is missing, not JSON, or in a newer format shows a message, not a blank page, and is still accessible. | `site/test/`, `tests/browser` |

## Working on it

- **Data:** `python -m ubi_ludus.pipeline.publish --run` runs the pipeline against the live providers (keys in `.env`, see `.env.example`) and writes `site/data/`. `--cache-dir .cache` reuses answers for an hour, so repeated runs spend no quota. Without `--run` it only re-writes the files from the last warehouse.
- **Preview:** `python -m http.server -d site 8000`, then http://localhost:8000. (Opening `index.html` from disk does not work: scripts and the strings file need a server.)
- **A new string:** add it to `i18n/pt-BR.json`, use it with `data-i18n="group.key"` in HTML or `t('group.key')` in code. Plurals are objects of forms (`one`, `other`) read with `plural()`. A string nothing uses fails a test, so add it with the thing that shows it.
- **A new colour or size:** add a token to `css/tokens.css` (with a dark value), never a raw value in another file. A colour used for text goes in `TEXT_PAIRS` in `tests/unit/test_site.py` so its contrast is checked.
- **A new image or font:** the site test refuses any file type it does not know. Add it on purpose, with a reason and its licence.
- **Tests:** `cd site && npm test` for the JavaScript, `pytest -m browser` for the browser checks. CI runs both.

## Data attribution

The footer shows "Football data provided by the Football-Data.org API" exactly as football-data.org's terms require, and credits API-Football. See [the provider comparison](../docs/research/provider-comparison.md).

## The teams picker

- It is an ARIA editable combobox with list autocomplete: `role=combobox` on the box, a `listbox` it controls, `aria-activedescendant` for the option under the arrow keys. Down and Up move (and wrap), Enter chooses (the first suggestion if none is under the arrows), Escape closes and then clears. What happened is said in a polite live region ("Palmeiras adicionado. 2 times escolhidos.").
- Search ignores case, accents and punctuation and also looks at each team's short name and aliases, so `barca` finds Barcelona and `brazil` finds Brasil. With nothing typed it suggests Brazilian teams first.
- Choosing a team saves it at once and shows its next matches, so a new visitor is two or three interactions from a result (click, type, pick; or just type and press Enter).
- The suggestions close after a choice and when a chosen team is removed, so they never cover the chosen teams the visitor may want to reach.
- A team's two colours are only an accent (a small square and a bar), set as CSS variables from script (the policy allows that, not a `style` attribute). There is no crest or logo, and the name is always next to the colour.

## The services picker

- One native checkbox for each service in `broadcasters.json` (pay TV, Premiere, Globoplay, Disney+, ...), each with what it includes ("Inclui: SporTV e ESPN."), tied to the checkbox with `aria-describedby`. Native checkboxes with real labels are the most accessible control there is.
- **Nothing is ticked by default.** Free TV and YouTube need no subscription, so no choice at all means "only free TV and YouTube", and the page says so in a live region that also reports how many are ticked.
- Choices are saved with the teams in one record, each change at once, and a service the data no longer has is ignored. How a match is marked "watchable with my services" is M3-07.

## The match card
- One card per match: when (Brazil time), the teams as the heading, competition and round, and where to watch. The left edge takes the colour of a followed team; no crests or logos, only colours.
- State is always a word, never only a colour: *Ao vivo* (with a dot), *Remarcado*, *Adiado*, *Cancelado*, *Encerrado*. Only a match that can still be watched (scheduled, rescheduled, live) lists broadcasters.
- How sure we are (FR-12): **confirmed** broadcasters carry a tick and a hidden "(confirmado)" for screen readers; **rule** broadcasters (from the rights table) have no tick and the card says to check before the match; **unknown** names no broadcaster at all and says "Transmissão ainda não confirmada" (FR-13). A card with both confirmed and rule broadcasters counts as rule.
- More than four broadcasters wait behind a "+N" button (`aria-expanded`, works with Enter and Space).
- Names come from the data and are always set as text, never as markup.
- Tests: `tests/fixtures/site/gallery/cards.html` draws all 14 cases (every state, confidence, a long list, a hostile name) with the site's own modules. `tests/browser/test_match_card.py` checks them, runs axe in both themes and three sizes, and compares colours, borders and words with `tests/browser/snapshots/match_card_styles.json` (computed styles rather than pixels, so Windows and Linux agree). After a deliberate change of look, record again with `UBI_LUDUS_UPDATE_SNAPSHOTS=1` and review the diff.

## The home lists
- Three lists, chosen with three buttons (`aria-pressed`, so the chosen one is also bold): **Meus times** (the next ten matches of the followed teams), **Hoje** and **Esta semana**.
- Days are calendar days in Brazil (`America/Sao_Paulo`), not UTC: a match at 01:00 UTC still belongs to the evening before. "This week" is today and the six days after it. A match still marked "to come" whose kickoff was more than three hours ago is old data and is left out.
- In Hoje and Esta semana the matches of followed teams come first, then the others, each soonest first. When both groups have matches they get a title ("Jogos dos seus times", "Outros jogos"); followed cards also carry `data-followed` and a stronger border.
- Until the visitor presses a button the page chooses: **Meus times** if they follow a team, else **Hoje**. A button they pressed is kept while the page is open (nothing about it is saved).
- The lists come before the pickers, so a returning visitor's next match is on screen on a phone without scrolling (tested at 375x812).
- Cards enter with a short rise and fade, the first six a beat apart; with reduced motion there is no animation at all.

## What the visitor can watch
- A broadcaster is the visitor's if it is free TV or YouTube (no subscription needed), or belongs to a ticked service, or is included by one (Disney+ includes ESPN). With nothing ticked that is "free TV and YouTube only", as the services picker says (`accessibleBroadcasters` in `match-model.js`).
- On a card: each badge is outlined solid when it is the visitor's and dashed when it is not (and says so to a screen reader), and a line says "Dá para assistir com os seus serviços." or "Nenhuma dessas emissoras está nos seus serviços." A match that cannot be watched also gets a dashed edge. Words, not colour alone.
- A match with no known broadcaster is neither: it says "Transmissão ainda não confirmada" and nothing about access (FR-13). Finished, postponed and cancelled matches say nothing either.
- **Só o que dá para assistir** hides only the matches known not to be watchable; matches with no confirmed broadcaster stay, since nothing says the visitor cannot watch them. The filter is applied before the ten-match limit of "Meus times". It is saved with the other choices (`onlyWatchable`, in localStorage only) and cleared by "Reset my data".
- Tests: `tests/browser/test_watchable.py` serves changed fixture matches so every case exists; the card gallery takes `?services=premiere,globoplay` to draw the cards for a visitor with those services.

## Freshness and reports
- The header says when the data was last updated, from `last_success_at` in `status.json`, in Brazil's time: "Atualizado hoje às 06:12", "ontem" or a date. Older than 36 hours, or no success on record, it becomes a warning ("Atenção: os dados podem estar desatualizados…"): a mark and words on a warning background, not colour alone. The clock is the visitor's; a few minutes of skew into the future still reads as today.
- Each card that lists broadcasters (or says none is known) has a "Reportar transmissão errada" link to a new GitHub issue from `.github/ISSUE_TEMPLATE/wrong-broadcast.yml`, with the match and what the site shows already filled in (`match`, `shown`, `title`). The footer has the same link with nothing filled in. The links carry the match and nothing about the visitor; they are the only way out of the site to GitHub, and only when the visitor clicks. Cards of matches that are over, postponed or cancelled have no link.
- Tests: `tests/browser/test_freshness_report.py` serves changed `status.json` files for every state.

## Filters and sharing
- **Filtros** (a box, closed until wanted; its summary counts the filters set): a competition, a broadcaster and a few letters of a team's name. They combine (AND) with each other, with the chosen list and with "Só o que dá para assistir", and are applied before the ten-match limit of "Meus times". The choices offered are the competitions and the named broadcasters that some match has; the team search ignores case and accents and finds short names and aliases ("barca").
- The filters and the list the visitor picked are always in the address (`?view=week&competition=…&broadcaster=…&q=…`, replaced in place, so Back is not filled with keystrokes), so a view can be bookmarked or reloaded. **The visitor's own teams and services are never in the address** unless they press "Copiar link desta visão", which builds a link with `teams`, `services` and `watchable` too and copies it (or shows it to copy by hand when the browser refuses the clipboard).
- Reading an address is the careful part. Every value is checked against an allow-list built from the data: lists must be one of the three, competitions and broadcasters must be ones offered, team and service ids must exist (at most 50 each, ids must also look like ids). The search text loses control characters and is cut at 60 characters, and is only ever put in a field as text. What does not fit is ignored.
- Opening a shared link shows its teams, services and filter **for that visit only** and saves nothing: a notice says so. The first time the visitor changes their teams or services the shown choices become their own and are saved, and the choices leave the address.
- Tests: `tests/browser/test_filters_share.py` (read the address with `location.href`; Playwright's `page.url` learns of `history.replaceState` a moment later).
