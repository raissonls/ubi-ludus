"""Structured logs for the pipeline (PRD FR-54, FR-03, risk R7).

One JSON object per line, on standard error, so the Actions log can be read by a person and
searched by a tool (``grep '"event": "run_summary"'``, or ``jq`` on a downloaded log). Every record
has ``time`` (UTC), ``level``, ``logger`` and ``message``; a record can carry more fields, which
sit at the top level next to them::

    logger.info("Provider calls this run", extra={"fields": {"event": "provider_calls", ...}})

Secrets never reach the log: the value of every environment variable whose name looks like a
secret (TOKEN, KEY, PASSWORD, SECRET) is replaced by ``***`` wherever it appears in a record, as a
safety net behind code that should not log secrets in the first place.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import IO, Any

#: The variable that sets the level (DEBUG, INFO, WARNING, ERROR); INFO when it is not set.
LEVEL_ENV = "UBI_LUDUS_LOG_LEVEL"
_SECRET_NAMES = ("TOKEN", "KEY", "PASSWORD", "SECRET")
#: Values shorter than this are not treated as secrets (a one-letter value would blank the log).
_MIN_SECRET_LENGTH = 6
#: What a handler installed by :func:`configure_logging` is called, so it is only added once.
_HANDLER_NAME = "ubi-ludus-json"


def secret_values(environ: Mapping[str, str] | None = None) -> list[str]:
    """The values of the environment variables that look like secrets, longest first."""
    env = os.environ if environ is None else environ
    values = {
        value.strip()
        for name, value in env.items()
        if any(part in name.upper() for part in _SECRET_NAMES)
        and len(value.strip()) >= _MIN_SECRET_LENGTH
    }
    return sorted(values, key=len, reverse=True)


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, "***")
    return text


class JsonFormatter(logging.Formatter):
    """A record as one line of JSON, with its extra fields and any exception, secrets removed."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            # The four basic keys are never overwritten by a field of the same name.
            entry.update({k: v for k, v in fields.items() if k not in entry})
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        line = json.dumps(entry, ensure_ascii=False, default=str, sort_keys=False)
        return redact(line, secret_values())


def configure_logging(
    stream: IO[str] | None = None,
    level: str | None = None,
) -> logging.Handler:
    """Send every log record to ``stream`` (standard error) as JSON lines.

    Safe to call more than once: the handler is replaced, never doubled.
    """
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing in [h for h in root.handlers if h.get_name() == _HANDLER_NAME]:
        root.removeHandler(existing)
    root.addHandler(handler)
    chosen = (level or os.environ.get(LEVEL_ENV) or "INFO").upper()
    root.setLevel(chosen if chosen in logging.getLevelNamesMapping() else "INFO")
    return handler


def event(logger: logging.Logger, message: str, name: str, **fields: Any) -> None:
    """Log an INFO record that is also a named event with data, for ``grep`` and ``jq``."""
    logger.info(message, extra={"fields": {"event": name, **fields}})
