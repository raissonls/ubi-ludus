import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from ubi_ludus.pipeline.previous import fetch_previous_matches
from ubi_ludus.pipeline.providers.base import ProviderError
from ubi_ludus.pipeline.providers.http import HttpGet, HttpResponse
from ubi_ludus.pipeline.warehouse import connect, load_previous_matches

URL = "https://example.test/matches.json"


def serving(status: int, body: bytes) -> HttpGet:
    def get(url: str, headers: Mapping[str, str]) -> HttpResponse:
        assert url == URL
        return HttpResponse(status, {}, body)

    return get


def document() -> dict[str, Any]:
    return {"schema_version": "1.0", "generated_at": "2026-11-01T09:00:00Z", "matches": []}


def test_a_good_file_is_returned() -> None:
    body = json.dumps(document()).encode()
    assert fetch_previous_matches(URL, serving(200, body)) == document()


@pytest.mark.parametrize(
    ("status", "body", "expected_log"),
    [
        (404, b"not found", "HTTP 404"),
        (200, b"<html>maintenance</html>", "not usable"),
        (200, b'{"schema_version": "1.0"}', "not usable"),
        (200, b"\xff\xfe", "not usable"),
    ],
)
def test_a_missing_or_damaged_file_gives_none_and_a_warning(
    status: int, body: bytes, expected_log: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert fetch_previous_matches(URL, serving(status, body)) is None
    assert expected_log in caplog.text


def test_a_network_failure_gives_none_and_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    def broken(url: str, headers: Mapping[str, str]) -> HttpResponse:
        raise ProviderError("Network error: unreachable")

    with caplog.at_level(logging.WARNING):
        assert fetch_previous_matches(URL, broken) is None
    assert "unreachable" in caplog.text


def test_a_url_that_is_not_https_gives_none(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert fetch_previous_matches("http://example.test/matches.json") is None
    assert "Only https" in caplog.text


def test_previous_matches_load_with_or_without_a_file(tmp_path: Path) -> None:
    con = connect(tmp_path / "w.duckdb")
    assert load_previous_matches(con, None) == 0
    assert con.execute("select count(*) from raw_previous_matches").fetchone() == (0,)

    previous = document()
    previous["matches"] = [
        {
            "id": "football-data-1",
            "kickoff_utc": "2026-11-04T22:30:00Z",
            "status": "rescheduled",
            "rescheduled_at": "2026-11-02T08:00:00Z",
        }
    ]
    assert load_previous_matches(con, previous) == 1
    assert con.execute("select id, rescheduled_at from raw_previous_matches").fetchall() == [
        ("football-data-1", "2026-11-02T08:00:00Z")
    ]
    con.close()
