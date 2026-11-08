"""The workflow that holds the site to its speed and weight targets (M5-02, NFR performance)."""

import re
from typing import Any

from test_workflows import PIPELINE, WORKFLOWS, load

LIGHTHOUSE = WORKFLOWS / "lighthouse.yml"
TEXT = LIGHTHOUSE.read_text(encoding="utf-8")


def jobs() -> dict[str, Any]:
    found: dict[str, Any] = load(LIGHTHOUSE)["jobs"]
    return found


def test_it_runs_on_main_after_each_deploy_and_by_hand() -> None:
    triggers = load(LIGHTHOUSE)[True]
    assert triggers["push"]["branches"] == ["main"]
    assert "site/**" in triggers["push"]["paths"]
    assert triggers["workflow_run"]["workflows"] == [load(PIPELINE)["name"]]  # the daily pipeline
    assert triggers["workflow_run"]["types"] == ["completed"]
    assert "workflow_dispatch" in triggers


def test_lighthouse_is_pinned_to_one_exact_version_and_never_the_latest() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", load(LIGHTHOUSE)["env"]["LIGHTHOUSE_VERSION"])
    calls = re.findall(r"npx --yes (\S+)", TEXT)
    assert calls and all(call == '"lighthouse@$LIGHTHOUSE_VERSION"' for call in calls)
    assert "lighthouse@latest" not in TEXT


def test_it_measures_three_times_and_a_miss_fails_the_run() -> None:
    for name, job in jobs().items():
        steps = "\n".join(str(step.get("run", "")) for step in job["steps"])
        assert "for run in 1 2 3" in steps, name
        checker = "ubi_ludus.quality.lighthouse check"
        assert f"{checker} lighthouse-1.json lighthouse-2.json lighthouse-3.json" in steps
        assert "set -o pipefail" in steps  # without it, tee would hide the checker's exit status


def test_it_can_read_the_repository_and_nothing_else_and_holds_no_secret() -> None:
    for job in jobs().values():
        assert job["permissions"] == {"contents": "read"}
    assert "secrets." not in TEXT


def test_the_deployed_site_is_only_measured_after_a_deploy_that_worked() -> None:
    assert "github.event.workflow_run.conclusion == 'success'" in jobs()["deployed"]["if"]
    assert jobs()["repository"]["if"] == "github.event_name != 'workflow_run'"


def test_the_repository_run_is_served_like_pages_and_stops_its_server() -> None:
    step = jobs()["repository"]["steps"][-1]["run"]
    assert "ubi_ludus.quality.lighthouse serve --site site --data lighthouse-data" in step
    assert "trap 'kill \"$server\"' EXIT" in step


def test_the_data_comes_from_what_is_published_with_the_test_data_as_the_fallback() -> None:
    step = jobs()["repository"]["steps"][1]["run"]
    assert '"$PAGES/data/$name.json"' in step and "tests/fixtures/site/data" in step
