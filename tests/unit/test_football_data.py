import email.message
import io
import json
import logging
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from ubi_ludus.pipeline.config import load_competitions
from ubi_ludus.pipeline.fetch import fetch_all, plan_fetches
from ubi_ludus.pipeline.providers.base import FetchRequest, FetchTarget, ProviderError
from ubi_ludus.pipeline.providers.default import default_registry
from ubi_ludus.pipeline.providers.football_data import (
    TOKEN_ENV,
    USER_AGENT,
    FootballDataAdapter,
)
from ubi_ludus.pipeline.providers.http import HttpResponse, urllib_get
from ubi_ludus.pipeline.warehouse import connect, load_provider_responses
from ubi_ludus.pipeline.window import DateWindow

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "football_data"
TOKEN = "SECRET-TOKEN-1234567890"  # noqa: S105 - a fake value, used to prove it never leaks
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
WINDOW = DateWindow(date(2026, 11, 1), date(2026, 11, 16))


class FakeHttp:
    """Plays back canned replies and remembers every call."""

    def __init__(self, *replies: HttpResponse) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls.append((url, dict(headers)))
        return self.replies.pop(0)


class Sleeps:
    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def reply(
    status: int = 200,
    body: bytes | None = None,
    *,
    fixture: str = "matches.json",
    available: int | None = 9,
    reset: int | None = 40,
) -> HttpResponse:
    headers: dict[str, str] = {}
    if available is not None:
        headers["x-requests-available-minute"] = str(available)
    if reset is not None:
        headers["x-requestcounter-reset"] = str(reset)
    content = body if body is not None else (FIXTURES / fixture).read_bytes()
    return HttpResponse(status, headers, content)


def target(provider_id: str, competition_id: str | None = None) -> FetchTarget:
    return FetchTarget(competition_id or provider_id.lower(), provider_id, WINDOW)


def request(*targets: FetchTarget) -> FetchRequest:
    return FetchRequest("football-data", targets, date(2026, 11, 2))


def adapter(http: FakeHttp, sleeps: Sleeps | None = None) -> FootballDataAdapter:
    return FootballDataAdapter(TOKEN, http_get=http, sleep=sleeps or Sleeps(), now=lambda: NOW)


def test_it_asks_for_each_competition_with_its_date_window() -> None:
    http = FakeHttp(reply(), reply())
    adapter(http).fetch(request(target("BSA"), target("CLI")))
    assert [url for url, _ in http.calls] == [
        "https://api.football-data.org/v4/competitions/BSA/matches?dateFrom=2026-11-01&dateTo=2026-11-16",
        "https://api.football-data.org/v4/competitions/CLI/matches?dateFrom=2026-11-01&dateTo=2026-11-16",
    ]


def test_the_key_goes_in_a_header_and_the_user_agent_names_the_project() -> None:
    http = FakeHttp(reply())
    adapter(http).fetch(request(target("BSA")))
    [(url, headers)] = http.calls
    assert headers["X-Auth-Token"] == TOKEN
    assert TOKEN not in url
    assert headers["User-Agent"] == USER_AGENT
    assert "ubi-ludus" in USER_AGENT
    assert "github.com/raissonls/ubi-ludus" in USER_AGENT


@pytest.mark.parametrize("fixture", ["matches.json", "matches_teams_undecided.json"])
def test_responses_come_back_untouched_with_where_they_came_from(fixture: str) -> None:
    http = FakeHttp(reply(fixture=fixture))
    [raw] = adapter(http).fetch(request(target("BSA", "brasileirao-serie-a")))
    assert raw.payload == json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    assert raw.provider == "football-data"
    assert raw.resource == "competitions/BSA/matches"
    assert raw.params == {"dateFrom": "2026-11-01", "dateTo": "2026-11-16"}
    assert raw.competition_id == "brasileirao-serie-a"
    assert raw.fetched_at == NOW


