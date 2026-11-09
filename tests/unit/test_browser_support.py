"""The browser support policy (docs/browser-support.md) matches what the site uses and what runs.

The policy promises a version of each browser. The site uses features that each need some version.
These tests keep the two honest: a new feature without a row in the policy fails, a feature that
needs a newer browser than the promise fails, and the weekly runs the policy lists must exist.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICY = (ROOT / "docs" / "browser-support.md").read_text(encoding="utf-8")
SITE = ROOT / "site"
MATRIX = ROOT / ".github" / "workflows" / "browser-matrix.yml"

# How each feature of the second table shows up in the site's files. A pattern is searched in the
# files of the kind named first ("js", "css" or "html").
DETECTORS: dict[str, tuple[str, str]] = {
    "`dialog.showModal()` and `::backdrop`": ("js", r"\.showModal\("),
    "The `inert` attribute": ("js", r"\binert\b"),
    "`dvh` units": ("css", r"\d\s*dvh\b"),
    "`:has()`": ("css", r":has\("),
    "`color-mix()`": ("css", r"color-mix\("),
    "`:focus-visible`": ("css", r":focus-visible"),
    "`Intl.ListFormat`": ("js", r"Intl\.ListFormat"),
    "`Intl.PluralRules`": ("js", r"Intl\.PluralRules"),
    "`replaceChildren()`": ("js", r"\.replaceChildren\("),
    "`overscroll-behavior`": ("css", r"overscroll-behavior"),
    "Scroll snapping": ("css", r"scroll-snap-type"),
    "`clipboard.writeText()`": ("js", r"clipboard\.writeText\("),
}

# Features that would need a row of their own. They are listed so that using one by accident fails
# here and the row is written on purpose, with the version the policy has to promise.
NOT_YET_ALLOWED: dict[str, tuple[str, str]] = {
    "container queries": ("css", r"@container\b"),
    "cascade layers": ("css", r"@layer\b"),
    "`light-dark()`": ("css", r"light-dark\("),
    "OKLCH and Lab colours": ("css", r"\b(?:oklch|oklab|lab)\("),
    "the popover attribute": ("html", r"\bpopover\b"),
    "view transitions": ("css", r"view-transition|startViewTransition"),
    "`text-wrap`": ("css", r"text-wrap"),
    "`@starting-style`": ("css", r"@starting-style"),
    "`Array.prototype.toSorted()` and `Object.groupBy()`": ("js", r"\.toSorted\(|Object\.groupBy"),
    "`structuredClone()`": ("js", r"structuredClone\("),
    "`AbortSignal.timeout()`": ("js", r"AbortSignal\.timeout"),
}


def section(heading: str) -> str:
    start = POLICY.index(f"## {heading}")
    following = POLICY.find("\n## ", start + 1)
    return POLICY[start : following if following != -1 else len(POLICY)]


def rows(text: str) -> list[list[str]]:
    """The cells of each row of the first table in `text`, without the header and the rule."""
    table = [line for line in text.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in table[2:]]


def version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def files(kind: str) -> list[Path]:
    pattern = {"js": "js/*.js", "css": "css/*.css", "html": "*.html"}[kind]
    found = sorted(SITE.glob(pattern))
    assert found, kind
    return found


def used(kind: str, pattern: str) -> bool:
    return any(re.search(pattern, path.read_text(encoding="utf-8")) for path in files(kind))


def supported() -> dict[str, str]:
    """The promised version by engine: Chrome, Safari or Firefox."""
    engine = {"Chrome": "Chrome", "Edge": "Chrome", "Safari": "Safari", "Firefox": "Firefox"}
    promised: dict[str, str] = {}
    for browser, from_version, _why in rows(section("What we support")):
        key = next(name for word, name in engine.items() if word in browser)
        # Several rows can share an engine (Safari on iOS and macOS): the newer one wins.
        if key not in promised or version(from_version) > version(promised[key]):
            promised[key] = from_version
    return promised


def features() -> dict[str, tuple[str, str, str]]:
    table = rows(section("What the site uses"))
    return {name: (chrome, safari, firefox) for name, chrome, safari, firefox, _used in table}


def test_the_policy_promises_chrome_safari_and_firefox_a_version_each() -> None:
    promised = supported()
    assert set(promised) == {"Chrome", "Safari", "Firefox"}
    assert all(re.fullmatch(r"\d+(\.\d+)?", value) for value in promised.values())


def test_every_feature_the_site_uses_has_a_row_and_every_row_is_still_used() -> None:
    listed = set(features())
    assert listed == set(DETECTORS), (
        "a feature in the policy has no detector in this test (or the other way round)"
    )
    for name, (kind, pattern) in DETECTORS.items():
        assert used(kind, pattern), f"{name} is in the policy but the site no longer uses it"


@pytest.mark.parametrize("name", sorted(NOT_YET_ALLOWED))
def test_a_feature_without_a_row_is_not_used_by_accident(name: str) -> None:
    kind, pattern = NOT_YET_ALLOWED[name]
    assert not used(kind, pattern), (
        f"The site uses {name}. Add it to 'What the site uses' in docs/browser-support.md with "
        "the versions that have it, move it to DETECTORS, and check the promise still holds."
    )


def test_no_feature_needs_a_newer_browser_than_the_policy_promises() -> None:
    promised = supported()
    too_new = []
    for name, (chrome, safari, firefox) in features().items():
        for engine, needs in (("Chrome", chrome), ("Safari", safari), ("Firefox", firefox)):
            if version(needs) > version(promised[engine]):
                too_new.append(f"{name}: needs {engine} {needs}, promised {promised[engine]}")
    assert too_new == []


def test_the_promise_is_not_older_than_it_has_to_be_in_a_way_nobody_noticed() -> None:
    """The floor is the highest version any feature needs; promising far more hides the reason."""
    promised = supported()
    for index, engine in enumerate(("Chrome", "Safari", "Firefox")):
        needed = max(version(row[index]) for row in features().values())
        # A round number above the need is fine (Safari 16.4 over 16.2), a gap of a whole
        # major version or more is not: the table would say "needs 16.2" and promise 18.
        assert version(promised[engine])[0] - needed[0] <= 1, engine


def test_every_run_the_policy_lists_exists_in_the_weekly_workflow() -> None:
    listed = [row[0].strip("`") for row in rows(section("What is tested"))]
    assert listed[0] == "chromium"  # the pull-request run, in ci.yml
    matrix = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))["jobs"]["browsers"]["strategy"]
    weekly = [entry["name"] for entry in matrix["matrix"]["include"]]
    assert weekly == listed[1:]


def test_the_policy_is_linked_from_the_site_readme_and_the_usability_kit() -> None:
    for path in (SITE / "README.md", ROOT / "docs" / "usability" / "README.md"):
        assert "browser-support.md" in path.read_text(encoding="utf-8"), path.name


# --- the weekly workflow ----------------------------------------------------------------------


def workflow() -> dict[object, object]:
    document = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_it_runs_on_monday_and_by_hand_and_never_on_a_pull_request() -> None:
    triggers = workflow()[True]  # YAML reads the key `on` as the boolean True
    assert isinstance(triggers, dict)
    [schedule] = triggers["schedule"]
    assert schedule["cron"].split()[2:] == ["*", "*", "1"]  # Monday
    assert "workflow_dispatch" in triggers
    assert "pull_request" not in triggers and "push" not in triggers  # not a required check


def test_each_run_sets_its_engine_and_profile_and_a_missing_browser_fails() -> None:
    jobs = workflow()["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["browsers"]
    assert job["env"]["UBI_LUDUS_ENGINE"] == "${{ matrix.engine }}"
    assert job["env"]["UBI_LUDUS_PROFILE"] == "${{ matrix.profile }}"
    assert job["env"]["UBI_LUDUS_REQUIRE_BROWSER"] == "1"
    assert job["strategy"]["fail-fast"] is False
    profiles = {entry["profile"] for entry in job["strategy"]["matrix"]["include"]}
    assert profiles == {"iphone", "android"}


def test_only_the_scheduled_run_opens_issues_and_it_is_the_only_job_that_can() -> None:
    jobs = workflow()["jobs"]
    assert isinstance(jobs, dict)
    assert jobs["browsers"]["permissions"] == {"contents": "read"}
    owner = jobs["tell-the-owner"]
    assert owner["permissions"] == {"issues": "write"}
    assert "github.event_name == 'schedule'" in owner["if"]


# --- the layout sweep --------------------------------------------------------------------------

SWEEP = ROOT / ".github" / "workflows" / "layout-sweep.yml"


def test_the_layout_sweep_is_started_by_hand_and_keeps_its_pictures_for_a_week() -> None:
    document = yaml.safe_load(SWEEP.read_text(encoding="utf-8"))
    assert list(document[True]) == ["workflow_dispatch"]  # by hand only
    job = document["jobs"]["sweep"]
    assert job["env"]["UBI_LUDUS_SCREENSHOTS"] == "sweep-pictures"
    upload = next(step for step in job["steps"] if "upload-artifact" in step.get("uses", ""))
    assert upload["with"]["retention-days"] == 7
    assert upload["with"]["path"] == "sweep-pictures"
    assert job["permissions"] == {"contents": "read"}


def test_the_sweep_covers_the_widths_and_states_the_issue_asks_for() -> None:
    text = (ROOT / "tests" / "browser" / "test_layout_sweep.py").read_text(encoding="utf-8")
    widths = re.search(r"WIDTHS = \(([^)]*)\)", text)
    assert widths is not None
    assert {int(w) for w in widths.group(1).split(",") if w.strip()} >= {
        320,
        360,
        390,
        430,
        768,
        1024,
        1440,
    }
    for state in ("empty", "with-teams", "settings-open", "match-sheet-open", "first-run"):
        assert f'"{state}"' in text, state
