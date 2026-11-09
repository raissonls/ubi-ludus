"""The pull request template, the code owners and the issue forms are in place and consistent.

These files are read by GitHub, which says nothing when one is wrong: a form with a typo in a field
type simply does not show up. The checks here are the only warning.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
GITHUB = ROOT / ".github"
FORMS = sorted(
    path for path in (GITHUB / "ISSUE_TEMPLATE").glob("*.yml") if path.name != "config.yml"
)
# The labels the repository has (the defaults GitHub creates, and ours). A form that names another
# one opens an issue with no label and no error.
LABELS = {
    "bug",
    "enhancement",
    "documentation",
    "question",
    "accessibility",
    "good first issue",
    "help wanted",
    "must",
    "should",
    "could",
    "backlog",
}
FIELD_TYPES = {"markdown", "input", "textarea", "dropdown", "checkboxes"}


def load(name: str) -> dict[str, Any]:
    document = yaml.safe_load((GITHUB / "ISSUE_TEMPLATE" / name).read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def fields(name: str) -> dict[str, dict[str, Any]]:
    """The fields of a form that the visitor fills in, by id."""
    return {f["id"]: f for f in load(name)["body"] if f["type"] != "markdown"}


# --- the issue forms ---------------------------------------------------------------------------


def test_the_forms_are_the_ones_we_expect() -> None:
    names = {path.name for path in FORMS}
    assert names >= {"bug-report.yml", "feature-request.yml", "wrong-broadcast.yml"}
    assert (GITHUB / "ISSUE_TEMPLATE" / "config.yml").is_file()


@pytest.mark.parametrize("path", FORMS, ids=lambda p: p.name)
def test_every_form_has_what_github_needs_and_uses_labels_that_exist(path: Path) -> None:
    document = load(path.name)
    for key in ("name", "description", "body"):
        assert document.get(key), f"{path.name}: missing {key}"
    assert set(document.get("labels", [])) <= LABELS, path.name
    ids = []
    for field in document["body"]:
        assert field["type"] in FIELD_TYPES, f"{path.name}: unknown type {field['type']}"
        if field["type"] == "markdown":
            continue
        assert field["attributes"].get("label"), f"{path.name}: a field has no label"
        assert re.fullmatch(r"[a-z0-9_-]+", field["id"]), field["id"]
        ids.append(field["id"])
        if field["type"] == "dropdown":
            assert len(field["attributes"]["options"]) >= 2
    assert len(ids) == len(set(ids)), f"{path.name}: two fields share an id"
    assert any(f.get("validations", {}).get("required") for f in fields(path.name).values())


def test_the_bug_form_asks_for_the_device_the_browser_and_the_steps() -> None:
    asked = fields("bug-report.yml")
    for needed in ("what-happened", "expected", "steps", "device", "browser", "screenshot"):
        assert needed in asked
    assert asked["device"]["validations"]["required"]
    assert asked["browser"]["validations"]["required"]
    text = (GITHUB / "ISSUE_TEMPLATE" / "bug-report.yml").read_text(encoding="utf-8")
    assert "personal data" in text  # the reminder


def test_the_feature_form_asks_for_the_problem_before_the_idea() -> None:
    ids = list(fields("feature-request.yml"))
    assert ids.index("problem") < ids.index("idea") < ids.index("alternatives")


def test_the_wrong_broadcast_form_keeps_the_fields_the_sites_link_fills_in() -> None:
    """The site's report link pre-fills these fields by id (site/js/report.js)."""
    report = (ROOT / "site" / "js" / "report.js").read_text(encoding="utf-8")
    assert "wrong-broadcast.yml" in report
    assert {"match", "shown"} <= set(fields("wrong-broadcast.yml"))


def test_the_chooser_links_to_private_security_reporting_and_to_the_privacy_notice() -> None:
    links = {link["name"]: link["url"] for link in load("config.yml")["contact_links"]}
    assert links["Security problem"].endswith("/security/advisories/new")
    assert links["Privacy"].endswith("/blob/main/PRIVACY.md")
    assert (ROOT / "PRIVACY.md").is_file()
    assert all(url.startswith("https://github.com/raissonls/ubi-ludus/") for url in links.values())


# --- the pull request template -----------------------------------------------------------------


TEMPLATE = (GITHUB / "pull_request_template.md").read_text(encoding="utf-8")


def test_the_pull_request_template_asks_what_why_evidence_and_the_way_back() -> None:
    for heading in ("What and why", "Type of change", "Evidence", "Risk and how to undo it"):
        assert f"## {heading}" in TEMPLATE, heading


def test_the_site_checklist_covers_the_states_devices_access_themes_privacy_and_size() -> None:
    checklist = TEMPLATE.split("## If the site changes")[1].split("\n## ")[0].lower()
    for word in (
        "loading",
        "empty",
        "error",
        "phone",
        "desktop",
        "keyboard",
        "screen reader",
        "dark",
        "light",
        "request",
        "content security policy",
        "size budgets",
    ):
        assert word in checklist, word


def test_the_template_links_to_files_that_exist() -> None:
    targets = re.findall(r"\]\((\.\./[^)#]+)", TEMPLATE)
    for target in targets:
        assert (GITHUB / target).resolve().exists(), target


# --- the code owners ---------------------------------------------------------------------------


def owner_lines() -> list[tuple[str, list[str]]]:
    lines = (GITHUB / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
    rules = [line.split() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    return [(parts[0], parts[1:]) for parts in rules]


def test_every_path_in_the_code_owners_exists_and_every_line_names_an_owner() -> None:
    lines = owner_lines()
    assert lines[0][0] == "*"  # the general line is first: the last matching line wins
    for pattern, owners in lines:
        assert owners
        assert all(owner.startswith("@") for owner in owners), pattern
        if pattern != "*":
            assert (ROOT / pattern.lstrip("/")).exists(), f"CODEOWNERS points at {pattern}"


def test_the_rights_data_and_the_workflows_have_a_named_owner() -> None:
    paths = {pattern for pattern, _ in owner_lines()}
    assert {"/data/", "/.github/workflows/", "/.github/CODEOWNERS"} <= paths


def test_contributing_mentions_the_template_the_code_owners_and_the_forms() -> None:
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for word in ("pull_request_template.md", "CODEOWNERS", "bug report", "feature request"):
        assert word in text, word