def test_the_key_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, "  from-the-environment  ")
    http = FakeHttp(reply())
    FootballDataAdapter(http_get=http, sleep=Sleeps()).fetch(request(target("BSA")))
    assert http.calls[0][1]["X-Auth-Token"] == "from-the-environment"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_key_is_a_clear_error(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv(TOKEN_ENV, raising=False)
    else:
        monkeypatch.setenv(TOKEN_ENV, value)
    with pytest.raises(ProviderError, match=f"{TOKEN_ENV} is not set"):
        FootballDataAdapter()


def test_the_key_never_appears_in_logs_errors_or_the_object_description(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    messages: list[str] = []
    for replies in (
        [reply(403), reply()],  # a skipped competition is logged
        [reply(429), reply(429)],  # rate limit twice: warning, then error
        [reply(401)],
        [reply(500)],
        [reply(body=b"not json")],
    ):
        engine = adapter(FakeHttp(*replies))
        messages.append(repr(engine))
        try:
            engine.fetch(request(target("BSA"), target("CLI")))
        except ProviderError as exc:
            messages.append(str(exc))
    everything = "\n".join(messages + [record.getMessage() for record in caplog.records])
    assert "football-data.org" in everything  # the scenarios really did log and raise
    assert TOKEN not in everything
    assert "token=<hidden>" in repr(adapter(FakeHttp()))


def test_a_competition_the_plan_does_not_cover_is_skipped_not_fatal() -> None:
    engine = adapter(FakeHttp(reply(403), reply(404), reply()))
    responses = engine.fetch(request(target("CSA"), target("BSB"), target("BSA")))
    assert [r.competition_id for r in responses] == ["bsa"]
    assert [competition for competition, _ in engine.skipped] == ["csa", "bsb"]
    assert "HTTP 403" in engine.skipped[0][1]


def test_the_skipped_list_starts_fresh_on_every_run() -> None:
    engine = adapter(FakeHttp(reply(403), reply(), reply()))
    engine.fetch(request(target("CSA"), target("BSA")))
    assert engine.skipped
    engine.fetch(request(target("BSA")))
    assert engine.skipped == []


def test_if_nothing_could_be_fetched_the_provider_counts_as_failed() -> None:
    engine = adapter(FakeHttp(reply(403), reply(404)))
    with pytest.raises(ProviderError, match="served none of the competitions: csa .*bsb"):
        engine.fetch(request(target("CSA"), target("BSB")))


def test_a_rejected_key_fails_the_provider() -> None:
    with pytest.raises(ProviderError, match="rejected the API token"):
        adapter(FakeHttp(reply(401))).fetch(request(target("BSA")))


@pytest.mark.parametrize("status", [500, 502, 400])
def test_other_http_errors_fail_the_provider(status: int) -> None:
    with pytest.raises(ProviderError, match=f"HTTP {status}"):
        adapter(FakeHttp(reply(status))).fetch(request(target("BSA")))


def test_a_body_that_is_not_json_fails_the_provider() -> None:
    with pytest.raises(ProviderError, match="not JSON"):
        adapter(FakeHttp(reply(body=b"<html>oops</html>"))).fetch(request(target("BSA")))


def test_it_does_not_wait_while_the_minute_allowance_lasts() -> None:
    sleeps = Sleeps()
    adapter(FakeHttp(reply(available=5), reply(available=4)), sleeps).fetch(
        request(target("BSA"), target("CLI"))
    )
    assert sleeps.seconds == []


def test_it_waits_for_the_next_minute_when_the_allowance_is_used_up() -> None:
    sleeps = Sleeps()
    adapter(FakeHttp(reply(available=0, reset=42), reply(available=9)), sleeps).fetch(
        request(target("BSA"), target("CLI"))
    )
    assert sleeps.seconds == [43]


def test_after_too_many_requests_it_waits_then_tries_once_more() -> None:
    sleeps = Sleeps()
    http = FakeHttp(reply(429, reset=20), reply())
    [raw] = adapter(http, sleeps).fetch(request(target("BSA")))
    assert sleeps.seconds == [21]
    assert len(http.calls) == 2
    assert raw.payload


def test_two_rate_limit_answers_in_a_row_fail_the_provider() -> None:
    with pytest.raises(ProviderError, match="twice in a row"):
        adapter(FakeHttp(reply(429), reply(429))).fetch(request(target("BSA")))


def test_without_rate_limit_headers_it_waits_a_full_minute_after_a_429() -> None:
    sleeps = Sleeps()
    adapter(FakeHttp(reply(429, available=None, reset=None), reply()), sleeps).fetch(
        request(target("BSA"))
    )
    assert sleeps.seconds == [61]


def test_garbled_rate_limit_headers_are_ignored() -> None:
    sleeps = Sleeps()
    garbled = HttpResponse(
        200, {"x-requests-available-minute": "lots"}, (FIXTURES / "matches.json").read_bytes()
    )
    adapter(FakeHttp(garbled, reply()), sleeps).fetch(request(target("BSA"), target("CLI")))
    assert sleeps.seconds == []


def test_a_run_with_no_targets_fetches_nothing_and_is_not_an_error() -> None:
    http = FakeHttp()
    assert adapter(http).fetch(request()) == []
    assert http.calls == []


def test_the_default_registry_builds_this_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    registry = default_registry()
    assert registry.names() == ["football-data"]
    assert isinstance(registry.create("football-data"), FootballDataAdapter)


def test_a_missing_key_shows_up_as_a_failed_provider_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    plan = plan_fetches(load_competitions(), date(2026, 11, 2))
    football_data_only = [r for r in plan if r.provider == "football-data"]
    [outcome] = fetch_all(football_data_only, default_registry())
    assert outcome.responses == ()
    assert outcome.error == f"{TOKEN_ENV} is not set"


def test_the_real_config_asks_football_data_for_nine_competitions() -> None:
    plan = plan_fetches(load_competitions(), date(2026, 11, 2))
    [football_data] = [r for r in plan if r.provider == "football-data"]
    assert {t.provider_id for t in football_data.targets} == {
        "BSA", "CLI", "CL", "PL", "PD", "SA", "BL1", "FL1", "WC",
    }  # fmt: skip
    assert all(
        t.window == DateWindow(date(2026, 11, 1), date(2026, 11, 16)) for t in football_data.targets
    )


def test_what_the_adapter_returns_can_be_loaded_into_the_warehouse(tmp_path: Path) -> None:
    http = FakeHttp(reply(), reply(fixture="matches_teams_undecided.json"))
    responses = adapter(http).fetch(
        request(target("BSA", "serie-a"), target("CLI", "libertadores"))
    )
    con = connect(tmp_path / "w.duckdb")
    assert load_provider_responses(con, responses) == 2
    rows = con.execute(
        "select competition_id, payload from raw_provider_responses order by competition_id"
    ).fetchall()
    assert [row[0] for row in rows] == ["libertadores", "serie-a"]
    assert json.loads(rows[1][1])["matches"][0]["id"] == 900001
    assert json.loads(rows[0][1])["matches"][0]["homeTeam"]["name"] is None


# --- the real HTTP helper, with the network replaced -------------------------------------------


def test_the_http_helper_refuses_plain_http() -> None:
    with pytest.raises(ValueError, match="https"):
        urllib_get("http://example.org/", {})


def test_the_http_helper_returns_error_statuses_as_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = email.message.Message()
    headers["X-RequestCounter-Reset"] = "17"

    def fake_urlopen(*_args: Any, **_kwargs: Any) -> None:
        raise urllib.error.HTTPError(
            "https://example.org/", 429, "Too Many", headers, io.BytesIO(b"{}")
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    response = urllib_get("https://example.org/", {})
    assert response.status == 429
    assert response.headers["x-requestcounter-reset"] == "17"
    assert response.body == b"{}"


def test_the_http_helper_turns_network_failures_into_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(*_args: Any, **_kwargs: Any) -> None:
        raise urllib.error.URLError("no route to host")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ProviderError, match="Network error"):
        urllib_get("https://example.org/", {})


def test_the_http_helper_reads_a_successful_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status = 200
        headers = email.message.Message()

        def __init__(self) -> None:
            self.headers["X-Requests-Available-Minute"] = "9"

        def read(self) -> bytes:
            return b'{"ok": true}'

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: FakeResponse())
    response = urllib_get("https://example.org/", {"X-Test": "1"})
    assert (response.status, response.body) == (200, b'{"ok": true}')
    assert response.headers["x-requests-available-minute"] == "9"
