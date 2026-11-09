# ADR-004: Run only the slow checks a change needs

- **Status:** Accepted
- **Date:** 2026-11-08
- **Related:** issue [#128](../../../../issues/128) (M6 Q-06), [docs/runbook.md](../runbook.md), [`ci.yml`](../../.github/workflows/ci.yml), [`changes.py`](../../src/ubi_ludus/quality/changes.py)

## Context

The pull request check "Lint, types and tests" takes about seven minutes, and almost all of it is one step: the tests, about six and a half minutes, most of them the site's tests in a real browser. It runs in full for every pull request, including one that changes a paragraph of a document.

Two things limit what can be skipped:

- Branch protection requires two checks by name, "Lint, types and tests" and "Secret scan". A required check that is **skipped** counts as passed, and one that **never starts** blocks the merge. A job that waits for another job which can fail is skipped when it does, and lets the pull request through with no test at all.
- Many fast tests read files that look like they belong to another area: a unit test reads `docs/runbook.md`, another reads the workflows and the issue forms, another checks the size of the site's files. A rule that skipped them for a "docs only" change would let a broken document through, to fail on `main` afterwards.

## Decision

1. **Two slow parts can be left out of a pull request run; everything else always runs.**
   - `browser`: installing the browser and the browser tests. Run when the site, its tests, its fixtures, the dependencies or the CI workflow change.
   - `pipeline`: the dbt tests. Run when the pipeline, the dbt models, the data, the config, the schemas, the Python tests, the dependencies or the CI workflow change.
   - Always: lint, format, types, the site's Node tests, the other Python tests (they are fast and they read documents, workflows and templates), and the secret scan.
2. **The rules are code**, in `src/ubi_ludus/quality/changes.py`, a list of path patterns where the first match wins. It uses only the standard library, so the job can run it before anything is installed, and it has its own tests, including the two edges: a change in `tests/browser/` runs the browser tests, a change in `docs/` runs only the cheap checks.
3. **Anything unknown runs everything.** A file no pattern knows, an empty list of changes, or a failed `git diff` all run both slow parts. A test lists every tracked file and fails when one has no rule, so a new folder gets its rule on purpose.
4. **A push to `main` and a manual run always run everything**, and so does a pull request that changes `ci.yml` or `pyproject.toml`. The coverage rule (80 %) is only applied to a full run, because leaving tests out lowers it.
5. **The required checks do not change.** Same job, same name, no `needs`, no job-level `if`: the deciding step and the conditions are steps inside the job, so the check always reports a result. Only a clear `false` leaves a part out; an empty or missing answer runs it.

## Consequences

- A pull request that changes only documents, templates or another workflow skips about five minutes of browser tests. One that changes only the site skips the dbt tests (a few seconds); the saving there is small, but the rule is the same for both.
- A document or workflow change is still checked by the fast tests that read them, so the usual "docs only" slip is caught before the merge, not after.
- **The risk we accept:** a change in one area that breaks the other through a path no rule links. The pipeline writes the files the site reads, for example. Two things limit it: the site's tests read fixtures, not the pipeline's output, and every push to `main` runs everything, so a miss shows up within minutes of the merge, as a red `main`, and is fixed by reverting. If it happens, the fix is a rule in `changes.py`, with a test.
- The deciding step needs the history between the two commits, so the checkout fetches all of it (a few seconds for this repository).
- The list of areas is a second place that names the folders. The test that every tracked file has a rule is what keeps it from going stale.

## Alternatives considered

| Option | Why not |
| --- | --- |
| `paths:` / `paths-ignore:` on the workflow | A workflow that is not started leaves the required check "pending" forever and blocks the merge. It also cannot express "run this part, not that one". |
| A separate job for each area, with `needs` and `if` | Skipped jobs count as passed, and a failed deciding job would skip them all and let a pull request through. It also changes the names of the checks that branch protection requires. |
| A marketplace action that filters paths | A third-party action with a pinned SHA to maintain, for a rule list of thirty lines. |
| Skip every test for a change in documents | The fast tests that read documents, workflows and templates would not run, and a broken one would fail on `main` after the merge. |
| Cache or shard the browser tests instead | Worth doing later, and it does not exclude this. It does not help a document change, which needs none of them. |
