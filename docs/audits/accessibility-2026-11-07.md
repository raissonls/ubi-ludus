# Accessibility audit, 2026-11-07 (M5-01)

Target: **WCAG 2.2 level AA** (PRD FR-31 and the accessibility requirement). Scope: the live site at https://raissonls.github.io/ubi-ludus/ in every state, both themes, at 1280, 375 and 320 px wide.

## Result in one paragraph

**Zero axe violations** in every state, size and theme, and none in forced-colours mode. Two real problems were found by checks axe does not make, and both are fixed: a link under the 24 px minimum size, and the services list sticking out of the screen with enlarged text on a 320 px phone. The keyboard walk, focus rings, contrast, text spacing, page structure and reduced motion all pass. **Not done by me, and needed: a pass with a real screen reader** (checklist below). I cannot run NVDA, VoiceOver or TalkBack here, so what I did instead is read the accessibility tree and the live announcements.

## What was checked, and how

| What | WCAG | How | Result |
| --- | --- | --- | --- |
| Markup, names, roles, text contrast | many (axe rules for 2.0, 2.1, 2.2 AA and best practice) | axe-core on the live page and, in CI, on the fixture site in each state | **no violations** |
| Every control reachable and in a sensible order, focus never stuck | 2.1.1, 2.1.2, 2.4.3 | Tab through the whole page, and Shift+Tab back | pass |
| Focus ring visible, at least 3:1 against what it touches | 2.4.7, 1.4.11 | read from the computed style at each Tab stop, both themes | pass (3 px ring; worst case well over 3:1) |
| Focus never hidden behind something | 2.4.11 (new in 2.2) | what is at the focused element's centre | pass |
| Targets at least 24 px | 2.5.8 (new in 2.2) | size of every Tab stop | **one failure, fixed** |
| Borders of controls at least 3:1 | 1.4.11 | computed border against the background | pass (3.6 to 5.3 : 1) |
| Wider text spacing loses nothing | 1.4.12 | line height 1.5, letter 0.12 em, word 0.16 em, paragraphs 2 em | pass |
| Text at 200% fits, no sideways scroll at 320 px | 1.4.4, 1.4.10 | root font size 200% at 1280, 375 and 320 px | **one failure, fixed** |
| High-contrast mode | 1.4.11, 1.4.3 | Chromium forced colours: axe and the focus ring | pass |
| Reduced motion | 2.3.3, FR-31 | no endless animation and no long one | pass |
| One h1, no skipped levels, one banner, main and footer, unique ids, a name for every control, language `pt-BR`, a page title | 1.3.1, 2.4.1, 2.4.2, 3.1.1, 4.1.2 | read from the page | pass |
| What a screen reader is told when you add and remove a team | 4.1.3 | the live region text, using the keyboard only | pass: "Palmeiras adicionado. 1 time escolhido." and "Palmeiras removido. Nenhum time escolhido.", and the focus stays in the search box |

States checked: first visit; the week list with the filters and the "not covered yet" list open; with teams and services chosen; and every card state in the card gallery (live, finished, postponed, cancelled, rescheduled, unknown broadcaster, a name that looks like HTML, and so on).

## Findings and fixes

1. **"Reportar transmissão errada" link was 22 px tall** (target size, 2.5.8). It is now at least 32 px, as tall as the calendar button beside it. (`site/css/base.css`, `.match-card__report`.)
2. **Services list stuck out of a 320 px screen with text at 200%** (resize text and reflow, 1.4.4 and 1.4.10): the grid column could not shrink below its longest word, so "TV por assinatura (cabo, satélite ou operadora)" pushed the page 39 px wider than the screen. The column can now shrink and the text wraps. (`.services`, `.service`, `.service label`, `.service__includes`.) My first pass over the live site missed this because it did not enlarge the text; the new test does.

Things that looked like findings and were not: the skip link seemed "off screen" when measured, because it slides in over a fraction of a second; text clipped by design in `visually-hidden` elements; and the controls inside the closed filters panel, which are not on the page until it is opened.

## Staying true

`tests/browser/test_accessibility_audit.py` runs the same checks on every pull request, in both themes at three sizes and four states (about 57 tests): the Tab walk and Shift+Tab, focus ring contrast and visibility, target size, text spacing, 200% text, forced colours, reduced motion, the page structure, and the announcements while choosing a team. The existing tests of each feature keep running axe in their own states.

## The pass with a real screen reader (still to do: about 10 minutes)

I could not do this one, and the issue asks for it. On your iPhone with **VoiceOver** (Settings, Accessibility, VoiceOver; or triple-click the side button once set up), or on Android with **TalkBack**, open https://raissonls.github.io/ubi-ludus/ and check each line. Note anything that sounds wrong, in your own words, in the box at the end; I will fix it.

1. The page title and then "Onde assistir futebol no Brasil", heading, are announced when it loads. *Pass if you know where you are.*
2. Swipe right through the page from the top. You should meet, in this order: a link "Pular para o conteúdo", the heading, the buttons **Meus times, Hoje, Esta semana** (the chosen one is read as selected or pressed), the **Filtros** group, the match list, the "competições ainda sem dados" group, then "Quais times você segue?" and "Quais serviços você tem?", then the footer. *Pass if nothing is skipped or read twice in a confusing way.*
3. On a match card, swipe through it: you hear the teams as a heading, the competition and round, the kick-off time with the date, **where to watch** with each broadcaster and whether it is confirmed or from the rights table, and whether you can watch it. *Pass if you can decide "can I watch this?" without looking.*
4. Use the rotor (VoiceOver) or Headings navigation (TalkBack) to jump heading by heading: one top heading, then the section headings, then one per card. *Pass if the order makes sense.*
5. Open the settings (the button "Abrir os ajustes" in the header). Under "Meus times", activate "Adicionar times": the choice of teams opens (continent, country, team; or type a name in its search). Pick Palmeiras. *Pass if each step says where you are and what you chose.* Back in the settings, find "Remover Palmeiras" and activate it: "Palmeiras removido. Nenhum time escolhido."
6. Tick a service: you hear how many services are chosen and what that changes. Untick it.
7. Open "Filtros" and "competições ainda sem dados": each opens and its contents are read. Close them again.

**Your notes:**

> _(write here what sounded wrong or confusing, which phone and screen reader, and the date)_

For a desktop screen reader (NVDA on Windows, free): the same steps with the arrow keys, `H` for headings and `D` for landmarks.
