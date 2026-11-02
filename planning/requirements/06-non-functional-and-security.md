# Requirements: non-functional and security

Source: PRD sections 7 and 13 ([PRD](../../docs/PRD.md)). The PRD is the source of truth; if it changes, update this file.

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| **Cost** | R$ 0/month. Only free tiers (GitHub Free, free provider plans, free e-mail sending). |
| **Performance** | Lighthouse (mobile) ≥ 90 for Performance, Accessibility, Best Practices and SEO. Largest Contentful Paint ≤ 2.5 s on simulated 4G. Total JS ≤ 100 KB gzipped. |
| **Accessibility** | WCAG 2.2 AA. Full keyboard navigation, visible focus, sufficient contrast, labelled controls. |
| **Reliability** | Pipeline success ≥ 95% over 30 days. If providers fail, the previous good dataset stays published and the freshness indicator warns the visitor. |
| **Privacy** | No accounts, no cookies, no third-party trackers, no analytics that identify people. Preferences stay in the browser. Privacy notice in the footer. Compatible with Brazil's LGPD for this scope. |
| **Browser support** | Last 2 versions of Chrome, Safari, Firefox and Edge, on mobile and desktop. |
| **Localisation** | pt-BR UI. Strings isolated in one file to allow future locales. Dates, times and plurals formatted with `Intl`. |
| **Maintainability** | Type hints, linting and formatting enforced; ≥ 80% line coverage on pipeline code; architecture decisions recorded in `docs/adr/`. |
| **Documentation** | All repository documentation in English: README, PRD, architecture, contributing guide, runbook, ADRs. |

## 13. Security and privacy

Because the repository and site are public from day one, the following are **requirements**, not nice-to-haves.

**Secrets and access**
- E-mail credentials and any API keys live only in GitHub Secrets. The owner's e-mail address is never committed.
- Workflow `permissions:` set explicitly to the minimum per job. Third-party actions pinned to commit SHAs. Dependabot enabled for Actions, Python and npm.
- Branch protection on `main`; required status checks; no force pushes. Two-factor authentication on the owner's GitHub account.
- Secret scanning and push protection enabled; a secret-scan step in CI.

**Application security**
- The site renders data with safe DOM APIs (`textContent`), never raw `innerHTML` with data.
- Content Security Policy via `<meta http-equiv>` (GitHub Pages cannot set headers): no inline scripts, same-origin scripts and styles, no third-party hosts.
- No third-party scripts or fonts loaded from CDNs (self-host to avoid supply-chain risk and tracking). If any external asset is unavoidable, use Subresource Integrity.
- Inputs from URL parameters are validated against an allow-list of team and service IDs.
- Generated `.ics` and e-mail content are escaped.

**Privacy**
- No cookies, no analytics that identify visitors. If aggregate analytics are ever added, they must be cookieless and documented.
- Team and service choices never leave the browser.
- A short privacy notice in the site footer and a `PRIVACY.md` in the repo.

**Operational**
- Provider API usage respects rate limits and terms; user-agent identifies the project.
- Runbook covers: rotating a leaked secret, switching provider, disabling the e-mail, rolling back the site.
