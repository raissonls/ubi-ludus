"""The layout across widths (docs/browser-support.md, M6 Q-03).

The other layout tests look at three windows: 1280, 375 and 320 px. A tablet, a big phone or a
narrow desktop window falls between them, where a sticky header, a strip of teams, rails of posters
and a side panel can collide. This sweeps seven widths over five states and checks two things:

- nothing makes the page scroll sideways, and when something does, the message says which element;
- two things that stay in place on the screen (sticky or fixed) never cover each other.

Screenshots are not compared. When UBI_LUDUS_SCREENSHOTS names a folder, one picture of every
width and state is saved there (the "Layout sweep" workflow does this on a manual run and keeps the
folder), for a quick look by a person. Fonts differ between machines, so pixels are not a test.
"""

import json
import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page
from site_browser import STORAGE_KEY, Visit, open_details, open_settings, visit

pytestmark = pytest.mark.browser

WIDTHS = (320, 360, 390, 430, 768, 1024, 1440)
HEIGHT = "mobile"  # the height of a phone-sized window (812 px); only the width is swept
SCREENSHOTS = os.environ.get("UBI_LUDUS_SCREENSHOTS")


def saved(*teams: str) -> dict[str, str]:
    return {STORAGE_KEY: json.dumps({"version": 1, "teams": list(teams), "services": []})}


# Each state opens the page in one way and leaves it ready to look at.
def empty(browser: Browser, origin: str, width: int) -> Iterator[Visit]:
    return visit(browser, origin, size=HEIGHT, width=width)


def with_teams(browser: Browser, origin: str, width: int) -> Iterator[Visit]:
    return visit(
        browser, origin, size=HEIGHT, width=width, saved=saved("palmeiras", "real-madrid", "brasil")
    )


def settings_open(browser: Browser, origin: str, width: int) -> Iterator[Visit]:
    teams = saved("palmeiras", "real-madrid", "brasil")
    return visit(browser, origin, size=HEIGHT, width=width, settings=True, saved=teams)


def sheet_open(browser: Browser, origin: str, width: int) -> Iterator[Visit]:
    for current in visit(browser, origin, size=HEIGHT, width=width, saved=saved("palmeiras")):
        open_details(current.page, "Palmeiras")
        current.page.wait_for_function("document.querySelector('#match-sheet').open")
        yield current


def first_run(browser: Browser, origin: str, width: int) -> Iterator[Visit]:
    return visit(browser, origin, size=HEIGHT, width=width, onboarding=True)


def adding_teams(browser: Browser, origin: str, width: int) -> Iterator[Visit]:
    """The first-run choice reached from the settings, with a team already ticked."""
    for current in visit(browser, origin, size=HEIGHT, width=width):
        add_teams_open(current.page)
        yield current


def add_teams_open(page: Page) -> None:
    open_settings(page)
    page.click("#reopen-onboarding")
    page.locator("#onboarding").wait_for(state="visible")
    page.locator("#ob-search").fill("palm")
    page.locator("#onboarding .ob-row--result[aria-pressed='false']").first.click()


STATES: dict[str, Callable[[Browser, str, int], Iterator[Visit]]] = {
    "empty": empty,
    "with-teams": with_teams,
    "settings-open": settings_open,
    "match-sheet-open": sheet_open,
    "first-run": first_run,
    "choosing-teams": adding_teams,
}

# The elements that overflow the window, outside anything that scrolls by itself (a rail of posters
# scrolls sideways on purpose; its posters are cut by it, not by the page).
OVERFLOWING = """
(() => {
  const limit = document.documentElement.clientWidth;
  const scrolls = (node) => {
    for (let up = node.parentElement; up; up = up.parentElement) {
      if (up === document.documentElement) break;
      const x = getComputedStyle(up).overflowX;
      if (x === 'auto' || x === 'scroll' || x === 'hidden' || x === 'clip') return true;
    }
    return false;
  };
  const found = [];
  for (const node of document.body.querySelectorAll('*')) {
    const style = getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    const box = node.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) continue;
    if (box.width <= 1 && box.height <= 1) continue;  // the visually hidden text
    if (box.right > limit + 1 || box.left < -1) {
      if (scrolls(node)) continue;
      const id = node.id ? '#' + node.id : '';
      const cls = node.classList.length ? '.' + [...node.classList].join('.') : '';
      found.push(node.tagName.toLowerCase() + id + cls + ' [' + Math.round(box.left) + ' to '
        + Math.round(box.right) + ' of ' + limit + ']');
    }
  }
  return {
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: limit,
    offenders: found.slice(0, 8),
  };
})()
"""

