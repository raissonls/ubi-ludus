"""The site in a real browser: accessibility (axe), the Content Security Policy at work, requests.

Needs a Chromium. In CI it is installed (`playwright install chromium`) and a missing browser is a
failure (UBI_LUDUS_REQUIRE_BROWSER=1). On a developer machine the tests use Chromium if it is
there, else Chrome or Edge, and skip when there is none.
"""

import functools
import http.server
import json
import os
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from axe_playwright_python.sync_playwright import Axe  # type: ignore[import-untyped]
from playwright.sync_api import Browser, Page, Playwright, Request, Route, sync_playwright

pytestmark = pytest.mark.browser

SITE = Path(__file__).resolve().parents[2] / "site"
# The published files the site loads from /data/. The pipeline writes the real ones; the tests
# serve the valid examples of the schemas.
DATA = Path(__file__).resolve().parents[1] / "fixtures" / "schemas" / "valid"
STORAGE_KEY = "ubi-ludus:preferences"
SECRET_TEAM = "time-secreto-xyz"  # noqa: S105 - a marker that must never leave the browser
SECRET_SERVICE = "servico-secreto-xyz"  # noqa: S105 - same
CHOICES = {
    STORAGE_KEY: json.dumps({"version": 1, "teams": [SECRET_TEAM], "services": [SECRET_SERVICE]})
}
STORAGE_BLOCKED = (
    "Object.defineProperty(window, 'localStorage',"
    " { get() { throw new DOMException('denied', 'SecurityError'); } });"
)
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]
WATCH_VIOLATIONS = (
    "window.__violations = [];"
    "document.addEventListener('securitypolicyviolation',"
    " e => window.__violations.push(e.violatedDirective));"
)
VIEWPORTS = {"desktop": (1280, 800), "mobile": (375, 812), "narrow": (320, 640)}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the base class name
        return

    def translate_path(self, path: str) -> str:
        clean = urlparse(path).path
        if clean.startswith("/data/"):
            return str(DATA / clean.removeprefix("/data/"))
        return super().translate_path(path)


