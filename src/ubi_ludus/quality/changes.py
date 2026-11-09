"""Which parts of the checks a pull request needs (M6 Q-06, ADR-004).

The main check takes about seven minutes, most of it the browser tests. A change to a document does
not need them. This reads the files a pull request changes and says which of the two slow parts
to run:

``browser``   the site's tests in a real browser (and installing that browser): when the site, its
              tests, its fixtures or the dependencies change.
``pipeline``  the dbt tests, which build the data models on fixtures: when the pipeline, the data,
              the schemas or the dependencies change.

Everything cheap always runs, whatever changed: lint, formatting, types, the site's Node tests and
the rest of the Python tests (which also read documents, workflows and templates, so a change to
one of those is caught). A file this does not know runs both slow parts, so a new folder can never
slip through unchecked. Pushes to ``main`` and manual runs always run everything.

Standard library only: the CI job runs it before anything is installed.

Usage (CI)::

    python -m ubi_ludus.quality.changes --base <sha> --head <sha>   # a pull request
    python -m ubi_ludus.quality.changes --all                       # push to main, manual run

It prints ``browser=true|false`` and ``pipeline=true|false``, one per line, ready to append to the
``GITHUB_OUTPUT`` file, and a short explanation on standard error.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase

#: Folders and files, and what they need. The first match wins, so specific rules go first.
#: "none" means no slow part: the cheap checks cover it.
RULES: tuple[tuple[str, frozenset[str]], ...] = (
    # --- the site -----------------------------------------------------------------------------
    ("site/*", frozenset({"browser"})),
    ("tests/browser/*", frozenset({"browser"})),
    ("tests/fixtures/site/*", frozenset({"browser"})),
    # --- the pipeline and its data ---------------------------------------------------------
    ("src/*", frozenset({"pipeline"})),
    ("dbt/*", frozenset({"pipeline"})),
    ("data/*", frozenset({"pipeline"})),
    ("config/*", frozenset({"pipeline"})),
    ("schemas/*", frozenset({"pipeline"})),
    ("tests/unit/*", frozenset({"pipeline"})),
    ("tests/e2e/*", frozenset({"pipeline"})),
    ("tests/fixtures/*", frozenset({"pipeline"})),
    ("tests/*.py", frozenset({"pipeline"})),
    # --- what both depend on ---------------------------------------------------------------
    ("pyproject.toml", frozenset({"browser", "pipeline"})),
    (".github/workflows/ci.yml", frozenset({"browser", "pipeline"})),
    (".pre-commit-config.yaml", frozenset({"browser", "pipeline"})),
    # --- nothing slow: documents, templates, the other workflows ---------------------------
    ("docs/*", frozenset()),
    (".github/workflows/*", frozenset()),
    (".github/ISSUE_TEMPLATE/*", frozenset()),
    (".github/pull_request_template.md", frozenset()),
    (".github/CODEOWNERS", frozenset()),
    (".github/dependabot.yml", frozenset()),
    ("*.md", frozenset()),
    ("LICENSE", frozenset()),
    (".gitignore", frozenset()),
    (".env.example", frozenset()),
    (".gitattributes", frozenset()),
)


@dataclass(frozen=True)
class Areas:
    """The slow parts of the checks to run, and why."""

    browser: bool
    pipeline: bool
    reason: str

    def lines(self) -> list[str]:
        return [f"browser={str(self.browser).lower()}", f"pipeline={str(self.pipeline).lower()}"]


def needs(path: str) -> frozenset[str] | None:
    """The slow parts a changed file needs, or None when no rule knows the file."""
    clean = path.replace("\\", "/").removeprefix("./")
    for pattern, wanted in RULES:
        if fnmatchcase(clean, pattern):
            return wanted
    return None


def classify(paths: Iterable[str]) -> Areas:
    """What to run for these changed files. No files at all (an empty diff) runs both, and so
    does a file that no rule knows."""
    changed = [p for p in paths if p.strip()]
    if not changed:
        return Areas(True, True, "no changed files were found, so everything runs")
    wanted: set[str] = set()
    for path in changed:
        found = needs(path)
        if found is None:
            return Areas(True, True, f"{path} is not in any known area, so everything runs")
        wanted |= found
    reason = f"{len(changed)} changed file(s) need: " + (
        ", ".join(sorted(wanted)) or "no slow part"
    )
    return Areas("browser" in wanted, "pipeline" in wanted, reason)


def changed_files(base: str, head: str) -> list[str]:
    """The files that differ between two commits, from git."""
    result = subprocess.run(  # noqa: S603 - fixed command, the shas come from the workflow
        ["git", "diff", "--name-only", f"{base}...{head}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"git diff failed: {result.stderr.strip()}")
    return result.stdout.splitlines()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--all", action="store_true", help="run everything (push to main, manual)")
    parser.add_argument("--base", help="the commit the pull request is based on")
    parser.add_argument("--head", help="the last commit of the pull request")
    args = parser.parse_args(argv)
    if args.all:
        areas = Areas(True, True, "not a pull request, so everything runs")
    elif args.base and args.head:
        try:
            areas = classify(changed_files(args.base, args.head))
        except SystemExit as exc:  # git could not tell: run everything rather than nothing
            print(f"{exc}; running everything", file=sys.stderr)
            areas = Areas(True, True, "git could not list the changes, so everything runs")
    else:
        parser.error("give --all, or --base and --head")
    print("\n".join(areas.lines()))
    print(f"Slow checks: {areas.reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
