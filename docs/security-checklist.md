# Security checklist and go-public plan

Owner: Raisson Leal Silva. Signed off on 2026-11-08 ([#39](../../../issues/39), M5-04), except the owner steps at the end of the sign-off. Created for issue [#6](../../../issues/6) (M0-06); reused as the sign-off list in [#39](../../../issues/39) (M5-04). Source of the requirements: [PRD section 13](PRD.md#13-security-and-privacy).

Tick items as they are done. Nothing here is legal advice.

## Decision: when the repository goes public

**Decided 2026-11-01: after M0 closes and before M1 starts. Target: 9 November 2026.**

Why then:

- A red CI check cannot block a merge on a private repo on GitHub Free. Branch protection and rulesets return "Upgrade to GitHub Pro or make this repository public" (checked with the GitHub API on 2026-11-01).
- Secret scanning, push protection and CodeQL are free only on public repositories. They matter most from M1 on, when the code starts handling API keys.
- GitHub Pages on Free needs a public repository, so the site could never ship from a private one.
- Actions are free without limit on public repositories (private repos on Free get a monthly allowance).
- Today the repository holds only the PRD, planning docs and a code scaffold. There is nothing to protect that is not already meant to be public.

### Before flipping to public

Run on 2026-11-02:

- [x] M0 is closed: all six M0 tasks done, including ADR-001 (#5).
- [x] Full-history secret scan is clean: gitleaks over all 25+ commits on every ref found nothing, and the latest run on `main` is green.
- [x] No raw provider data in the repo. `research-samples/` is git-ignored and nothing like it is tracked.
- [x] No API keys in files. `.env` is git-ignored and `.env.example` has empty values. The real key values were also searched for in every tracked file, commit message, issue, pull request and comment: no match.
- [x] Docs read as a stranger would. The README status line was out of date ("no code yet") and was fixed. No local paths or employer names appear in files, issues or pull requests.
- [ ] Commit e-mail checked (see [Account](#account-and-personal-data)). The scan found one personal address in the author field of pre-squash commits (13 by 2026-11-08, 3 of them on `main`). It cannot be removed from those commits, so the account settings in the Account section must be on. Still the owner's to do.
- [x] Issues read: 55 issues, 11 pull requests and 8 comments were scanned for e-mail addresses, tokens and local paths. Nothing found. They become public with the repo. The project board stays private unless you change it.

## What GitHub Free allows

Read from the GitHub docs and the API on 2026-11-01. Where the docs were unclear, the item says to verify in the settings.

| Feature | Private repo (Free) | Public repo (Free) |
|---|---|---|
| Branch protection | No (API: upgrade or make public) | Yes, expected. Verify in the settings on the day. |
| Rulesets | No (same API response) | The docs list rulesets for Team and Enterprise, so it may not be available. Use classic branch protection if so. |
| GitHub Pages | No | Yes |
| Secret scanning, push protection | No | Yes |
| CodeQL code scanning | No | Yes |
| Dependabot alerts | Yes (switched on 2026-11-02) | Yes |
| Dependabot version updates | Yes (config merged in M0-04) | Yes |
| GitHub Actions | Monthly allowance, then blocked unless a payment method exists | Free |

## Account and personal data

- [x] **Two-factor authentication is on** for the GitHub account. Confirmed by the owner on 2026-11-02 (the API does not expose this setting, so it cannot be verified automatically).
- [ ] Recovery codes are saved somewhere safe, not in this repo.
- [ ] **Commit e-mail.** Squash-merged commits on `main` already use GitHub's noreply address, but the first empty commit and the pre-squash branch commits (visible on pull request pages once the repo is public) show a personal e-mail. In GitHub, Settings, Emails: turn on "Keep my email addresses private" and "Block command line pushes that expose my email". Locally, `git config user.email` is set to the noreply address for this repository.
- [ ] Optional: sign commits (GitHub shows a "Verified" badge). Not required for Phase 1.

## On the day the repository goes public

Do these in order, in the GitHub web settings. Items marked "now" can already be done today.

### Visibility and branch protection

- [x] Settings, General, Danger Zone: change visibility to **Public**. Done 2026-11-02; confirmed with the API and a logged-out request.
- [x] **Protect `main`** (Settings, Branches). Rules: require a pull request before merging; require status checks to pass, using the two checks `Lint, types and tests` and `Secret scan`; block force pushes; block branch deletion. Do not require approvals while there is a single maintainer (nobody could merge), but turn that on when a second person joins. Done 2026-11-02 and read back from the API: both checks required, pull request required with no approvals, no force pushes or deletion, linear history, and it applies to administrators too.
- [x] Settings, General, Pull Requests: allow squash merging only, and enable "Automatically delete head branches". Done 2026-11-02 (merge commits and rebase merges are off).
- [x] Repeat the deliberate-failure test from M0-04 once: a red check must now block the merge button. Done 2026-11-02 on throwaway PR #68: the red check made the pull request BLOCKED, and both a normal merge and a direct API merge as the admin were refused ("Required status check ... is failing"). The PR was closed without merging.

### Scanning and updates

- [x] Settings, Advanced Security: enable **secret scanning** and **push protection**. Done 2026-11-02, read back from the API.
- [x] Enable **code scanning**, CodeQL default setup (Python now; JavaScript when the site exists). Configured 2026-11-02 (Python and GitHub Actions workflows). Check the Security tab after its first run.
- [x] **Dependabot alerts** are on (enabled 2026-11-02 on the private repo, through the API).
- [x] Enable **Dependabot security updates**, if the settings offer them. Done 2026-11-02.
- [x] `SECURITY.md` is in the repository. It tells people to use GitHub's private "Report a vulnerability" button.
- [x] Enable **private vulnerability reporting** (Settings, Advanced Security) once the repo is public, so that button exists. Done 2026-11-02.

### GitHub Actions

- [x] Settings, Actions, General: turn on the policy that **requires actions to be pinned to a full-length commit SHA** (the workflow already complies). Dependabot alerts for Actions only work for actions with version tags, so keep the version in the comment next to each SHA. Done 2026-11-02, read back from the API.
- [x] Workflow permissions stay on "Read repository contents" and "Allow GitHub Actions to create and approve pull requests" stays off (both already set). Verified 2026-11-02 through the API.
- [x] GitHub Pages and the API keys as repository secrets were set up in M4 (#32).

## Checklist from PRD section 13 (the M5-04 sign-off, 2026-11-08)

Each row was checked against the repository and against GitHub's own settings on 2026-11-08, not copied from an earlier note. "How it was checked" says what was looked at, so the check can be repeated.

| Requirement | Status | How it was checked |
|---|---|---|
| E-mail credentials and API keys only in GitHub Secrets | done | `gh secret list` shows six secrets (names only). The real value of every key in the git-ignored `.env` was searched for in the whole history of every ref (about 4 MB of patches) and in every tracked file: **no match**. `.env` is git-ignored and `.env.example` has empty values. The unused `API_FOOTBALL_KEY` secret is still stored: see "Left for the owner" below. |
| Owner's e-mail address never committed | done, one caveat | The value of `EMAIL_TO` and `EMAIL_FROM` is in no commit and no tracked file. Caveat: 3 commits on `main` (and 10 on old branches) were authored with a personal address before the noreply setting was used; all 45 later commits on `main` use the noreply address. History on a protected branch is not rewritten. See "Left for the owner". |
| Workflow `permissions:` minimal per job | done | Reviewed one by one, see the table below. Every workflow starts from `permissions: {}` and `tests/unit/test_workflows.py` fails if one does not, or if a job other than the named ones can write issues or Pages. The repository default is "read" and Actions cannot approve pull requests (API). |
| Third-party actions pinned to commit SHAs | done | The repository policy "require full-length commit SHA" is on (API: `sha_pinning_required: true`) and a test checks every `uses:` line. |
| Dependabot for Actions and Python | done | `.github/dependabot.yml` has `github-actions` and `pip`. 0 open Dependabot alerts (API). |
| Dependabot for npm | not applicable | `site/package.json` has no dependencies and no lock file: it only marks the files as ES modules. Lighthouse is fetched with `npx` at an exact version in `lighthouse.yml` (not hash-pinned; tracked in #70). |
| Branch protection, required checks, no force pushes | done | Read back from the API: pull request required, checks `Lint, types and tests` and `Secret scan` required, no force pushes, no deletion, linear history, applies to administrators. |
| Two-factor authentication on the owner's account | done | Confirmed by the owner on 2026-11-02 (GitHub does not expose it). |
| Secret scanning and push protection | done | Both `enabled` in the repository's security settings; 0 open secret-scanning alerts and 0 open code-scanning alerts. |
| Secret-scan step in CI | done | gitleaks job `Secret scan` in `ci.yml`, a required check; green on every merged pull request. |
| Site renders data with `textContent`, not raw `innerHTML` | done | No `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval` or `new Function` anywhere in `site/js`, and `tests/unit/test_site.py` fails if one is added. |
| Content Security Policy via meta tag, no inline scripts | done | `site/index.html` sets `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'none'`. No inline script or style exists (the browser tests would fail). |
| No third-party scripts or fonts; self-host | done | The only outside addresses in the page are links the visitor clicks (the repository, the privacy page, the issue form, football-data.org). The policy above blocks any other load. |
| URL parameters validated against an allow-list | done | `site/js/url-state.js`: views, competitions, broadcasters, teams and services are checked against the ids the site has; the search text is cleaned of control characters and cut to 60 characters; lists are cut to 50. Tested. |
| Generated `.ics` and e-mail content escaped | done | `site/js/ics.js` escapes backslash, semicolon, comma and new lines (`site/test/ics.test.js`); `email/render.py` passes every value through `html.escape` and `tests/unit/test_email_render.py` renders a hostile name (`<script>`, an `onerror` image, line breaks) and checks nothing survives. |
| No cookies or identifying analytics; privacy notice and `PRIVACY.md` | done | No `document.cookie` and no analytics in `site/`; `PRIVACY.md` and the footer notice exist. |
| Preferences never leave the browser | done | Saved only in `localStorage` (`preferences.js`); the policy allows connections to the site's own address only, so nothing could be sent elsewhere. |
| Provider calls within rate limits; user-agent identifies the project | done | One provider, 9 calls a run, once a day, through the limiter and the per-run call budget in `providers/guard.py` (the free plan allows 10 a minute). The user-agent is `ubi-ludus/<version> (+repository address)`. |
| Runbook: rotate a leaked secret, switch provider, disable e-mail, roll back | done, one step untried | [Runbook](runbook.md). The outage drill ran live on 2026-11-08. The site rollback (re-running an old deploy) has **not** been tried on the live site: see the runbook. |
| Provider terms re-checked before launch | done | Re-read on 2026-11-08, see below. |

### Workflow permissions, one by one (2026-11-08)

| Workflow, job | Permissions | Why that much |
|---|---|---|
| `ci.yml`, `checks` | contents: read | check out the code |
| `ci.yml`, `secret-scan` | contents: read, pull-requests: read | gitleaks reads the commits of a pull request; comments are off |
| `pipeline.yml`, `build` | contents: read | check out; the provider token reaches one step only |
| `pipeline.yml`, `deploy` | pages: write, id-token: write | the only job that can publish the site |
| `pipeline.yml`, `email` | contents: read | the four mail secrets reach one step only |
| `pipeline.yml`, `status` | issues: write | open and close the failure issue |
| `watchdog.yml`, `keep-alive` | actions: write | switch workflows back on (the 60-day rule) |
| `watchdog.yml`, `freshness` | contents: read, issues: write | open the stale-data issue |
| `review-report.yml`, `report` | contents: read, issues: write | weekly report issue |
| `lighthouse.yml`, both jobs | contents: read | measure only; no secrets at all |

No workflow uses a `pull_request_target` trigger or runs code from a pull request with a secret.

### Provider terms (football-data.org), re-read on 2026-11-08

Source: the General Terms and Conditions on football-data.org's registration page (last updated 2018-06-01; they can be amended at any time) and its pricing page. Not legal advice.

| Rule | Where we stand |
|---|---|
| 7.1: show "Football data provided by the Football-Data.org API" somewhere visible | in the footer on every page (`site/index.html`), with a link |
| 6.1: credentials may not be stored in the code repository of an open-source project | the token exists only as a GitHub secret; searched for in the history, none found |
| 9.2: team crests and logos belong to their owners and need their consent | none used anywhere: team colours only (PRD R5), and a browser test checks the team picker has no image |
| 2.3: a key is for one application | one key, used by this one pipeline only |
| 3: fair usage, excessive use may end the account | about 9 calls a day against 10 a minute allowed |
| 9.1: after cancelling, the data may no longer be shown | would apply if the account is closed: the site would then need to stop showing it (the runbook's "Switching provider") |
| Commercial use | the terms and the pricing page do not forbid it, but the project is non-commercial and has no ads or paid features; ask the provider before that changes |
| Minimum fields published | only what a match card needs (teams, kickoff, competition, status, score) plus our own broadcaster data; raw provider payloads are never committed or served |

API-Football is no longer used ([ADR-003](adr/ADR-003-drop-api-football.md)), so its terms no longer apply; the footer no longer names it.

### Left for the owner

These cannot be done or verified from here (the automatic safety check refuses changes to the secret store):

1. **Delete the unused secret:** `gh secret delete API_FOOTBALL_KEY` (the account is suspended and nothing reads it).
2. **Commit e-mail.** In GitHub, Settings, Emails: "Keep my email addresses private" and "Block command line pushes that expose my email" (also listed under [Account](#account-and-personal-data)). The 13 older commits cannot be changed.
3. **Recovery codes** for the GitHub account are saved somewhere safe, and 2FA is still on.

## Ongoing habits

- Merge or close Dependabot pull requests each week, after CI passes.
- If a key ever leaks: revoke it at the provider first, then replace it in GitHub Secrets, then clean the code. The exact steps are in the [runbook](runbook.md#rotating-a-leaked-secret).
- Re-read the providers' terms before any change that could affect them: ads, paid features, selling data, crests (see [provider comparison](research/provider-comparison.md)).
