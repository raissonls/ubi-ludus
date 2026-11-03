"""Browser fixtures: the site served from a throwaway local server, and a browser to open it.

Needs a Chromium. In CI it is installed (`playwright install chromium`) and a missing browser is a
failure (UBI_LUDUS_REQUIRE_BROWSER=1). On a developer machine the tests use Chromium if it is
there, else Chrome or Edge, and skip when there is none.
"""

import functools
import http.server
import os
import threading
from collections.abc import Iterator
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Browser, Playwright, sync_playwright
from site_browser import DATA, GALLERY, SITE


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the base class name
        return

    def translate_path(self, path: str) -> str:
        clean = urlparse(path).path
        if clean.startswith("/data/"):
            return str(DATA / clean.removeprefix("/data/"))
        if clean.startswith("/gallery/"):  # the test-only page that draws every card
            return str(GALLERY / clean.removeprefix("/gallery/"))
        return super().translate_path(path)


class Server(http.server.ThreadingHTTPServer):
    # The default queue holds 5 connections; a page loads some twenty files at once, and under
    # load a refused connection left the page without its scripts and the test waiting for nothing.
    request_queue_size = 128


@pytest.fixture(scope="module")
def origin() -> Iterator[str]:
    handler = functools.partial(QuietHandler, directory=str(SITE))
    server = Server(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def launch(playwright: Playwright) -> Browser:
    errors = []
    for channel in (None, "chrome", "msedge"):
        try:
            return playwright.chromium.launch(channel=channel)
        except Exception as exc:  # noqa: BLE001 - any launch failure means "try the next one"
            errors.append(f"{channel or 'chromium'}: {str(exc).splitlines()[0]}")
    message = "No browser for the site tests (" + "; ".join(errors) + ")"
    if os.environ.get("UBI_LUDUS_REQUIRE_BROWSER") == "1":
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        found = launch(playwright)
        yield found
        found.close()
