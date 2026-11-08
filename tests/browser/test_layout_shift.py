"""The page must not jump while it loads (M5-02, NFR performance: Lighthouse CLS under 0.1).

Before this was fixed the live site scored 1.08. The page is at least a screen tall, so at first
paint the footer sat at the bottom of the screen; when the matches arrived the page grew by
thousands of pixels and the footer jumped far below it. The header and the headings also grew as
their text (filled in from the strings file) arrived. What is filled in later now keeps its room
from the first paint (site/css/base.css).

This measures what the browser itself reports as layout shifts (the same numbers Lighthouse reads),
on a page that loads at once from a local server: the order of events is the same as on a slow
connection, only faster, and it still jumped by 1.08.
"""

import json
from typing import Any

import pytest
from playwright.sync_api import Browser, Page
from site_browser import STORAGE_KEY, VIEWPORTS, visit

pytestmark = pytest.mark.browser

# Lighthouse calls anything under 0.1 good. The page measures a tenth of that, so this has room.
LIMIT = 0.1

RECORD = """
window.__shifts = [];
new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.hadRecentInput) continue;
    const name = (node) => node && node.tagName
      ? node.tagName.toLowerCase() + (node.id ? '#' + node.id : '')
      : '?';
    window.__shifts.push({
      value: entry.value,
      moved: entry.sources.map((source) => name(source.node)),
    });
  }
}).observe({ type: 'layout-shift', buffered: true });
"""

SAVED = {
    STORAGE_KEY: json.dumps(
        {"version": 1, "teams": ["palmeiras"], "services": ["globoplay"], "onlyWatchable": False}
    )
}


def record(page: Page) -> None:
    page.add_init_script(RECORD)


def total_and_movers(page: Page) -> tuple[float, list[str]]:
    # Let any late shift happen (animations, the freshness line) before reading.
    page.evaluate("new Promise((resolve) => setTimeout(resolve, 600))")
    shifts: list[dict[str, Any]] = page.evaluate("window.__shifts")
    return sum(s["value"] for s in shifts), sorted({m for s in shifts for m in s["moved"]})


# "2026-11-02" is the day of the data: fresh. A week later the freshness note is a warning.
FRESH = "2026-11-02T12:00:00Z"
OLD = "2026-11-12T12:00:00Z"


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize(
    ("name", "options"),
    [
        ("fresh data", {"now": FRESH}),
        ("old data, so a warning in the header", {"now": OLD}),
        ("the week list", {"now": FRESH, "path": "/index.html?view=week"}),
        ("a team and a service chosen", {"now": FRESH, "saved": SAVED}),
    ],
)
def test_the_page_does_not_jump_while_it_loads(
    browser: Browser, origin: str, scheme: str, size: str, name: str, options: dict[str, Any]
) -> None:
    for current in visit(browser, origin, scheme, size, before_open=record, **options):
        total, movers = total_and_movers(current.page)
        assert total < LIMIT, f"{name}: layout shift {total:.3f}, what moved: {movers}"


def test_the_footer_starts_below_the_first_screen_so_it_never_has_to_jump(
    browser: Browser, origin: str
) -> None:
    """The cause of 1.08: a footer in view at first paint that the loaded page then pushed away."""
    for current in visit(browser, origin, size="mobile", wait_ready=False):
        page = current.page
        page.wait_for_selector("footer", state="attached")
        top = page.evaluate("document.querySelector('footer').getBoundingClientRect().top")
        assert top >= VIEWPORTS["mobile"][1], f"the footer starts at {top:.0f} px, in view"


def test_what_is_filled_in_later_has_its_room_before_it_arrives(
    browser: Browser, origin: str
) -> None:
    """The name, the title, the section title and the freshness line, before any text exists."""
    for current in visit(browser, origin, size="mobile", wait_ready=False):
        page = current.page
        page.route("**/i18n/*.json", lambda route: route.abort())  # the strings never arrive
        page.reload()
        page.wait_for_selector("footer", state="attached")
        heights = page.evaluate(
            """() => Object.fromEntries(
              ['.brand', '#freshness', 'main h1', '#matches-title'].map((selector) =>
                [selector, document.querySelector(selector).getBoundingClientRect().height]))"""
        )
        assert all(height >= 20 for height in heights.values()), heights
