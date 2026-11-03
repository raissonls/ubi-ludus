"""The GitHub Actions workflows keep the security baseline (PRD NFR, security checklist)."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
FILES = sorted(WORKFLOWS.glob("*.yml"))
SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def load(path: Path) -> dict[Any, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def steps_of(workflow: dict[Any, Any]) -> list[dict[str, Any]]:
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def test_there_are_workflows_to_check() -> None:
    assert {f.name for f in FILES} >= {"ci.yml", "review-report.yml"}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_full_commit(path: Path) -> None:
    used = [step["uses"] for step in steps_of(load(path)) if "uses" in step]
    assert used
    assert all(SHA.match(action) for action in used), used


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_nothing_is_allowed_by_default_and_each_job_asks_for_what_it_needs(path: Path) -> None:
    workflow = load(path)
    assert workflow["permissions"] == {}
    for job in workflow["jobs"].values():
        assert job["permissions"]  # a job without its own list would get the default


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_workflow_runs_untrusted_code_with_secrets(path: Path) -> None:
    triggers = load(path)[True]  # YAML reads the key `on` as the boolean True
    assert "pull_request_target" not in triggers


def test_the_review_runs_every_thursday_and_can_be_started_by_hand() -> None:
    triggers = load(WORKFLOWS / "review-report.yml")[True]
    [schedule] = triggers["schedule"]
    minute, hour, day_of_month, month, weekday = schedule["cron"].split()
    assert (day_of_month, month, weekday) == ("*", "*", "4")  # Thursday
    assert 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59
    assert "workflow_dispatch" in triggers


def test_the_review_can_only_write_issues_and_gives_its_keys_to_one_step() -> None:
    workflow = load(WORKFLOWS / "review-report.yml")
    [job] = workflow["jobs"].values()
    assert job["permissions"] == {"contents": "read", "issues": "write"}

    # A secret's value goes to one step. The check before it only asks whether one exists.
    def uses_a_value(step: dict[str, Any]) -> bool:
        env = step.get("env", {})
        return any("secrets." in str(v) and "!= ''" not in str(v) for v in env.values())

    assert [s["name"] for s in job["steps"] if uses_a_value(s)] == ["Build the report"]
    assert "secrets." not in str(job.get("env", {}))


def test_the_review_stops_quietly_while_the_teams_file_or_a_key_is_missing() -> None:
    steps = load(WORKFLOWS / "review-report.yml")["jobs"]["report"]["steps"]
    gate = next(s for s in steps if s.get("id") == "ready")
    assert "data/teams.yml" in gate["run"]
    assert "FOOTBALL_DATA_TOKEN" in gate["run"]
    assert "API_FOOTBALL_KEY" in gate["run"]
    later = [s for s in steps if "if" in s]
    assert later
    assert all(s["if"] == "steps.ready.outputs.ready == 'true'" for s in later)
