# Security checklist and go-public plan

Owner: Raisson Leal Silva. Created for issue [#6](../../../issues/6) (M0-06); reused as the sign-off list in [#39](../../../issues/39) (M5-04). Source of the requirements: [PRD section 13](PRD.md#13-security-and-privacy).

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

- [ ] M0 is closed: all six M0 tasks done, including ADR-001 (#5).
- [ ] Full-history secret scan is clean. CI runs gitleaks over the whole history, so check that the latest run on `main` is green, and run `pre-commit run gitleaks --all-files` locally right before flipping.
- [ ] No raw provider data in the repo. `research-samples/` is git-ignored; confirm with `git ls-files | grep research-samples` (should print nothing).
- [ ] No API keys in files: `.env` is git-ignored and `.env.example` has empty values.
- [ ] README, PRD and docs read once as a stranger would, looking for anything private.
- [ ] Commit e-mail checked (see [Account](#account-and-personal-data)).
- [ ] Issues are read once: they become public with the repo. The project board stays private unless you change it.

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

- [ ] Settings, General, Danger Zone: change visibility to **Public**.
- [ ] **Protect `main`** (Settings, Branches). Rules: require a pull request before merging; require status checks to pass, using the two checks `Lint, types and tests` and `Secret scan`; block force pushes; block branch deletion. Do not require approvals while there is a single maintainer (nobody could merge), but turn that on when a second person joins.
- [ ] Settings, General, Pull Requests: allow squash merging only, and enable "Automatically delete head branches".
- [ ] Repeat the deliberate-failure test from M0-04 once: a red check must now block the merge button.

### Scanning and updates

- [ ] Settings, Advanced Security: enable **secret scanning** and **push protection**.
- [ ] Enable **code scanning**, CodeQL default setup (Python now; JavaScript when the site exists).
- [x] **Dependabot alerts** are on (enabled 2026-11-02 on the private repo, through the API).
- [ ] Enable **Dependabot security updates**, if the settings offer them.
- [x] `SECURITY.md` is in the repository. It tells people to use GitHub's private "Report a vulnerability" button.
- [ ] Enable **private vulnerability reporting** (Settings, Advanced Security) once the repo is public, so that button exists.

### GitHub Actions

- [ ] Settings, Actions, General: turn on the policy that **requires actions to be pinned to a full-length commit SHA** (the workflow already complies). Dependabot alerts for Actions only work for actions with version tags, so keep the version in the comment next to each SHA.
- [ ] Workflow permissions stay on "Read repository contents" and "Allow GitHub Actions to create and approve pull requests" stays off (both already set).
- [ ] GitHub Pages and the API keys as repository secrets are set up in M4 (#32), not before.

## Checklist from PRD section 13 (used for the M5-04 sign-off)

| Requirement | Done in | Status |
|---|---|---|
| E-mail credentials and API keys only in GitHub Secrets | M4-02 (#31) | open |
| Owner's e-mail address never committed | M4-02 (#31) | open |
| Workflow `permissions:` minimal per job | M0-04 (#4) | done |
| Third-party actions pinned to commit SHAs | M0-04 (#4) | done |
| Dependabot for Actions and Python | M0-04 (#4) | done |
| Dependabot for npm | when the site gets a `package.json` (M3-01, #18) | open |
| Branch protection, required checks, no force pushes | go-public day (above) | open |
| Two-factor authentication on the owner's account | M0-06 (#6), confirmed 2026-11-02 | done |
| Secret scanning and push protection | go-public day (above) | open |
| Secret-scan step in CI | M0-04 (#4) | done |
| Site renders data with `textContent`, not raw `innerHTML` | M3-05 (#22) | open |
| Content Security Policy via meta tag, no inline scripts | M3-01 (#18) | open |
| No third-party scripts or fonts; self-host | M3-01 (#18) | open |
| URL parameters validated against an allow-list | M3-09 (#26) | open |
| Generated `.ics` and e-mail content escaped | M3-12 (#29), M4-01 (#30) | open |
| No cookies or identifying analytics; privacy notice and `PRIVACY.md` | M3-01 (#18), M3-02 (#19) | open |
| Preferences never leave the browser | M3-02 (#19) | open |
| Provider calls within rate limits; user-agent identifies the project | M1-03 (#9), M1-05 (#11), M1-07 (#53) | open |
| Runbook: rotate a leaked secret, switch provider, disable e-mail, roll back | M4-06 (#35) | open |
| Provider terms re-checked before launch | M5-04 (#39) | open |

## Ongoing habits

- Merge or close Dependabot pull requests each week, after CI passes.
- If a key ever leaks: revoke it at the provider first, then replace it in GitHub Secrets, then clean the code. The runbook (M4-06) will hold the exact steps.
- Re-read the providers' terms before any change that could affect them: ads, paid features, selling data, crests (see [provider comparison](research/provider-comparison.md)).
