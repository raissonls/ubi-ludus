"""The speed and weight targets (M5-02): the budget, the checker and the Pages-like server."""

from __future__ import annotations

import gzip
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ubi_ludus.quality.lighthouse import (
    CACHE_CONTROL,
    Budget,
    check,
    main,
    make_server,
    measure,
    middle,
    problems,
    table,
)

SITE = Path(__file__).resolve().parents[2] / "site"


def report(
    *,
    performance: float = 0.98,
    accessibility: float = 1.0,
    best: float = 1.0,
    seo: float = 1.0,
    lcp: float = 1200,
    cls: float = 0.02,
    tbt: float = 0,
    scripts: tuple[int, ...] = (1500, 2900, 2200),
) -> dict[str, Any]:
    """The parts of a Lighthouse report the checker reads."""
    items: list[dict[str, Any]] = [{"resourceType": "Script", "transferSize": n} for n in scripts]
    items += [
        {"resourceType": "Stylesheet", "transferSize": 99999},
        {"resourceType": "Document", "transferSize": 3000},
    ]
    return {
        "categories": {
            "performance": {"score": performance},
            "accessibility": {"score": accessibility},
            "best-practices": {"score": best},
            "seo": {"score": seo},
        },
        "audits": {
            "largest-contentful-paint": {"numericValue": lcp},
            "cumulative-layout-shift": {"numericValue": cls},
            "total-blocking-time": {"numericValue": tbt},
            "network-requests": {"details": {"items": items}},
        },
    }


# --- reading a report ---------------------------------------------------------------------------


def test_the_numbers_of_a_report_are_read_and_only_scripts_count_as_javascript() -> None:
    found = measure(report(scripts=(1024, 2048, 1024)))
    assert found.js_kb == 4.0  # the stylesheet and the document are not JavaScript
    assert (found.lcp_ms, found.cls, found.tbt_ms) == (1200, 0.02, 0)
    assert found.scores == {
        "performance": 0.98,
        "accessibility": 1.0,
        "best-practices": 1.0,
        "seo": 1.0,
    }


def test_the_middle_of_three_runs_is_used_so_one_bad_run_does_not_fail_the_build() -> None:
    runs = [
        measure(report(lcp=lcp, cls=cls, performance=perf))
        for lcp, cls, perf in ((1100, 0.01, 0.99), (4800, 0.3, 0.6), (1300, 0.03, 0.97))
    ]
    found = middle(runs)
    assert found.lcp_ms == 1300 and found.cls == 0.03 and found.scores["performance"] == 0.97


# --- the targets --------------------------------------------------------------------------------


def test_a_site_inside_every_target_has_nothing_over() -> None:
    assert problems(measure(report())) == []


@pytest.mark.parametrize(
    ("change", "words"),
    [
        ({"performance": 0.76}, "performance is 76, the target is 90 or more"),
        ({"accessibility": 0.89}, "accessibility is 89"),
        ({"best": 0.5}, "best-practices is 50"),
        ({"seo": 0.0}, "seo is 0"),
        ({"lcp": 2600}, "Largest Contentful Paint is 2.60 s, the target is 2.5 s or less"),
        ({"cls": 1.081}, "layout shift is 1.081, the target is 0.1 or less"),
        ({"tbt": 450}, "blocking time is 450 ms"),
        (
            {"scripts": (60 * 1024, 50 * 1024)},
            "JavaScript is 110.0 KB gzipped, the target is 100 or less",
        ),
    ],
)
def test_each_target_that_is_missed_is_named_in_words(change: dict[str, Any], words: str) -> None:
    assert [line for line in problems(measure(report(**change))) if words in line]


def test_the_targets_are_the_ones_in_the_prd() -> None:
    budget = Budget()
    assert (budget.min_score, budget.max_lcp_ms, budget.max_cls, budget.max_js_kb) == (
        0.9,
        2500,
        0.1,
        100,
    )


def test_a_value_exactly_on_the_target_passes() -> None:
    edge = report(performance=0.9, lcp=2500, cls=0.1, scripts=(100 * 1024,))
    assert problems(measure(edge)) == []


def test_the_table_says_ok_or_over_for_each_line() -> None:
    text = table(measure(report(cls=0.5)), runs=3)
    assert "the middle of 3 run(s)" in text
    assert "| Layout shift | 0.500 | 0.1 or less | **over** |" in text
    assert "| Performance | 98 | 90 or more | ok |" in text
    assert "| JavaScript, gzipped | 6.4 KB | 100 KB or less | ok |" in text


