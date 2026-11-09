"""Which slow checks a pull request needs, and how the CI workflow uses the answer (M6 Q-06)."""

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from ubi_ludus.quality import changes
from ubi_ludus.quality.changes import RULES, Areas, classify, needs

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"


# --- the rules --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "browser", "pipeline"),
    [
        ("tests/browser/test_hero.py", True, False),  # the edge the issue names
        ("tests/browser/site_browser.py", True, False),
        ("site/js/home.js", True, False),
        ("site/css/base.css", True, False),
        ("tests/fixtures/site/data/matches.json", True, False),
        ("docs/runbook.md", False, False),  # the other edge: only the cheap checks
        ("docs/adr/ADR-004-faster-checks.md", False, False),
        ("README.md", False, False),
        ("CONTRIBUTING.md", False, False),
        (".github/pull_request_template.md", False, False),
        (".github/ISSUE_TEMPLATE/bug-report.yml", False, False),
        (".github/workflows/lighthouse.yml", False, False),
        (".github/CODEOWNERS", False, False),
        ("src/ubi_ludus/pipeline/publish.py", False, True),
        ("dbt/models/matches.sql", False, True),
        ("data/rights/rights.yml", False, True),
        ("schemas/match.schema.json", False, True),
        ("config/competitions.yml", False, True),
        ("tests/unit/test_rights.py", False, True),
        ("tests/fixtures/football_data/matches.json", False, True),
        ("pyproject.toml", True, True),  # the dependencies are shared
        (".github/workflows/ci.yml", True, True),  # the workflow itself is the thing under test
        (".pre-commit-config.yaml", True, True),
    ],
)
def test_each_kind_of_file_needs_the_slow_parts_that_check_it(
    path: str, browser: bool, pipeline: bool
) -> None:
    found = classify([path])
    assert (found.browser, found.pipeline) == (browser, pipeline), found.reason


def test_a_file_in_a_folder_nobody_listed_runs_everything() -> None:
    found = classify(["newfolder/thing.py"])
    assert (found.browser, found.pipeline) == (True, True)
    assert "newfolder/thing.py" in found.reason
    assert needs("newfolder/thing.py") is None


def test_one_unknown_file_among_documents_still_runs_everything() -> None:
    found = classify(["docs/runbook.md", "mystery.bin"])
    assert (found.browser, found.pipeline) == (True, True)


def test_no_changed_files_runs_everything_and_says_why() -> None:
    for nothing in ([], [""], ["  "]):
        found = classify(nothing)
        assert (found.browser, found.pipeline) == (True, True)
        assert "no changed files" in found.reason


def test_a_mixed_change_runs_the_union() -> None:
    found = classify(["site/js/home.js", "docs/runbook.md"])
    assert (found.browser, found.pipeline) == (True, False)
    found = classify(["site/js/home.js", "src/ubi_ludus/pipeline/run.py"])
    assert (found.browser, found.pipeline) == (True, True)
    found = classify(["docs/runbook.md", ".github/CODEOWNERS"])
    assert (found.browser, found.pipeline) == (False, False)
    assert "no slow part" in found.reason


def test_windows_paths_and_a_leading_dot_slash_are_read_the_same() -> None:
    assert needs("site\\js\\home.js") == needs("site/js/home.js")
    assert needs("./docs/runbook.md") == frozenset()
    assert needs("./.github/CODEOWNERS") == frozenset()  # the dot of .github is kept


def test_the_first_matching_rule_wins_so_workflows_ci_is_not_swallowed_by_the_general_one() -> None:
    patterns = [pattern for pattern, _ in RULES]
    assert patterns.index(".github/workflows/ci.yml") < patterns.index(".github/workflows/*")


def test_every_file_in_the_repository_today_is_in_a_known_area() -> None:
    """A new top-level file or folder runs everything, which is right, but it should be a choice:
    this fails when something is added, so the rule for it is written on purpose."""
    listed = subprocess.run(  # noqa: S603 - fixed command
        ["git", "ls-files"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert listed
    unknown = [path for path in listed if needs(path) is None]
    assert unknown == [], f"add a rule in src/ubi_ludus/quality/changes.py for: {unknown[:5]}"


# --- reading the changes from git and the command line ------------------------------------------


def git(folder: Path, *args: str) -> str:
    return subprocess.run(  # noqa: S603 - fixed command
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],  # noqa: S607
        cwd=folder,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_the_changed_files_are_those_between_the_base_and_the_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "one")
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "x.md").write_text("x", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "two")
    head = git(tmp_path, "rev-parse", "HEAD").strip()
    monkeypatch.chdir(tmp_path)
    assert changes.changed_files(base, head) == ["docs/x.md"]


def test_a_failed_git_diff_runs_everything_instead_of_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert changes.main(["--base", "not-a-commit", "--head", "not-a-commit"]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["browser=true", "pipeline=true"]
    assert "everything" in captured.err


def test_all_prints_the_two_lines_a_workflow_appends_to_its_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert changes.main(["--all"]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["browser=true", "pipeline=true"]
    assert Areas(False, True, "x").lines() == ["browser=false", "pipeline=true"]


def test_the_command_needs_a_mode(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        changes.main([])
    assert "--all" in capsys.readouterr().err


# --- the workflow ------------------------------------------------------------------------------


def checks_job() -> dict[str, Any]:
    document = yaml.safe_load(CI.read_text(encoding="utf-8"))
    job: dict[str, Any] = document["jobs"]["checks"]
    return job


def test_the_required_check_keeps_its_name_and_never_waits_for_another_job() -> None:
    """Branch protection requires "Lint, types and tests". A job that can be skipped, or that waits
    for one that can fail, would let a pull request through with no result."""
    job = checks_job()
    assert job["name"] == "Lint, types and tests"
    assert "needs" not in job and "if" not in job
    document = yaml.safe_load(CI.read_text(encoding="utf-8"))
    assert document["jobs"]["secret-scan"]["name"] == "Secret scan"
    assert "if" not in document["jobs"]["secret-scan"]


def test_lint_format_types_and_the_node_tests_always_run() -> None:
    steps = {step["name"]: step for step in checks_job()["steps"] if "name" in step}
    for name in ("Lint", "Format check", "Type-check", "Site unit tests (Node)"):
        assert "if" not in steps[name], name


def test_the_workflow_asks_the_rules_and_a_missing_answer_runs_the_part() -> None:
    steps = checks_job()["steps"]
    checkout = steps[0]
    assert checkout["with"]["fetch-depth"] == 0  # git needs the history between the two commits
    decide = next(step for step in steps if step.get("id") == "areas")
    assert "ubi_ludus.quality.changes --base" in decide["run"]
    assert "--all" in decide["run"] and "set -o pipefail" in decide["run"]
    browser = next(step for step in steps if "playwright install" in step.get("run", ""))
    assert browser["if"].startswith("steps.areas.outputs.browser != 'false'")
    tests = next(step for step in steps if step.get("name", "").startswith("Tests"))
    run = tests["run"]
    assert '[ "$RUN_BROWSER" != "false" ] || expression="not browser"' in run
    assert 'not dbt"' in run and "--no-cov" in run  # coverage is measured on the full run only
    assert tests["env"]["UBI_LUDUS_REQUIRE_BROWSER"] == "1"


def test_a_full_run_is_the_same_command_as_before() -> None:
    run = next(
        step["run"] for step in checks_job()["steps"] if step.get("name", "").startswith("Tests")
    )
    assert "pytest -n auto --dist loadfile\n" in run + "\n"
