"""Response cache, rate limiter, call budget and call log (PRD FR-03)."""

import json
import logging
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest

from ubi_ludus.pipeline.fetch import fetch_all
from ubi_ludus.pipeline.providers.api_football import ApiFootballAdapter
from ubi_ludus.pipeline.providers.base import (
    FetchRequest,
    FetchTarget,
    ProviderError,
)
from ubi_ludus.pipeline.providers.cache import CACHE_HIT_HEADER, ResponseCache, is_cacheable
from ubi_ludus.pipeline.providers.default import LIMITS, default_registry
from ubi_ludus.pipeline.providers.football_data import FootballDataAdapter
from ubi_ludus.pipeline.providers.guard import (
    CallBudget,
    CallLog,
    GuardedHttp,
    QuotaExceededError,
    RateLimiter,
)
from ubi_ludus.pipeline.providers.http import HttpResponse
from ubi_ludus.pipeline.providers.registry import AdapterRegistry
from ubi_ludus.pipeline.window import DateWindow, window_for

URL = "https://api.example.org/v4/things?from=2026-11-01"
TODAY = date(2026, 11, 2)
SECRET = "fake-key-fake-key"  # noqa: S105 - a fake value, used to prove it never leaks


class Clock:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class Network:
    """Stands in for the network: plays back replies and counts the calls that reach it."""

    def __init__(self, *replies: HttpResponse) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls.append((url, dict(headers)))
        return self.replies.pop(0) if self.replies else ok()


def ok(body: str = '{"matches": []}', headers: dict[str, str] | None = None) -> HttpResponse:
    return HttpResponse(200, headers or {}, body.encode())


# --- the response cache --------------------------------------------------------------------------


def test_a_stored_reply_comes_back_with_the_same_body_and_is_marked_as_a_hit(
    tmp_path: Path,
) -> None:
    cache = ResponseCache(tmp_path)
    body = '{"name": "Grêmio"}'.encode()
    assert cache.put("p", URL, HttpResponse(200, {"x-ratelimit-remaining": "0"}, body))

    hit = cache.get("p", URL)
    assert hit is not None
    assert hit.status == 200
    assert hit.body == body
    # What describes the moment of the call is not replayed: it would make a run wait for nothing.
    assert hit.headers == {CACHE_HIT_HEADER: "hit"}


def test_the_key_is_the_provider_and_the_url_nothing_else(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path)
    cache.put("p", URL, ok())
    assert cache.get("p", URL) is not None
    assert cache.get("p", URL + "&page=2") is None
    assert cache.get("other", URL) is None


def test_nothing_secret_reaches_the_cache_directory(tmp_path: Path) -> None:
    network = Network(ok())
    guard = GuardedHttp("p", network, cache=ResponseCache(tmp_path))
    guard(URL, {"X-Auth-Token": SECRET})
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert files
    assert all(SECRET not in p.name and SECRET not in p.read_text("utf-8") for p in files)
    assert all("api.example.org" not in p.name for p in files)


def test_an_entry_is_used_until_it_is_as_old_as_the_time_to_live(tmp_path: Path) -> None:
    clock = Clock()
    cache = ResponseCache(tmp_path, ttl_seconds=100, now=clock)
    cache.put("p", URL, ok())
    clock.now += 99.9
    assert cache.get("p", URL) is not None
    clock.now += 0.1
    assert cache.get("p", URL) is None


@pytest.mark.parametrize(
    "reply",
    [
        HttpResponse(404, {}, b'{"matches": []}'),
        HttpResponse(429, {}, b'{"matches": []}'),
        HttpResponse(200, {}, b"<html>"),
        HttpResponse(200, {}, b"[1, 2]"),
        HttpResponse(200, {}, b'{"errors": {"plan": "Free plans do not have access"}}'),
        HttpResponse(200, {}, b'{"errors": ["something"]}'),
    ],
)
def test_only_a_successful_answer_with_data_is_stored(tmp_path: Path, reply: HttpResponse) -> None:
    cache = ResponseCache(tmp_path)
    assert is_cacheable(reply) is False
    assert cache.put("p", URL, reply) is False
    assert cache.get("p", URL) is None
    assert not list(tmp_path.rglob("*.json"))


def test_an_empty_errors_list_is_a_normal_answer() -> None:
    assert is_cacheable(ok('{"errors": [], "response": []}'))


def test_a_damaged_entry_is_a_miss_not_a_failure(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path)
    cache.put("p", URL, ok())
    [entry] = tmp_path.rglob("*.json")
    for damaged in ("{ not json", "[]", '{"stored_at": "soon"}', '{"body": "x"}'):
        entry.write_text(damaged, encoding="utf-8")
        assert cache.get("p", URL) is None