@pytest.fixture(scope="module")
def origin() -> Iterator[str]:
    handler = functools.partial(QuietHandler, directory=str(SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
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


def answer_with(status: int) -> Callable[[Route], None]:
    return lambda route: route.fulfill(status=status)


class Visit:
    """One page load, with everything the browser reported while it happened."""

    def __init__(self, page: Page, origin: str) -> None:
        self.page = page
        self.origin = origin
        self.console: list[str] = []
        self.requests: list[str] = []
        self.details: list[Request] = []
        self.failed: list[str] = []
        page.on("console", lambda m: self.console.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: self.console.append(f"pageerror: {e}"))
        page.on("request", self._saw)
        page.on("requestfailed", lambda r: self.failed.append(r.url))

    def _saw(self, request: Request) -> None:
        self.requests.append(request.url)
        self.details.append(request)

    def open(self) -> None:
        self.page.goto(self.origin + "/index.html")
        self.page.wait_for_selector("html[data-ready='true']")


def visit(
    browser: Browser,
    origin: str,
    scheme: str = "light",
    size: str = "desktop",
    reduced_motion: str = "no-preference",
    saved: dict[str, str] | None = None,
    storage_blocked: bool = False,
    broken: dict[str, int] | None = None,
    newer_format: str | None = None,
) -> Iterator[Visit]:
    """Open the page. ``saved`` is what localStorage holds before the page runs, ``broken`` maps a
    data file to the HTTP status it answers with, `newer_format` names a data file served as if
    it were in a format the site does not know."""
    width, height = VIEWPORTS[size]
    context = browser.new_context(
        color_scheme=scheme,  # type: ignore[arg-type]
        reduced_motion=reduced_motion,  # type: ignore[arg-type]
        viewport={"width": width, "height": height},
    )
    try:
        if saved:
            items = json.dumps(saved)
            context.add_init_script(
                f"for (const [k, v] of Object.entries({items})) localStorage.setItem(k, v);"
            )
        if storage_blocked:
            context.add_init_script(STORAGE_BLOCKED)
        page = context.new_page()
        for name, status in (broken or {}).items():
            page.route(f"**/data/{name}.json", answer_with(status))
        if newer_format:
            document = json.loads((DATA / f"{newer_format}.json").read_text(encoding="utf-8"))
            document["schema_version"] = "2.0"
            page.route(
                f"**/data/{newer_format}.json",
                lambda route: route.fulfill(
                    status=200, content_type="application/json", body=json.dumps(document)
                ),
            )
        current = Visit(page, origin)
        current.open()
        yield current
    finally:
        context.close()


# --- accessibility (axe) --------------------------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_no_wcag_2_2_aa_violation(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(browser, origin, scheme, size):
        results = Axe().run(current.page, options={"runOnly": {"type": "tag", "values": WCAG_TAGS}})
        violations = [
            f"{v['id']} ({v['impact']}): {[n['target'] for n in v['nodes']]}"
            for v in results.response["violations"]
        ]
        assert violations == []


# --- the page works ------------------------------------------------------------------------------


def test_the_strings_are_on_the_page(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert page.locator("h1").inner_text() == "Onde assistir futebol no Brasil"
        assert (
            page.locator("footer")
            .inner_text()
            .count("Football data provided by the Football-Data.org API")
            == 1
        )
        assert page.locator(".brand__name").inner_text() == "Ubi Ludus"
        assert "[" not in page.locator("body").inner_text(), "a missing string shows as [key]"


def test_nothing_is_reported_wrong_and_nothing_leaves_this_origin(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        assert current.console == []
        assert current.failed == []
        assert current.requests
        assert all(url.startswith(origin + "/") for url in current.requests), current.requests


def test_the_page_never_scrolls_sideways_even_on_a_narrow_screen(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, size="narrow"):
        widths = current.page.evaluate(
            "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
        )
        assert widths[0] <= widths[1]


def test_the_skip_link_is_first_in_the_tab_order_and_moves_focus_to_the_content(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.className") == "skip-link"
        page.keyboard.press("Enter")
        assert page.evaluate("document.activeElement.id") == "main"


def test_every_focusable_thing_shows_a_focus_ring(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        for _ in range(page.locator("a").count()):
            page.keyboard.press("Tab")
            style = page.evaluate(
                "(() => { const s = getComputedStyle(document.activeElement);"
                " return [s.outlineStyle, s.outlineWidth]; })()"
            )
            assert style[0] != "none", page.evaluate("document.activeElement.outerHTML")
            assert style[1] != "0px"


# --- the data and the visitor's choices (FR-22) -----------------------------------------------


def loaded_text() -> str:
    count = len(json.loads((DATA / "matches.json").read_text(encoding="utf-8"))["matches"])
    return f"{count} jogo carregado." if count == 1 else f"{count} jogos carregados."


def test_the_published_files_are_loaded_and_counted(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        assert current.page.locator("#data-status").inner_text() == loaded_text()
        fetched = sorted(urlparse(u).path for u in current.requests if "/data/" in u)
        assert fetched == [
            f"/data/{n}.json"
            for n in sorted(["matches", "teams", "competitions", "broadcasters", "status"])
        ]


def test_no_request_carries_the_visitors_choices(browser: Browser, origin: str) -> None:
    """The choices sit in localStorage before the page runs; no request may mention them."""
    for current in visit(browser, origin, saved=CHOICES):
        current.page.click("#reset-data")
        current.page.wait_for_function("document.querySelector('#reset-result').textContent !== ''")
        assert current.details
        for request in current.details:
            text = " ".join([request.url, str(request.post_data), json.dumps(request.headers)])
            assert SECRET_TEAM not in text and SECRET_SERVICE not in text, request.url
            assert request.method == "GET", request.url
            assert request.post_data is None, request.url
            assert "?" not in request.url, "no query string"
            assert "cookie" not in request.headers, "no cookie is ever sent"
        assert current.page.context.cookies() == []
        assert current.page.evaluate("document.cookie") == ""


def test_the_reset_control_erases_the_saved_choices_and_says_so(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=CHOICES):
        page = current.page
        assert page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')") is not None
        page.get_by_role("button", name="Apagar meus dados").click()
        assert page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')") is None
        assert "apagadas" in page.locator("#reset-result").inner_text()


def test_the_reset_control_works_from_the_keyboard(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=CHOICES):
        page = current.page
        page.locator("#reset-data").focus()
        page.keyboard.press("Enter")
        assert "apagadas" in page.locator("#reset-result").inner_text()
        assert page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')") is None


def test_with_storage_blocked_the_page_still_works_and_reset_still_answers(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, storage_blocked=True):
        assert current.console == []
        assert current.page.locator("#data-status").inner_text() == loaded_text()
        current.page.click("#reset-data")
        assert "apagadas" in current.page.locator("#reset-result").inner_text()


def test_when_the_data_cannot_be_loaded_the_page_says_so_and_stays_accessible(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, broken={"matches": 500}):
        message = current.page.locator("#data-status").inner_text()
        assert message.startswith("Não foi possível carregar os jogos")
        assert any("matches.json" in line for line in current.console)
        results = Axe().run(current.page, options={"runOnly": {"type": "tag", "values": WCAG_TAGS}})
        assert results.response["violations"] == []


def test_a_data_file_in_a_newer_format_is_refused_the_same_way(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, newer_format="teams"):
        assert current.page.locator("#data-status").inner_text().startswith("Não foi possível")
        assert any("this site reads 1.x" in line for line in current.console)


# --- themes and motion ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scheme", "background"), [("light", "rgb(246, 247, 244)"), ("dark", "rgb(14, 16, 19)")]
)
def test_the_theme_follows_the_system_setting(
    browser: Browser, origin: str, scheme: str, background: str
) -> None:
    for current in visit(browser, origin, scheme):
        assert (
            current.page.evaluate("getComputedStyle(document.body).backgroundColor") == background
        )


@pytest.mark.parametrize(("setting", "duration"), [("reduce", "0s"), ("no-preference", "0.12s")])
def test_motion_stops_when_the_visitor_asks_for_less(
    browser: Browser, origin: str, setting: str, duration: str
) -> None:
    for current in visit(browser, origin, reduced_motion=setting):
        shown = current.page.evaluate(
            "getComputedStyle(document.querySelector('.skip-link')).transitionDuration"
        )
        assert shown == duration


# --- the policy at work --------------------------------------------------------------------------


def test_the_policy_really_blocks_an_inline_script(browser: Browser, origin: str) -> None:
    """Not just present in the markup: the browser refuses the script and says so."""
    for current in visit(browser, origin):
        page = current.page
        page.evaluate(WATCH_VIOLATIONS)
        page.evaluate(
            "(() => { const s = document.createElement('script');"
            " s.textContent = 'window.__pwned = true';"
            " document.body.appendChild(s); })()"
        )
        assert page.evaluate("window.__pwned") is None
        assert page.evaluate("window.__violations")[0].startswith("script-src")


def test_the_policy_blocks_a_script_from_another_host(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.evaluate(WATCH_VIOLATIONS)
        page.evaluate(
            "(() => { const s = document.createElement('script');"
            " s.src = 'https://example.org/x.js'; document.body.appendChild(s); })()"
        )
        page.wait_for_function("window.__violations.length > 0")
        assert page.evaluate("window.__violations")[0].startswith("script-src")
