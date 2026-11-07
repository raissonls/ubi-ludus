import json
import logging
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from dbt_helpers import LEGACY_COMPETITIONS

from ubi_ludus.pipeline.config import load_competitions
from ubi_ludus.pipeline.fetch import fetch_all, plan_fetches
from ubi_ludus.pipeline.providers.api_football import (
    KEY_ENV,
    USER_AGENT,
    ApiFootballAdapter,
)
from ubi_ludus.pipeline.providers.base import FetchRequest, FetchTarget, ProviderError
from ubi_ludus.pipeline.providers.default import default_registry
from ubi_ludus.pipeline.providers.http import HttpResponse
from ubi_ludus.pipeline.warehouse import connect, load_provider_responses
from ubi_ludus.pipeline.window import DateWindow, window_for

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "api_football"
KEY = "fake-key-fake-key"  # a fake value, used to prove it never leaks
NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
TODAY = date(2026, 11, 2)
WINDOW = window_for(TODAY, 1)  # 1 Nov through 3 Nov


class FakeHttp:
    """Plays back canned replies and remembers every call."""

    def __init__(self, *replies: HttpResponse) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls.append((url, dict(headers)))
        return self.replies.pop(0)

    @property
    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]


class Sleeps:
    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def reply(
    status: int = 200,
    body: bytes | None = None,
    *,
    fixture: str = "fixtures_day.json",
    minute_left: int | None = 9,
    day_left: int | None = 90,
) -> HttpResponse:
    headers: dict[str, str] = {}
    if minute_left is not None:
        headers["x-ratelimit-remaining"] = str(minute_left)
    if day_left is not None:
        headers["x-ratelimit-requests-remaining"] = str(day_left)
    content = body if body is not None else (FIXTURES / fixture).read_bytes()
    return HttpResponse(status, headers, content)


def status_reply(current: int = 5, limit: int = 100) -> HttpResponse:
    body = {"errors": [], "response": {"requests": {"current": current, "limit_day": limit}}}
    return reply(body=json.dumps(body).encode())


def error_reply(**errors: str) -> HttpResponse:
    return reply(body=json.dumps({"errors": errors, "results": 0, "response": []}).encode())


def target(league_id: str, competition_id: str, window: DateWindow = WINDOW) -> FetchTarget:
    return FetchTarget(competition_id, league_id, window)


def request(*targets: FetchTarget) -> FetchRequest:
    return FetchRequest("api-football", targets or (target("73", "copa-do-brasil"),), TODAY)


def adapter(http: FakeHttp, sleeps: Sleeps | None = None) -> ApiFootballAdapter:
    return ApiFootballAdapter(KEY, http_get=http, sleep=sleeps or Sleeps(), now=lambda: NOW)


def days_asked(http: FakeHttp) -> list[str]:
    return [url.split("date=")[1].split("&")[0] for url in http.urls if "fixtures" in url]


def day_replies(count: int = 3) -> list[HttpResponse]:
    return [reply() for _ in range(count)]


def test_it_reads_the_quota_then_asks_for_each_day_in_brazils_calendar() -> None:
    http = FakeHttp(status_reply(), *day_replies())
    adapter(http).fetch(request())
    assert http.urls == [
        "https://v3.football.api-sports.io/status",
        "https://v3.football.api-sports.io/fixtures?date=2026-11-02&timezone=America%2FSao_Paulo",
        "https://v3.football.api-sports.io/fixtures?date=2026-11-03&timezone=America%2FSao_Paulo",
        "https://v3.football.api-sports.io/fixtures?date=2026-11-01&timezone=America%2FSao_Paulo",
    ]


def test_the_key_goes_in_a_header_and_the_user_agent_names_the_project() -> None:
    http = FakeHttp(status_reply(), *day_replies())
    adapter(http).fetch(request())
    for url, headers in http.calls:
        assert headers["x-apisports-key"] == KEY
        assert KEY not in url
        assert headers["User-Agent"] == USER_AGENT
    assert "github.com/raissonls/ubi-ludus" in USER_AGENT


def test_it_keeps_only_the_leagues_we_follow_and_the_rest_comes_back_untouched() -> None:
    http = FakeHttp(status_reply(), *day_replies())
    responses = adapter(http).fetch(
        request(target("73", "copa-do-brasil"), target("11", "copa-sul-americana"))
    )

    assert len(responses) == 3
    original = json.loads((FIXTURES / "fixtures_day.json").read_text(encoding="utf-8"))
    raw = responses[0]
    payload: dict[str, Any] = raw.payload  # type: ignore[assignment]
    assert [f["league"]["id"] for f in payload["response"]] == [73, 11]  # league 999 is dropped
    assert payload["response"] == original["response"][:2]
    assert payload["results"] == 2
    assert {k: v for k, v in payload.items() if k not in ("response", "results")} == {
        k: v for k, v in original.items() if k not in ("response", "results")
    }
    assert (raw.provider, raw.resource, raw.competition_id) == ("api-football", "fixtures", None)
    assert raw.params == {"date": "2026-11-02", "timezone": "America/Sao_Paulo"}
    assert raw.fetched_at == NOW


