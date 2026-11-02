---
id: M3-01
title: Site scaffold, design tokens, themes and security baseline
milestone: M3
priority: Must
estimate_h: 4
status: todo
requirements: [FR-31, NFR-security, NFR-i18n]
depends_on: [M1-01]
---

# M3-01 · Site scaffold, design tokens, themes and security baseline

**Milestone:** M3 Website core (Nov 23 - Dec 6) · **Priority:** Must · **Estimate:** 4 h

## Why

Everything else in the site builds on this: structure, look, safe defaults and the pt-BR string file.

## Definition of done

- [ ] `site/` with ES modules, no framework, small bundle.
- [ ] Design tokens (colour, type, spacing, motion) with light and dark themes; respects `prefers-color-scheme` and `prefers-reduced-motion`.
- [ ] Content Security Policy via meta tag, no inline scripts, no third-party hosts; fonts self-hosted.
- [ ] All UI strings in `site/i18n/pt-BR.json`; dates and times formatted with `Intl`.
- [ ] Footer privacy notice and `PRIVACY.md`.
- [ ] Front-end CI checks added: axe accessibility and a bundle size check.

## Notes

_Add decisions, links and anything learned while doing the task._