# Elements that stay in place while the page scrolls, and the pairs of them that cover each other.
# While a modal is open (the settings panel, the sheet, the first-run flow) it is meant to cover the
# page behind it, so only what is inside it counts.
PINNED_OVERLAPS = """
(() => {
  const modal = document.querySelector('dialog[open], #onboarding:not([hidden])');
  const everything = (root) => [root, ...root.querySelectorAll('*')];
  const pinned = [];
  for (const node of everything(modal ? modal : document.body)) {
    const style = getComputedStyle(node);
    if (style.position !== 'sticky' && style.position !== 'fixed') continue;
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    const box = node.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) continue;
    pinned.push({ node, box });
  }
  const name = (node) => node.tagName.toLowerCase() + (node.id ? '#' + node.id : '')
    + (node.classList.length ? '.' + [...node.classList].join('.') : '');
  const overlaps = [];
  for (let i = 0; i < pinned.length; i++) {
    for (let j = i + 1; j < pinned.length; j++) {
      const a = pinned[i], b = pinned[j];
      if (a.node.contains(b.node) || b.node.contains(a.node)) continue;  // one holds the other
      const across = Math.min(a.box.right, b.box.right) - Math.max(a.box.left, b.box.left);
      const down = Math.min(a.box.bottom, b.box.bottom) - Math.max(a.box.top, b.box.top);
      if (across > 1 && down > 1) overlaps.push(name(a.node) + ' covers ' + name(b.node));
    }
  }
  return { pinned: pinned.map((p) => name(p.node)), overlaps };
})()
"""


def settle(page: Page) -> None:
    """Wait for the entrance animations (the panel slides in, the first-run screen fades in): a
    box half way across the window is not what a visitor is left with."""
    page.evaluate(
        "Promise.allSettled(document.getAnimations()"
        ".filter((a) => a.effect.getComputedTiming().iterations !== Infinity)"
        ".map((a) => a.finished))"
    )


def save_picture(page: Page, state: str, width: int) -> None:
    if SCREENSHOTS:
        folder = Path(SCREENSHOTS)
        folder.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(folder / f"{state}-{width}.png"))


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("state", list(STATES))
def test_nothing_makes_the_page_scroll_sideways(
    browser: Browser, origin: str, state: str, width: int
) -> None:
    for current in STATES[state](browser, origin, width):
        page = current.page
        settle(page)
        save_picture(page, state, width)
        found = page.evaluate(OVERFLOWING)
        assert found["scrollWidth"] <= found["clientWidth"], (
            f"{state} at {width} px scrolls sideways ({found['scrollWidth']} px of "
            f"{found['clientWidth']}); beyond the edge: {found['offenders']}"
        )
        assert found["offenders"] == [], f"{state} at {width} px: {found['offenders']}"


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("state", list(STATES))
def test_things_that_stay_in_place_never_cover_each_other(
    browser: Browser, origin: str, state: str, width: int
) -> None:
    for current in STATES[state](browser, origin, width):
        settle(current.page)
        found = current.page.evaluate(PINNED_OVERLAPS)
        assert found["overlaps"] == [], (
            f"{state} at {width} px: {found['overlaps']} (in place: {found['pinned']})"
        )


def test_the_sweep_would_catch_a_page_that_is_too_wide(browser: Browser, origin: str) -> None:
    """The check itself works: a box forced wider than the window is found and named."""
    for current in empty(browser, origin, 360):
        page = current.page
        page.evaluate(
            "(() => { const b = document.createElement('div'); b.id = 'too-wide';"
            " b.style.cssText = 'width:900px;height:10px'; document.body.append(b); })()"
        )
        found = page.evaluate(OVERFLOWING)
        assert found["scrollWidth"] > found["clientWidth"]
        assert any("#too-wide" in line for line in found["offenders"])


def test_the_sweep_would_catch_two_pinned_things_on_top_of_each_other(
    browser: Browser, origin: str
) -> None:
    for current in empty(browser, origin, 390):
        page = current.page
        page.evaluate(
            "(() => { const b = document.createElement('div'); b.id = 'stuck';"
            " b.style.cssText = 'position:fixed;top:0;left:0;height:60px;width:100%';"
            " document.body.prepend(b); })()"
        )
        found = page.evaluate(PINNED_OVERLAPS)
        assert any("#stuck" in line for line in found["overlaps"])
