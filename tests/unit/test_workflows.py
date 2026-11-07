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


# --- the daily pipeline (M4-03, FR-50) -----------------------------------------------------------

PIPELINE = WORKFLOWS / "pipeline.yml"
SITE = Path(__file__).resolve().parents[2] / "site"


def pipeline_jobs() -> dict[str, Any]:
    jobs: dict[str, Any] = load(PIPELINE)["jobs"]
    return jobs


def run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in job["steps"])


def test_the_pipeline_runs_every_day_at_0900_utc_and_can_be_started_by_hand() -> None:
    triggers = load(PIPELINE)[True]
    [schedule] = triggers["schedule"]
    assert schedule["cron"] == "0 9 * * *"  # 06:00 in Brazil
    assert "workflow_dispatch" in triggers
    assert triggers["workflow_dispatch"]["inputs"]["send_email"]["default"] is True


def test_the_steps_run_in_order_and_each_waits_for_the_one_before() -> None:
    jobs = pipeline_jobs()
    assert list(jobs) == ["build", "deploy", "email"]
    assert jobs["deploy"]["needs"] == "build"
    assert set(jobs["email"]["needs"]) == {"build", "deploy"}


def test_the_e_mail_can_be_left_out_of_a_manual_run_but_never_of_the_daily_one() -> None:
    condition = pipeline_jobs()["email"]["if"]
    assert condition == "github.event_name != 'workflow_dispatch' || inputs.send_email"


def test_a_provider_that_fails_stops_the_run_before_anything_is_deployed() -> None:
    build = pipeline_jobs()["build"]
    step = next(s for s in build["steps"] if "pipeline.publish" in str(s.get("run", "")))
    command = " ".join(str(step["run"]).split())
    assert "--run" in command and "--require-all-providers" in command
    assert '--previous-url "$PREVIOUS_URL"' in command
    # The address of the last published file comes from the repository, not typed in.
    expected = "https://${{ github.repository_owner }}.github.io/"
    expected += "${{ github.event.repository.name }}/data/matches.json"
    assert step["env"]["PREVIOUS_URL"] == expected
    # The default (a failing step stops the job) is not turned off, and the deploy needs the build.
    assert "continue-on-error" not in str(build)
    assert "continue-on-error" not in str(pipeline_jobs()["deploy"])


def test_the_site_is_deployed_with_the_pages_actions_and_data_is_never_committed() -> None:
    jobs = pipeline_jobs()
    uses = [s["uses"] for job in jobs.values() for s in job["steps"] if "uses" in s]
    assert any(u.startswith("actions/upload-pages-artifact@") for u in uses)
    assert any(u.startswith("actions/deploy-pages@") for u in uses)
    everything = "\n".join(run_text(job) for job in jobs.values())
    assert not re.search(r"git\s+(commit|push|add)", everything)
    assert jobs["deploy"]["permissions"] == {"pages": "write", "id-token": "write"}
    assert jobs["deploy"]["environment"]["name"] == "github-pages"


def test_each_secret_goes_to_one_step_and_nothing_else_gets_a_secret() -> None:
    def holders(job: dict[str, Any]) -> list[str]:
        return [s.get("name", "?") for s in job["steps"] if "secrets." in str(s.get("env", {}))]

    jobs = pipeline_jobs()
    assert holders(jobs["build"]) == ["Fetch, build with dbt, export and validate"]
    assert holders(jobs["email"]) == ["Send the e-mail"]
    assert holders(jobs["deploy"]) == []
    build_env = next(s for s in jobs["build"]["steps"] if "pipeline.publish" in str(s.get("run")))
    assert set(build_env["env"]) == {"FOOTBALL_DATA_TOKEN", "API_FOOTBALL_KEY", "PREVIOUS_URL"}
    mail = next(s for s in jobs["email"]["steps"] if "email.send" in str(s.get("run")))
    assert {"SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"} <= set(mail["env"])
    for job in jobs.values():
        assert "secrets." not in str(job.get("env", {}))


def test_the_e_mail_is_sent_from_the_data_that_was_deployed() -> None:
    jobs = pipeline_jobs()
    names = [s.get("with", {}).get("name") for s in jobs["build"]["steps"] if "with" in s]
    assert "site-data" in names  # uploaded by the build
    download = next(s for s in jobs["email"]["steps"] if "download-artifact" in str(s.get("uses")))
    assert download["with"] == {"name": "site-data", "path": "site/data"}
    assert "--data site/data" in run_text(jobs["email"])


def test_only_what_the_site_needs_is_deployed() -> None:
    """A new file at the top of site/ must be added to the deploy or be named here as left out."""
    step = next(s for s in pipeline_jobs()["build"]["steps"] if s.get("name") == "Gather the site")
    copied = {Path(p).name for p in re.findall(r"site/\S+", step["run"])}
    left_out = {"README.md", "package.json", "test"}  # docs, tooling and tests: not for visitors
    committed = {p.name for p in SITE.iterdir() if p.name != "data"}  # data/ is made by the run
    assert copied - {"data"} | left_out == committed
    assert "data" in copied
