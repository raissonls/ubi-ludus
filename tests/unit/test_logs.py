"""Structured logs (FR-54, FR-03, R7): one JSON line per record, call counts, no secrets."""

from __future__ import annotations

import io
import json
import logging
from typing import Any

import pytest
from log_helpers import leave_logging_as_found  # noqa: F401 - an autouse fixture

from ubi_ludus.logs import (
    LEVEL_ENV,
    JsonFormatter,
    configure_logging,
    event,
    redact,
    secret_values,
)
from ubi_ludus.pipeline.providers.guard import CallLog

FAKE = "tok-3f9a7c1d5e"  # a made-up value that looks like a secret


def record(text: str = "hello", /, **fields: Any) -> logging.LogRecord:
    made = logging.LogRecord("ubi.test", logging.INFO, __file__, 1, text, (), None)
    if fields:
        made.fields = fields
    return made


def line(entry: logging.LogRecord) -> dict[str, Any]:
    text = JsonFormatter().format(entry)
    assert "\n" not in text  # one record, one line
    parsed: dict[str, Any] = json.loads(text)
    return parsed


# --- the shape -----------------------------------------------------------------------------------


def test_a_record_is_one_json_line_with_the_basic_fields() -> None:
    found = line(record("It worked"))
    assert list(found) == ["time", "level", "logger", "message"]
    assert (found["level"], found["logger"], found["message"]) == ("INFO", "ubi.test", "It worked")
    assert found["time"].endswith("Z") and len(found["time"]) == 20  # 2026-11-07T23:04:01Z


def test_extra_fields_sit_next_to_the_basic_ones_and_cannot_replace_them() -> None:
    found = line(record("m", event="x", level="HACKED", message="HACKED", numbers={"a": 1}))
    assert found["event"] == "x" and found["numbers"] == {"a": 1}
    assert found["level"] == "INFO" and found["message"] == "m"


def test_line_breaks_and_accents_stay_on_one_line_and_survive() -> None:
    found = line(record("one\ntwo\r\nthree: ação", note="a\nb"))
    assert found["message"] == "one\ntwo\r\nthree: ação" and found["note"] == "a\nb"


def test_a_value_json_cannot_hold_is_written_as_text() -> None:
    found = line(record("m", when=object))
    assert "class 'object'" in found["when"]


def test_an_exception_is_included_on_one_line() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        made = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed", (), sys.exc_info())
    found = line(made)
    assert "ValueError: boom" in found["exception"]


def test_the_message_arguments_are_filled_in() -> None:
    made = logging.LogRecord("t", logging.INFO, __file__, 1, "%d of %s", (3, "ten"), None)
    assert line(made)["message"] == "3 of ten"


# --- no secrets ----------------------------------------------------------------------------------


def test_the_values_of_secret_looking_variables_are_found_and_the_rest_are_not() -> None:
    env = {
        "FOOTBALL_DATA_TOKEN": FAKE,
        "SMTP_PASSWORD": "p4ssw0rd-xyz",
        "SOME_API_KEY": "key-1234567",
        "MY_SECRET": "s3cr3t-value",
        "SHORT_TOKEN": "abc",  # too short to be worth hiding: it would blank ordinary text
        "HOME": "/home/someone",
        "PATH": "/usr/bin",
    }
    assert set(secret_values(env)) == {FAKE, "p4ssw0rd-xyz", "key-1234567", "s3cr3t-value"}
    assert redact(f"a {FAKE} b p4ssw0rd-xyz", secret_values(env)) == "a *** b ***"
    assert redact("nothing here", secret_values(env)) == "nothing here"


def test_a_secret_is_removed_from_the_message_the_fields_and_the_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOOTBALL_DATA_TOKEN", FAKE)
    try:
        raise RuntimeError(f"rejected {FAKE}")
    except RuntimeError:
        import sys

        made = logging.LogRecord("t", logging.ERROR, __file__, 1, f"key {FAKE}", (), sys.exc_info())
    made.fields = {"detail": f"x{FAKE}y"}
    text = JsonFormatter().format(made)
    assert FAKE not in text
    assert text.count("***") == 3
    assert json.loads(text)["detail"] == "x***y"


