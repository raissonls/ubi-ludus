"""The runbook (M4-06) stays true: what it names exists, and what exists is in it."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "docs" / "runbook.md"
WORKFLOWS = ROOT / ".github" / "workflows"
TEXT = RUNBOOK.read_text(encoding="utf-8")


def anchors(markdown: str) -> set[str]:
    """The anchors GitHub makes for the headings of a Markdown file."""
    found = set()
    for heading in re.findall(r"^#{1,6}\s+(.*?)\s*$", markdown, flags=re.M):
        slug = re.sub(r"[^\w\s-]", "", heading.lower().replace("`", "")).strip()
        found.add(re.sub(r"\s", "-", slug))
    return found


def workflow(name: str) -> dict[Any, Any]:
    document = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_it_covers_what_the_issue_asks_for() -> None:
    headings = anchors(TEXT)
    assert {
        "rotating-a-leaked-secret",
        "switching-provider",
        "disabling-the-e-mail",
        "rolling-back-the-site",
        "the-weekly-routine",
        "running-the-pipeline-on-your-machine",
        "reading-a-failing-dbt-test",
        "when-something-is-red",
    } <= headings


def test_every_link_goes_to_a_file_that_exists_and_a_heading_that_exists() -> None:
    links = re.findall(r"\]\((?!https?:)([^)\s]+)\)", TEXT)
    assert links
    for link in links:
        target, _, anchor = link.partition("#")
        path = RUNBOOK if target == "" else (RUNBOOK.parent / target).resolve()
        assert path.exists(), f"{link}: no such file"
        if anchor and path.suffix == ".md":
            assert anchor in anchors(path.read_text(encoding="utf-8")), f"{link}: no such heading"


def test_the_in_page_shortcuts_at_the_top_go_to_sections_that_exist() -> None:
    top = TEXT.split("## What runs, and where")[0]
    for anchor in re.findall(r"\]\(#([^)]+)\)", top):
        assert anchor in anchors(TEXT), anchor


def test_every_secret_the_workflows_use_is_in_the_rotation_table() -> None:
    used: set[str] = set()
    for path in WORKFLOWS.glob("*.yml"):
        used |= set(re.findall(r"secrets\.([A-Z_]+)", path.read_text(encoding="utf-8")))
    used.discard("GITHUB_TOKEN")  # made by GitHub for each run, nobody rotates it
    assert used == {
        "FOOTBALL_DATA_TOKEN",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "EMAIL_FROM",
        "EMAIL_TO",
    }
    table = TEXT.split("## Rotating a leaked secret")[1].split("## Switching provider")[0]
    for name in used:
        assert f"`{name}`" in table, name


def test_the_commands_name_workflows_and_inputs_that_exist() -> None:
    commands = re.findall(
        r"gh workflow (?:run|enable|disable) ([\w.-]+\.yml)((?: -f [\w]+=\w+)*)", TEXT
    )
    assert commands
    for file, options in commands:
        document = workflow(file)  # the file exists
        assert "workflow_dispatch" in document[True], f"{file} cannot be started by hand"
        inputs = (document[True]["workflow_dispatch"] or {}).get("inputs", {})
        for name in re.findall(r"-f (\w+)=", options):
            assert name in inputs, f"{file} has no input {name}"


def test_the_e_mail_switch_and_the_smtp_variables_are_what_the_workflow_reads() -> None:
    pipeline = (WORKFLOWS / "pipeline.yml").read_text(encoding="utf-8")
    assert "vars.EMAIL_ENABLED != 'false'" in pipeline and "EMAIL_ENABLED" in TEXT
    for name in ("SMTP_HOST", "SMTP_PORT"):
        assert f"vars.{name}" in pipeline and f"gh variable set {name}" in TEXT


def test_every_dbt_test_is_explained_and_none_that_is_not_there_is() -> None:
    table = TEXT.split("### Reading a failing dbt test")[1].split("To run dbt on its own")[0]
    named = set(re.findall(r"^\| `([a-z_]+)` \|", table, flags=re.M))
    on_disk = {path.stem for path in (ROOT / "dbt" / "tests").glob("*.sql")}
    assert named == on_disk


def test_the_dbt_tests_that_only_warn_are_the_ones_the_runbook_says_warn() -> None:
    table = TEXT.split("### Reading a failing dbt test")[1].split("To run dbt on its own")[0]
    for path in (ROOT / "dbt" / "tests").glob("*.sql"):
        warns = "severity='warn'" in path.read_text(encoding="utf-8")
        row = next(r for r in table.splitlines() if r.startswith(f"| `{path.stem}`"))
        assert ("| warns |" in row) is warns, f"{path.stem}: the runbook says the opposite"


@pytest.mark.parametrize("name", ["EMAIL_ENABLED"])
def test_the_variable_is_not_a_secret_and_is_never_given_a_value_in_a_file(name: str) -> None:
    for path in WORKFLOWS.glob("*.yml"):
        assert f"{name}:" not in path.read_text(encoding="utf-8")  # only read with vars., never set


def test_the_audit_folder_the_routine_points_to_has_its_template() -> None:
    assert (ROOT / "docs" / "audits" / "README.md").exists()
    assert "docs/audits/YYYY-MM-DD.md" in TEXT