def test_a_cache_that_cannot_be_written_is_only_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file where the cache wants a folder", encoding="utf-8")
    assert ResponseCache(blocker).put("p", URL, ok()) is False
    assert "Could not write the response cache" in caplog.text


def test_prune_removes_expired_and_damaged_entries_and_keeps_fresh_ones(tmp_path: Path) -> None:
    clock = Clock()
    cache = ResponseCache(tmp_path, ttl_seconds=100, now=clock)
    cache.put("p", "https://x/old", ok())
    clock.now += 60
    cache.put("p", "https://x/fresh", ok())
    clock.now += 60  # "old" is 120 s old, "fresh" 60 s
    (tmp_path / "p" / "broken.json").write_text("{", encoding="utf-8")

    assert cache.prune() == 2
    assert cache.get("p", "https://x/fresh") is not None
    assert cache.get("p", "https://x/old") is None
    assert len(list((tmp_path / "p").glob("*.json"))) == 1
    assert ResponseCache(tmp_path / "missing").prune() == 0


def test_prune_that_cannot_delete_only_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    cache = ResponseCache(tmp_path, ttl_seconds=0)
    cache.put("p", URL, ok())

    def refuse(_self: Path, *_a: object, **_k: object) -> None:
        raise PermissionError("in use")

    monkeypatch.setattr(Path, "unlink", refuse)
    assert cache.prune() == 0
    assert "Could not remove" in caplog.text


# --- the rate limiter ----------------------------------------------------------------------------


def test_calls_under_the_limit_do_not_wait() -> None:
    clock = Clock()
    limiter = RateLimiter(3, 60, clock=clock, sleep=clock.sleep)
    assert [limiter.wait() for _ in range(3)] == [0, 0, 0]
    assert clock.slept == []


def test_the_call_over_the_limit_waits_until_the_oldest_one_leaves_the_window() -> None:
    clock = Clock()
    limiter = RateLimiter(3, 60, clock=clock, sleep=clock.sleep)
    limiter.wait()  # t = 1000
    clock.now += 10
    limiter.wait()  # 1010
    limiter.wait()  # 1010
    clock.now += 5  # 1015: the oldest call is 15 s old
    assert limiter.wait() == 45
    assert clock.slept == [45]


def test_never_more_than_the_limit_in_any_window_however_the_calls_are_spaced() -> None:
    clock = Clock()
    limiter = RateLimiter(10, 60, clock=clock, sleep=clock.sleep)
    stamps = []
    for _ in range(35):
        limiter.wait()
        stamps.append(clock.now)
        clock.now += 1.5
    for index, start in enumerate(stamps):
        assert len([s for s in stamps[index:] if s - start < 60]) <= 10


def test_calls_that_are_old_enough_are_forgotten() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock=clock, sleep=clock.sleep)
    limiter.wait()
    clock.now += 60
    assert limiter.wait() == 0


def test_a_limit_below_one_is_a_mistake() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        RateLimiter(0)


# --- the call budget -----------------------------------------------------------------------------


def test_the_budget_allows_its_calls_and_refuses_the_next() -> None:
    budget = CallBudget("p", 2)
    budget.spend()
    budget.spend()
    with pytest.raises(QuotaExceededError, match="p call budget of 2 used up"):
        budget.spend()
    assert budget.used == 2
    assert isinstance(QuotaExceededError("x"), ProviderError)


def test_without_a_limit_the_budget_never_refuses() -> None:
    budget = CallBudget("p")
    for _ in range(500):
        budget.spend()
    assert budget.used == 500


def test_allow_only_counts_from_now_and_never_goes_negative() -> None:
    budget = CallBudget("p", 100)
    budget.spend()
    budget.allow_only(1)
    budget.spend()
    with pytest.raises(QuotaExceededError):
        budget.spend()
    budget.allow_only(-5)
    with pytest.raises(QuotaExceededError):
        budget.spend()


# --- the guard -----------------------------------------------------------------------------------


def test_a_call_reaches_the_network_once_and_is_counted_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    log = CallLog()
    network = Network(ok())
    GuardedHttp("p", network, call_log=log)(URL, {"X-Auth-Token": SECRET})

    assert len(network.calls) == 1
    assert (log.stats("p").network, log.stats("p").cached, log.stats("p").total) == (1, 0, 1)
    assert "p GET /v4/things?from=2026-11-01: HTTP 200" in caplog.text
    assert SECRET not in caplog.text