# --- the command --------------------------------------------------------------------------------


def write(tmp_path: Path, *documents: dict[str, Any]) -> list[Path]:
    paths = []
    for number, document in enumerate(documents):
        path = tmp_path / f"lh-{number}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)
    return paths


def test_check_reads_the_reports_and_returns_the_table_and_the_problems(tmp_path: Path) -> None:
    text, over = check(write(tmp_path, report(), report(), report(cls=1.0)))
    assert over == [] and "the middle of 3 run(s)" in text  # the one bad run is outvoted


def test_check_with_no_report_is_an_error() -> None:
    with pytest.raises(ValueError, match="no Lighthouse report"):
        check([])


def test_the_command_exits_0_inside_the_targets_and_1_outside(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = write(tmp_path, report())
    assert main(["check", str(good[0])]) == 0
    assert "| Largest Contentful Paint | 1.20 s |" in capsys.readouterr().out
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(report(cls=1.081, lcp=3100)), encoding="utf-8")
    assert main(["check", str(bad)]) == 1
    captured = capsys.readouterr()
    assert "over the target: layout shift is 1.081" in captured.err
    assert "over the target: Largest Contentful Paint is 3.10 s" in captured.err


# --- the server ---------------------------------------------------------------------------------


@pytest.fixture
def server(tmp_path: Path) -> Iterator[str]:
    site = tmp_path / "site"
    (site / "js").mkdir(parents=True)
    (site / "index.html").write_text("<!doctype html><title>x</title>" + "a" * 500, "utf-8")
    (site / "js" / "main.js").write_text("export const a = 1;\n" * 100, encoding="utf-8")
    (site / "logo.bin").write_bytes(b"\x00\x01\x02")
    data = tmp_path / "data"
    data.mkdir()
    (data / "status.json").write_text('{"ok": true}', encoding="utf-8")
    running = make_server(site, data, 0)
    thread = threading.Thread(target=running.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{running.server_address[1]}"
    running.shutdown()
    running.server_close()


def get(url: str, encoding: str | None = None) -> tuple[int, dict[str, str], bytes]:
    headers = {"Accept-Encoding": encoding} if encoding else {}
    request = urllib.request.Request(url, headers=headers)  # noqa: S310 - the local test server
    with urllib.request.urlopen(request) as response:  # noqa: S310
        return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()


def test_text_files_are_compressed_and_cached_the_way_pages_sends_them(server: str) -> None:
    status, headers, body = get(f"{server}/js/main.js", "gzip")
    assert status == 200 and headers["content-encoding"] == "gzip"
    assert headers["cache-control"] == CACHE_CONTROL == "max-age=600"
    assert headers["content-type"].startswith("text/javascript")
    assert gzip.decompress(body).startswith(b"export const a = 1;")
    assert len(body) < 100  # it really is smaller


def test_a_client_that_does_not_ask_for_gzip_gets_the_plain_file(server: str) -> None:
    _, headers, body = get(f"{server}/js/main.js")
    assert "content-encoding" not in headers and body.startswith(b"export const a = 1;")


def test_a_folders_address_serves_its_index_and_data_comes_from_the_data_folder(
    server: str,
) -> None:
    assert b"<title>x</title>" in get(f"{server}/")[2]
    assert json.loads(get(f"{server}/data/status.json")[2]) == {"ok": True}


def test_a_file_that_is_not_text_and_a_missing_one_are_left_to_the_plain_server(
    server: str,
) -> None:
    assert get(f"{server}/logo.bin", "gzip")[2] == b"\x00\x01\x02"
    with pytest.raises(urllib.error.HTTPError) as caught:
        get(f"{server}/nothing.html")
    assert caught.value.code == 404


# --- the real site ------------------------------------------------------------------------------


def test_the_sites_javascript_is_inside_its_budget_before_it_is_ever_measured() -> None:
    """Total JavaScript at most 100 KB gzipped (NFR). The CI run measures what is really sent."""
    total = sum(len(gzip.compress(path.read_bytes(), 6)) for path in (SITE / "js").glob("*.js"))
    assert total / 1024 <= Budget().max_js_kb
    assert total / 1024 < 60  # and with room: this is what the budget protects
