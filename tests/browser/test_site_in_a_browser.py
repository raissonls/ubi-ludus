"""The site in a real browser: accessibility (axe), the Content Security Policy at work, requests,
the data and the visitor's choices. The browser and the server are in conftest.py."""

import json
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Browser
from site_browser import (
    CHOICES,
    SECRET_SERVICE,
    SECRET_TEAM,
    STORAGE_KEY,
    VIEWPORTS,
    WATCH_VIOLATIONS,
    axe_violations,
    visit,
)

pytestmark = pytest.mark.browser

# --- accessibility (axe) --------------------------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_no_wcag_2_2_aa_violation(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(browser, origin, scheme, size):
        assert axe_violations(current.page) == []


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


def test_the_published_files_are_loaded_and_counted(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        assert current.page.locator("#matches-content").is_visible()
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
        assert current.page.locator("#matches-content").is_visible()
        current.page.click("#reset-data")
        assert "apagadas" in current.page.locator("#reset-result").inner_text()


def test_when_the_data_cannot_be_loaded_the_page_says_so_and_stays_accessible(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, broken={"matches": 500}):
        message = current.page.locator("#state-panel").inner_text()
        assert message.startswith("Não foi possível carregar os jogos")
        assert any("matches.json" in line for line in current.console)
        assert axe_violations(current.page) == []


def test_a_data_file_in_a_newer_format_is_refused_the_same_way(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, newer_format="teams"):
        assert current.page.locator("#state-panel").inner_text().startswith("Esta página ficou")
        assert any("this site reads 1.x" in line for line in current.console)


# --- themes and motion ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scheme", "background"), [("light", "rgb(247, 243, 250)"), ("dark", "rgb(20, 4, 28)")]
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