def test_a_log_line_names_no_host_and_a_url_without_a_query_is_just_its_path(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    GuardedHttp("p", Network(ok()))("https://api.example.org/status", {})
    assert "p GET /status: HTTP 200" in caplog.text
    assert "api.example.org" not in caplog.text


def test_a_second_identical_request_is_answered_from_the_cache_for_free(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    log = CallLog()
    clock = Clock()
    network = Network(ok('{"n": 1}'))
    budget = CallBudget("p", 1)
    guard = GuardedHttp(
        "p",
        network,
        cache=ResponseCache(tmp_path),
        limiter=RateLimiter(1, 60, clock=clock, sleep=clock.sleep),
        budget=budget,
        call_log=log,
    )

    first = guard(URL, {})
    second = guard(URL, {})

    assert second.body == first.body
    assert len(network.calls) == 1
    assert (log.stats("p").network, log.stats("p").cached) == (1, 1)
    assert budget.used == 1  # a cache hit costs no budget
    assert clock.slept == []  # and no waiting
    assert "from cache" in caplog.text


def test_a_request_marked_never_cache_always_goes_to_the_network(tmp_path: Path) -> None:
    network = Network(ok(), ok())
    guard = GuardedHttp(
        "p", network, cache=ResponseCache(tmp_path), never_cache=lambda url: "things" in url
    )
    guard(URL, {})
    guard(URL, {})
    assert len(network.calls) == 2
    assert not list(tmp_path.rglob("*.json"))


def test_an_answer_that_is_not_worth_replaying_is_not_cached(tmp_path: Path) -> None:
    network = Network(HttpResponse(500, {}, b"{}"), ok())
    guard = GuardedHttp("p", network, cache=ResponseCache(tmp_path))
    assert guard(URL, {}).status == 500
    assert guard(URL, {}).status == 200
    assert len(network.calls) == 2


def test_the_budget_stops_calls_before_they_reach_the_network() -> None:
    network = Network()
    guard = GuardedHttp("p", network, budget=CallBudget("p", 3))
    for _ in range(3):
        guard(URL, {})
    with pytest.raises(QuotaExceededError):
        guard(URL, {})
    assert len(network.calls) == 3


def test_the_limiter_waits_before_the_call_not_after() -> None:
    clock = Clock()
    seen: list[float] = []

    def network(_url: str, _headers: Mapping[str, str]) -> HttpResponse:
        seen.append(clock.now)
        return ok()

    guard = GuardedHttp("p", network, limiter=RateLimiter(1, 60, clock=clock, sleep=clock.sleep))
    guard(URL, {})
    guard(URL, {})
    assert seen == [1000.0, 1060.0]


def test_the_run_summary_is_logged_with_the_total_over_the_network(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    log = CallLog()
    GuardedHttp("a", Network(), call_log=log)(URL, {})
    GuardedHttp("b", Network(), call_log=log)(URL, {})
    log.log_summary()
    assert log.network_calls == 2
    assert "a 1 (1 over the network, 0 from cache); b 1" in caplog.text
    assert "Total over the network: 2" in caplog.text


def test_an_empty_run_logs_none(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    CallLog().log_summary()
    assert "Provider calls this run: none. Total over the network: 0" in caplog.text


# --- the adapters behind the guard ---------------------------------------------------------------


def guarded_football_data(network: Network, limit: int | None) -> FootballDataAdapter:
    guard = GuardedHttp("football-data", network, budget=CallBudget("football-data", limit))
    return FootballDataAdapter("token-value", http_get=guard, sleep=lambda _s: None)


def football_data_request(count: int) -> FetchRequest:
    window = DateWindow(date(2026, 11, 1), date(2026, 11, 16))
    targets = tuple(FetchTarget(f"c{n}", f"C{n}", window) for n in range(count))
    return FetchRequest("football-data", targets, TODAY)


def test_football_data_stops_when_its_budget_is_used_up_and_keeps_what_it_has() -> None:
    network = Network()
    engine = guarded_football_data(network, limit=2)
    responses = engine.fetch(football_data_request(5))

    assert [r.competition_id for r in responses] == ["c0", "c1"]
    assert len(network.calls) == 2
    assert [competition for competition, _ in engine.skipped] == ["c2", "c3", "c4"]


def test_football_data_with_no_budget_at_all_fails_without_a_call() -> None:
    network = Network()
    with pytest.raises(ProviderError, match="served none of the competitions"):
        guarded_football_data(network, limit=0).fetch(football_data_request(2))
    assert network.calls == []


def api_football_status(current: int) -> HttpResponse:
    body = {"errors": [], "response": {"requests": {"current": current, "limit_day": 100}}}
    return ok(json.dumps(body))


def fixtures_day() -> HttpResponse:
    return ok(json.dumps({"errors": [], "results": 0, "response": []}))


def guarded_api_football(network: Network) -> ApiFootballAdapter:
    budget = CallBudget("api-football", 10)
    guard = GuardedHttp("api-football", network, budget=budget)
    return ApiFootballAdapter(SECRET, http_get=guard, sleep=lambda _s: None, budget=budget)


def api_football_request() -> FetchRequest:
    target = FetchTarget("copa-do-brasil", "73", window_for(TODAY, 1))
    return FetchRequest("api-football", (target,), TODAY)


def test_api_football_never_asks_for_more_than_the_quota_left_even_with_a_retry() -> None:
    """98 of 100 used: two calls remain. The first day is rate limited and retried, which takes
    the second call, so the other days must wait for tomorrow instead of going over."""
    limited = HttpResponse(429, {}, b"{}")
    network = Network(api_football_status(98), limited, fixtures_day())
    engine = guarded_api_football(network)

    responses = engine.fetch(api_football_request())

    assert len(responses) == 1
    assert len(network.calls) == 3  # the status call (free) + the 2 calls left
    # Yesterday is dropped up front for lack of quota; tomorrow loses its call to the retry.
    assert [day for day, _ in engine.skipped] == ["2026-11-01", "2026-11-03"]
    assert "call budget" in engine.skipped[1][1]


def test_api_football_with_the_quota_used_up_makes_no_fixture_call() -> None:
    network = Network(api_football_status(100))
    with pytest.raises(ProviderError, match="daily quota is used up"):
        guarded_api_football(network).fetch(api_football_request())
    assert len(network.calls) == 1


# --- the default registry, end to end ------------------------------------------------------------


def registry_fixtures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, network: Network
) -> tuple[AdapterRegistry, CallLog, Clock]:
    monkeypatch.setenv("FOOTBALL_DATA_TOKEN", "token-value")
    monkeypatch.setenv("API_FOOTBALL_KEY", SECRET)
    clock = Clock()
    log = CallLog()
    registry = default_registry(
        cache_dir=tmp_path / "cache", call_log=log, http=network, sleep=clock.sleep, clock=clock
    )
    return registry, log, clock


def test_the_pipeline_stops_calling_when_the_run_would_exceed_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    network = Network()
    registry, log, clock = registry_fixtures(tmp_path, monkeypatch, network)
    fuse = LIMITS["football-data"].calls_per_run
    assert fuse is not None

    [outcome] = fetch_all([football_data_request(fuse + 15)], registry, log)

    assert len(network.calls) == fuse  # the call over the fuse never left the machine
    assert len(outcome.responses) == fuse
    assert outcome.error is None
    assert f"Total over the network: {fuse}" in caplog.text
    # And the per-minute limit held on the way: 10 calls, then a wait for the window to move on.
    assert clock.slept
    assert max(clock.slept) <= 60


def test_a_second_run_inside_the_hour_costs_nothing_but_the_quota_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache saves the fixture calls; the status call is never replayed, it is today's news."""
    football_data = football_data_request(3)
    api_football = api_football_request()
    network = Network(  # in the order the calls are made: API-Football first, then football-data
        api_football_status(5), fixtures_day(), fixtures_day(), fixtures_day(), ok(), ok(), ok()
    )

    first_registry, first_log, _ = registry_fixtures(tmp_path, monkeypatch, network)
    fetch_all([api_football, football_data], first_registry, first_log)
    assert first_log.network_calls == 7
    assert len(network.calls) == 7

    network.replies = [api_football_status(12)]
    second_registry, second_log, _ = registry_fixtures(tmp_path, monkeypatch, network)
    outcomes = fetch_all([api_football, football_data], second_registry, second_log)

    assert len(network.calls) == 8  # only the status call went out
    assert second_log.network_calls == 1
    assert second_log.stats("football-data").cached == 3
    assert second_log.stats("api-football").cached == 3
    assert [len(o.responses) for o in outcomes] == [3, 3]


def test_the_cache_is_pruned_when_the_registry_is_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ResponseCache(tmp_path / "cache", ttl_seconds=3600).put("football-data", URL, ok())
    [stale] = (tmp_path / "cache").rglob("*.json")
    monkeypatch.setenv("FOOTBALL_DATA_TOKEN", "token-value")
    default_registry(cache_dir=tmp_path / "cache", cache_ttl_seconds=0)
    assert not stale.exists()


def test_without_a_cache_directory_nothing_is_written_to_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FOOTBALL_DATA_TOKEN", "token-value")
    registry = default_registry(http=Network(), sleep=lambda _s: None)
    fetch_all([football_data_request(2)], registry)
    assert list(tmp_path.iterdir()) == []


def test_the_run_total_is_logged_even_when_a_provider_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    network = Network(HttpResponse(401, {}, b"{}"))
    registry, log, _ = registry_fixtures(tmp_path, monkeypatch, network)
    [outcome] = fetch_all([football_data_request(2)], registry, log)
    assert outcome.error is not None
    assert "Total over the network: 1" in caplog.text
    assert "token-value" not in caplog.text
    assert SECRET not in caplog.text


def test_the_documented_limits_are_ten_calls_a_minute() -> None:
    assert {name: limit.calls_per_minute for name, limit in LIMITS.items()} == {
        "football-data": 10,
        "api-football": 10,
    }
