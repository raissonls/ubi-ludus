# The site

Static HTML, CSS and JavaScript (ES modules). **No framework, no build step, no dependencies** ([ADR-001](../docs/adr/ADR-001-architecture.md)). What is in `site/` is what gets published.

```text
index.html        the page: the Content Security Policy, then the markup
css/tokens.css    design tokens: colour (light and dark), type, space, shape, motion
css/base.css      reset, typography and the page frame; reads only tokens
js/main.js        entry point
js/i18n.js        loads i18n/pt-BR.json, translates, fills the page
js/format.js      dates and times in Brazil's time zone (Intl)
i18n/pt-BR.json   every string the visitor reads
assets/           the icon
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
| **Privacy**: no cookies and no storage until the preferences module (M3-02); the footer notice and `PRIVACY.md` exist. | `test_site.py` |

## Working on it

- **Preview:** `python -m http.server -d site 8000`, then http://localhost:8000. (Opening `index.html` from disk does not work: scripts and the strings file need a server.)
- **A new string:** add it to `i18n/pt-BR.json`, use it with `data-i18n="group.key"` in HTML or `t('group.key')` in code. Plurals are objects of forms (`one`, `other`) read with `plural()`. A string nothing uses fails a test, so add it with the thing that shows it.
- **A new colour or size:** add a token to `css/tokens.css` (with a dark value), never a raw value in another file. A colour used for text goes in `TEXT_PAIRS` in `tests/unit/test_site.py` so its contrast is checked.
- **A new image or font:** the site test refuses any file type it does not know. Add it on purpose, with a reason and its licence.
- **Tests:** `cd site && npm test` for the JavaScript, `pytest -m browser` for the browser checks. CI runs both.

## Data attribution

The footer shows "Football data provided by the Football-Data.org API" exactly as football-data.org's terms require, and credits API-Football. See [the provider comparison](../docs/research/provider-comparison.md).