def test_a_league_nobody_follows_gives_an_empty_list_not_an_error() -> None:
    http = FakeHttp(status_reply(), reply())
    [raw] = adapter(http).fetch(
        FetchRequest("api-football", (target("5", "x", DateWindow(TODAY, TODAY)),), TODAY)
    )
    assert raw.payload["response"] == []  # type: ignore[index]


def test_the_key_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KEY_ENV, "  from-the-environment  ")
    http = FakeHttp(status_reply(), *day_replies())
    ApiFootballAdapter(http_get=http, sleep=Sleeps()).fetch(request())
    assert http.calls[0][1]["x-apisports-key"] == "from-the-environment"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_key_is_a_clear_error(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is None:
        monkeypatch.delenv(KEY_ENV, raising=False)
    else:
        monkeypatch.setenv(KEY_ENV, value)
    with pytest.raises(ProviderError, match=f"{KEY_ENV} is not set"):
        ApiFootballAdapter()


def test_the_key_never_appears_in_logs_errors_or_the_object_description(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    messages: list[str] = []
    for replies in (
        [status_reply(), error_reply(plan="no access"), reply(), reply()],  # a skipped day
        [status_reply(), reply(429), reply(429)],  # rate limit twice: warning, then error
        [error_reply(token="Error/Missing application key.")],  # noqa: S106 - the provider's name
        [status_reply(), reply(500)],
        [status_reply(), reply(body=b"not json")],
        [reply(500), reply(), reply(), reply()],  # unreadable quota
    ):
        engine = adapter(FakeHttp(*replies))
        messages.append(repr(engine))
        try:
            engine.fetch(request())
        except ProviderError as exc:
            messages.append(str(exc))
    everything = "\n".join(messages + [record.getMessage() for record in caplog.records])
    # The scenarios really did log and raise, so the check below is not vacuous.
    assert "rejected the API key" in everything
    assert "rate limit" in everything
    assert "skipped" in everything
    assert "quota unknown" in everything
    assert KEY not in everything
    assert "key=<hidden>" in repr(adapter(FakeHttp()))


# --- the daily quota ----------------------------------------------------------------------------


def test_with_less_quota_than_days_it_drops_yesterday_first() -> None:
    http = FakeHttp(status_reply(current=98), reply(), reply())
    engine = adapter(http)
    responses = engine.fetch(request())
    assert days_asked(http) == ["2026-11-02", "2026-11-03"]
    assert len(responses) == 2
    assert engine.skipped == [("2026-11-01", "not enough of the daily quota left")]


def test_with_no_quota_left_it_fails_before_asking_for_any_fixtures() -> None:
    http = FakeHttp(status_reply(current=100))
    with pytest.raises(ProviderError, match="daily quota is used up"):
        adapter(http).fetch(request())
    assert len(http.calls) == 1


def test_the_quota_of_exactly_three_is_enough() -> None:
    http = FakeHttp(status_reply(current=97), *day_replies())
    assert len(adapter(http).fetch(request())) == 3


@pytest.mark.parametrize(
    "status",
    [
        reply(500),
        reply(body=b"not json"),
        reply(body=b'{"errors": [], "response": []}'),
        reply(body=b'{"errors": [], "response": {"requests": {"current": "many"}}}'),
        error_reply(bug="something broke"),
    ],
)
def test_if_the_quota_cannot_be_read_it_goes_on_and_trusts_the_response_headers(
    status: HttpResponse, caplog: pytest.LogCaptureFixture
) -> None:
    http = FakeHttp(status, *day_replies())
    assert len(adapter(http).fetch(request())) == 3
    assert "quota unknown" in caplog.text


def test_when_a_response_says_the_quota_is_used_up_the_remaining_days_are_not_asked() -> None:
    http = FakeHttp(status_reply(), reply(day_left=0))
    engine = adapter(http)
    responses = engine.fetch(request())
    assert len(responses) == 1
    assert days_asked(http) == ["2026-11-02"]
    assert [day for day, _ in engine.skipped] == ["2026-11-03", "2026-11-01"]


def test_a_quota_error_keeps_what_was_already_fetched() -> None:
    http = FakeHttp(
        status_reply(), reply(), error_reply(requests="You have reached the request limit")
    )
    engine = adapter(http)
    responses = engine.fetch(request())
    assert len(responses) == 1
    assert days_asked(http) == ["2026-11-02", "2026-11-03"]
    assert [day for day, _ in engine.skipped] == ["2026-11-03", "2026-11-01"]
    assert "daily quota reached" in engine.skipped[0][1]


# --- what the free plan refuses -----------------------------------------------------------------


def test_a_day_the_plan_refuses_is_skipped_not_fatal() -> None:
    plan = (FIXTURES / "plan_error.json").read_bytes()
    http = FakeHttp(status_reply(), reply(), reply(body=plan), reply())
    engine = adapter(http)
    responses = engine.fetch(request())
    assert [r.params["date"] for r in responses] == ["2026-11-02", "2026-11-01"]
    [(day, why)] = engine.skipped
    assert day == "2026-11-03"
    assert "Free plans do not have access to this date" in why


def test_the_skipped_list_starts_fresh_on_every_run() -> None:
    plan = (FIXTURES / "plan_error.json").read_bytes()
    http = FakeHttp(
        status_reply(), reply(), reply(body=plan), reply(), status_reply(), *day_replies()
    )
    engine = adapter(http)
    engine.fetch(request())
    assert engine.skipped
    engine.fetch(request())
    assert engine.skipped == []


def test_if_no_day_could_be_served_the_provider_counts_as_failed() -> None:
    plan = (FIXTURES / "plan_error.json").read_bytes()
    http = FakeHttp(status_reply(), *[reply(body=plan) for _ in range(3)])
    with pytest.raises(ProviderError, match=r"served none of the days: 2026-11-02 .*2026-11-01"):
        adapter(http).fetch(request())


def test_errors_given_as_a_list_are_read_too() -> None:
    body = json.dumps({"errors": ["Something odd"], "response": []}).encode()
    http = FakeHttp(status_reply(), *[reply(body=body) for _ in range(3)])
    with pytest.raises(ProviderError, match="Something odd"):
        adapter(http).fetch(request())


def test_a_horizon_longer_than_the_plan_allows_is_trimmed_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    long_window = window_for(TODAY, 14)
    http = FakeHttp(status_reply(), *day_replies())
    adapter(http).fetch(request(target("73", "copa-do-brasil", long_window)))
    assert days_asked(http) == ["2026-11-02", "2026-11-03", "2026-11-01"]
    assert "ignoring the longer horizon of copa-do-brasil" in caplog.text


def test_only_the_days_some_competition_needs_are_asked() -> None:
    http = FakeHttp(status_reply(), reply())
    adapter(http).fetch(request(target("73", "copa-do-brasil", DateWindow(TODAY, TODAY))))
    assert days_asked(http) == ["2026-11-02"]


def test_a_run_with_no_targets_fetches_nothing_and_is_not_an_error() -> None:
    http = FakeHttp()
    assert adapter(http).fetch(FetchRequest("api-football", (), TODAY)) == []
    assert http.calls == []


# --- keys, rate limits and odd answers -----------------------------------------------------------


def test_a_rejected_key_fails_the_provider_before_any_fixture_is_asked() -> None:
    http = FakeHttp(error_reply(token="Error/Missing application key."))  # noqa: S106
    with pytest.raises(ProviderError, match="rejected the API key"):
        adapter(http).fetch(request())
    assert len(http.calls) == 1


@pytest.mark.parametrize("status", [401, 403])
def test_an_http_auth_error_is_a_rejected_key_too(status: int) -> None:
    with pytest.raises(ProviderError, match="rejected the API key"):
        adapter(FakeHttp(reply(status, body=b"{}"))).fetch(request())


@pytest.mark.parametrize("status", [500, 502, 400])
def test_other_http_errors_on_fixtures_fail_the_provider(status: int) -> None:
    with pytest.raises(ProviderError, match=f"HTTP {status}"):
        adapter(FakeHttp(status_reply(), reply(status, body=b"{}"))).fetch(request())


def test_a_body_that_is_not_json_fails_the_provider() -> None:
    with pytest.raises(ProviderError, match="not JSON"):
        adapter(FakeHttp(status_reply(), reply(body=b"<html>oops</html>"))).fetch(request())


def test_a_json_document_that_is_not_an_object_fails_the_provider() -> None:
    with pytest.raises(ProviderError, match="unexpected document"):
        adapter(FakeHttp(status_reply(), reply(body=b"[1, 2]"))).fetch(request())


def test_an_answer_without_a_fixture_list_fails_the_provider() -> None:
    body = json.dumps({"errors": [], "response": {"oops": 1}}).encode()
    with pytest.raises(ProviderError, match="no fixture list for 2026-11-02"):
        adapter(FakeHttp(status_reply(), reply(body=body))).fetch(request())


def test_it_does_not_wait_while_the_minute_allowance_lasts() -> None:
    sleeps = Sleeps()
    adapter(FakeHttp(status_reply(), *day_replies()), sleeps).fetch(request())
    assert sleeps.seconds == []


def test_it_waits_for_the_next_minute_when_the_allowance_is_used_up() -> None:
    sleeps = Sleeps()
    http = FakeHttp(status_reply(), reply(minute_left=0), reply(), reply())
    adapter(http, sleeps).fetch(request())
    assert sleeps.seconds == [61]


def test_after_too_many_requests_it_waits_then_tries_once_more() -> None:
    sleeps = Sleeps()
    http = FakeHttp(status_reply(), reply(429), reply(), reply(), reply())
    assert len(adapter(http, sleeps).fetch(request())) == 3
    assert sleeps.seconds == [61]
    assert len(http.calls) == 5


def test_the_rate_limit_error_sent_with_http_200_is_handled_the_same_way() -> None:
    sleeps = Sleeps()
    limited = error_reply(rateLimit="Too many requests. Your rate limit is 10 requests per minute.")
    http = FakeHttp(status_reply(), limited, reply(), reply(), reply())
    assert len(adapter(http, sleeps).fetch(request())) == 3
    assert sleeps.seconds == [61]


def test_two_rate_limit_answers_in_a_row_fail_the_provider() -> None:
    with pytest.raises(ProviderError, match="twice in a row"):
        adapter(FakeHttp(status_reply(), reply(429), reply(429))).fetch(request())


def test_garbled_rate_limit_headers_are_ignored() -> None:
    sleeps = Sleeps()
    garbled = HttpResponse(
        200, {"x-ratelimit-remaining": "lots"}, (FIXTURES / "fixtures_day.json").read_bytes()
    )
    adapter(FakeHttp(status_reply(), garbled, reply(), reply()), sleeps).fetch(request())
    assert sleeps.seconds == []


def test_a_run_is_far_below_ten_calls_a_minute() -> None:
    """One status call and at most three days: four calls, however many competitions there are."""
    http = FakeHttp(status_reply(), *day_replies())
    targets = [target(str(n), f"league-{n}") for n in range(40)]
    adapter(http).fetch(request(*targets))
    assert len(http.calls) == 4


# --- wiring -------------------------------------------------------------------------------------


def test_the_default_registry_builds_this_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KEY_ENV, KEY)
    registry = default_registry()
    assert "api-football" in registry.names()
    assert isinstance(registry.create("api-football"), ApiFootballAdapter)


def test_a_missing_key_shows_up_as_a_failed_provider_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(KEY_ENV, raising=False)
    plan = plan_fetches(load_competitions(LEGACY_COMPETITIONS), TODAY)
    only_this = [r for r in plan if r.provider == "api-football"]
    [outcome] = fetch_all(only_this, default_registry())
    assert outcome.responses == ()
    assert outcome.error == f"{KEY_ENV} is not set"


def test_the_frozen_config_asks_api_football_for_ten_leagues_until_tomorrow() -> None:
    plan = plan_fetches(load_competitions(LEGACY_COMPETITIONS), TODAY)
    [api_football] = [r for r in plan if r.provider == "api-football"]
    assert {t.provider_id for t in api_football.targets} == {
        "73", "475", "624", "629", "477", "11", "13", "71", "34", "10",
    }  # fmt: skip
    assert all(t.window == WINDOW for t in api_football.targets)


def test_the_national_team_competitions_are_covered_by_their_league_ids() -> None:
    by_id = {c.id: c for c in load_competitions(LEGACY_COMPETITIONS)}
    for competition_id, league_id in (
        ("eliminatorias-copa-do-mundo", "34"),
        ("amistosos-selecoes", "10"),
    ):
        [source] = by_id[competition_id].sources
        assert (source.provider, source.provider_id, source.horizon_days) == (
            "api-football", league_id, 1,
        )  # fmt: skip
        assert by_id[competition_id].coverage == "short"


def test_what_the_adapter_returns_can_be_loaded_into_the_warehouse(tmp_path: Path) -> None:
    http = FakeHttp(status_reply(), *day_replies())
    responses = adapter(http).fetch(request(target("73", "copa-do-brasil")))
    con = connect(tmp_path / "w.duckdb")
    assert load_provider_responses(con, responses) == 3
    rows = con.execute(
        "select provider, resource, competition_id, payload from raw_provider_responses"
    ).fetchall()
    assert {(r[0], r[1], r[2]) for r in rows} == {("api-football", "fixtures", None)}
    assert json.loads(rows[0][3])["response"][0]["fixture"]["id"] == 880001
