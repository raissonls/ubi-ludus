"""The freshness check behind the watchdog workflow (FR-51, R6)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from ubi_ludus.pipeline import watchdog
from ubi_ludus.pipeline.providers.base import ProviderError
from ubi_ludus.pipeline.providers.http import HttpResponse
from ubi_ludus.pipeline.watchdog import Verdict, check

STATUS = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "site" / "data" / "status.json").read_text(
        encoding="utf-8"
    )
)
URL = "https://example.org/ubi-ludus/data/status.json"
NOW = datetime(2026, 11, 8, 11, 0, tzinfo=UTC)
LIMIT = timedelta(hours=5)


def serving(body: bytes | None = None, status: int = 200, **changes: Any) -> Any:
    document = {**STATUS, **changes}
    payload = json.dumps(document).encode() if body is None else body

    def get(url: str, headers: Mapping[str, str]) -> HttpResponse:
        assert url == URL and dict(headers) == {}
        return HttpResponse(status, {}, payload)

    return get


def hours_ago(hours: float) -> str:
    return (NOW - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_data_from_this_morning_is_fresh() -> None:
    verdict = check(URL, NOW, LIMIT, serving(last_success_at=hours_ago(2)))
    assert verdict.fresh and verdict.message.startswith(
        "Fresh: last successful run 2026-11-08 09:00"
    )


def test_data_from_yesterday_means_todays_run_did_not_happen() -> None:
    verdict = check(URL, NOW, LIMIT, serving(last_success_at=hours_ago(26)))
    assert not verdict.fresh
    assert "26.0 hours old" in verdict.message and "2026-11-07 09:00 UTC" in verdict.message


def test_the_limit_is_inclusive_at_the_edge() -> None:
    assert check(URL, NOW, LIMIT, serving(last_success_at=hours_ago(5))).fresh
    assert not check(URL, NOW, LIMIT, serving(last_success_at=hours_ago(5.1))).fresh


def test_a_site_that_cannot_be_reached_is_a_stale_verdict_not_a_crash() -> None:
    def down(url: str, headers: Mapping[str, str]) -> HttpResponse:
        raise ProviderError("Network error: timed out")

    verdict = check(URL, NOW, LIMIT, down)
    assert (
        not verdict.fresh
        and "Could not reach" in verdict.message
        and "timed out" in verdict.message
    )


def test_an_address_that_is_not_https_is_a_stale_verdict() -> None:
    verdict = check("http://example.org/status.json", NOW, LIMIT)  # the real fetcher refuses it
    assert not verdict.fresh and "Could not reach" in verdict.message


@pytest.mark.parametrize("status", [404, 500, 503])
def test_an_error_page_is_a_stale_verdict(status: int) -> None:
    verdict = check(URL, NOW, LIMIT, serving(b"", status))
    assert not verdict.fresh and f"HTTP {status}" in verdict.message


@pytest.mark.parametrize(
    "body",
    [b"<html>Not Found</html>", b"{}", b'{"schema_version": "1.0"}', b"[]"],
)
def test_a_file_that_is_not_a_status_file_is_a_stale_verdict(body: bytes) -> None:
    verdict = check(URL, NOW, LIMIT, serving(body))
    assert not verdict.fresh and "cannot be read" in verdict.message


def test_the_command_prints_the_verdict_and_exits_with_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[timedelta] = []

    def fake_check(url: str, now: datetime, limit: timedelta) -> Verdict:
        seen.append(limit)
        return Verdict(url.endswith("fresh.json"), f"verdict for {url}")

    monkeypatch.setattr(watchdog, "check", fake_check)
    assert watchdog.main(["--url", "https://x.org/fresh.json", "--max-age-hours", "3"]) == 0
    assert watchdog.main(["--url", "https://x.org/old.json"]) == 1
    output = capsys.readouterr().out
    assert "verdict for https://x.org/fresh.json" in output and "old.json" in output
    assert seen == [timedelta(hours=3), timedelta(hours=5)]  # the default is five hours


def test_the_default_limit_is_five_hours() -> None:
    assert watchdog.DEFAULT_MAX_AGE_HOURS == 5.0