# --- turning it on -------------------------------------------------------------------------------


def test_configure_logging_writes_json_lines_to_the_stream() -> None:
    stream = io.StringIO()
    configure_logging(stream)
    logging.getLogger("ubi.test").info("hello", extra={"fields": {"event": "greeting"}})
    [written] = stream.getvalue().splitlines()
    assert json.loads(written)["event"] == "greeting"


def test_configure_logging_twice_does_not_write_every_line_twice() -> None:
    stream = io.StringIO()
    configure_logging(stream)
    configure_logging(stream)
    logging.getLogger("ubi.test").info("once")
    assert len(stream.getvalue().splitlines()) == 1


def test_the_level_comes_from_the_environment_or_is_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LEVEL_ENV, raising=False)
    configure_logging(io.StringIO())
    assert logging.getLogger().level == logging.INFO
    monkeypatch.setenv(LEVEL_ENV, "warning")
    configure_logging(io.StringIO())
    assert logging.getLogger().level == logging.WARNING
    monkeypatch.setenv(LEVEL_ENV, "nonsense")
    configure_logging(io.StringIO())
    assert logging.getLogger().level == logging.INFO


def test_an_event_is_a_named_record_with_data() -> None:
    stream = io.StringIO()
    configure_logging(stream)
    event(logging.getLogger("ubi.test"), "Done", "thing_done", count=3)
    found = json.loads(stream.getvalue())
    assert (found["event"], found["count"], found["message"]) == ("thing_done", 3, "Done")


# --- the call counts (FR-03) ---------------------------------------------------------------------


def test_the_run_logs_how_many_calls_each_provider_got_over_the_network_and_from_cache(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = CallLog()
    calls.stats("football-data").network += 9
    calls.stats("football-data").cached += 2
    calls.stats("other").network += 1
    caplog.set_level(logging.INFO)
    calls.log_summary()
    [summary] = [
        r for r in caplog.records if getattr(r, "fields", {}).get("event") == "provider_calls"
    ]
    assert summary.fields["providers"] == {  # type: ignore[attr-defined]
        "football-data": {"total": 11, "network": 9, "cached": 2},
        "other": {"total": 1, "network": 1, "cached": 0},
    }
    assert summary.fields["network_total"] == 10  # type: ignore[attr-defined]
    assert "football-data 11 (9 over the network, 2 from cache)" in summary.getMessage()
    # And as a line of the log it is JSON that can be searched.
    assert json.loads(JsonFormatter().format(summary))["event"] == "provider_calls"


def test_a_run_with_no_calls_says_none() -> None:
    made = CallLog()
    stream = io.StringIO()
    configure_logging(stream)
    made.log_summary()
    found = json.loads(stream.getvalue())
    assert found["providers"] == {} and found["network_total"] == 0
    assert "Provider calls this run: none" in found["message"]


def test_a_plain_handler_a_library_installed_is_replaced_so_no_line_comes_out_twice() -> None:
    root = logging.getLogger()
    plain_stream = io.StringIO()
    plain = logging.StreamHandler(plain_stream)  # what importing dbt leaves on the root logger
    root.addHandler(plain)
    ours = io.StringIO()
    configure_logging(ours)
    logging.getLogger("ubi.test").info("once")
    assert plain not in root.handlers
    assert plain_stream.getvalue() == "" and len(ours.getvalue().splitlines()) == 1


def test_a_handler_that_is_not_a_plain_stream_handler_is_left_alone() -> None:
    class Collecting(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.seen.append(record.getMessage())

    mine = Collecting()
    logging.getLogger().addHandler(mine)
    configure_logging(io.StringIO())
    logging.getLogger("ubi.test").info("kept")
    assert mine.seen == ["kept"]
