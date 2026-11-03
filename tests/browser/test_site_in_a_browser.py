"""The site in a real browser: accessibility (axe), the Content Security Policy at work, requests.

Needs a Chromium. In CI it is installed (`playwright install chromium`) and a missing browser is a
failure (UBI_LUDUS_REQUIRE_BROWSER=1). On a developer machine the tests use Chromium if it is
there, else Chrome or Edge, and skip when there is none.
"""

import functools
import http.server
import os
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from axe_playwright_python.sync_playwright import Axe  # type: ignore[import-untyped]
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

pytestmark = pytest.mark.browser

SITE = Path(__file__).resolve().parents[2] / "site"
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


class Visit:
    """One page load, with everything the browser reported while it happened."""

    def __init__(self, page: Page, origin: str) -> None:
        self.page = page
        self.origin = origin
        self.console: list[str] = []
        self.requests: list[str] = []
        self.failed: list[str] = []
        page.on("console", lambda m: self.console.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: self.console.append(f"pageerror: {e}"))
        page.on("request", lambda r: self.requests.append(r.url))
        page.on("requestfailed", lambda r: self.failed.append(r.url))

    def open(self) -> None:
        self.page.goto(self.origin + "/index.html")
        self.page.wait_for_selector("html[data-ready='true']")


def visit(
    browser: Browser,
    origin: str,
    scheme: str = "light",
    size: str = "desktop",
    reduced_motion: str = "no-preference",
) -> Iterator[Visit]:
    width, height = VIEWPORTS[size]
    context = browser.new_context(
        color_scheme=scheme,  # type: ignore[arg-type]
        reduced_motion=reduced_motion,  # type: ignore[arg-type]
        viewport={"width": width, "height": height},
    )
    try:
        current = Visit(context.new_page(), origin)
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
