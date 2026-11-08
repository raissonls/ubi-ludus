# ruff: noqa: E501 - the JavaScript in the strings below is easier to read in long lines
"""WCAG 2.2 AA beyond what axe finds (M5-01, FR-31).

axe checks a page's markup and text contrast; the tests of each feature run it in their own states.
This is the audit of what a person using the keyboard, a large text size, a high-contrast mode or a
screen reader meets, the same in every state and both themes:

* a **walk with the Tab key** through every stop: the focus ring is visible and has at least 3:1
  against what it touches (1.4.11), is not hidden behind anything (2.4.11), every target is at least
  24 px (2.5.8), and the focus never gets stuck (2.1.2);
* **text spacing** and **200% text** lose no content (1.4.12, 1.4.4) and the page does not scroll
  sideways at 320 px (1.4.10);
* **forced colours** (Windows high contrast) keep the page readable;
* the **structure** a screen reader navigates by: one h1, no skipped levels, the landmarks, unique
  ids, a name for every control, the language (1.3.1, 2.4.1, 2.4.2, 3.1.1, 4.1.2);
* **reduced motion** stops every endless animation (2.3.3, FR-31).

A real screen reader (NVDA, VoiceOver, TalkBack) is not run here: docs/audits/ has the checklist.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Page
from site_browser import DATA, STORAGE_KEY, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

GALLERY = "/gallery/cards.html"
MAX_STOPS = 400

DESCRIBE_FOCUSED = r"""
() => {
  const e = document.activeElement;
  if (!e || e === document.body) return null;
  const nums = (c) => c.match(/[\d.]+/g).map(Number);
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const solid = (el) => { let n = el; while (n) { const c = nums(getComputedStyle(n).backgroundColor); if (c.length < 4 || c[3] > 0.99) return c.slice(0, 3); n = n.parentElement; } return [255, 255, 255]; };
  const s = getComputedStyle(e);
  const r = e.getBoundingClientRect();
  const label = e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : '');
  const hasOutline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2;
  const hasShadow = !!(s.boxShadow && s.boxShadow !== 'none');
  const cx = Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1);
  const cy = Math.min(Math.max(r.top + r.height / 2, 0), innerHeight - 1);
  const top = document.elementFromPoint(cx, cy);
  // An inline link inside a sentence is exempt from the 24 px size (2.5.8).
  const inline = s.display === 'inline' && e.tagName === 'A';
  return {
    label, width: Math.round(r.width), height: Math.round(r.height), inline,
    ring: hasOutline || hasShadow,
    ringContrast: hasOutline ? +ratio(nums(s.outlineColor).slice(0, 3), solid(e.parentElement || e)).toFixed(2) : null,
    obscured: !!top && !(e === top || e.contains(top) || top.contains(e)),
    inViewport: r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth,
  };
}
"""

STRUCTURE = """
() => {
  const visible = (e) => e.offsetParent !== null || getComputedStyle(e).position === 'fixed';
  const levels = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible).map((h) => +h.tagName[1]);
  const ids = {};
  document.querySelectorAll('[id]').forEach((e) => { ids[e.id] = (ids[e.id] || 0) + 1; });
  const named = (e) => (e.getAttribute('aria-label') || e.innerText || e.value || '').trim()
    || (e.labels && [...e.labels].map((l) => l.innerText).join('').trim())
    || (e.getAttribute('aria-labelledby') || '').split(' ').map((i) => document.getElementById(i)?.innerText || '').join('').trim()
    || e.getAttribute('title');
  const controls = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, summary')]
    .filter((e) => visible(e) && !(e.closest('details:not([open])') && e.tagName !== 'SUMMARY'));
  return {
    levels,
    duplicates: Object.entries(ids).filter(([, n]) => n > 1).map(([id]) => id),
    unnamed: controls.filter((e) => !named(e)).map((e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '')),
    main: document.querySelectorAll('main, [role=main]').length,
    banner: document.querySelectorAll('header, [role=banner]').length,
    contentinfo: document.querySelectorAll('footer, [role=contentinfo]').length,
    lang: document.documentElement.lang,
    title: document.title,
  };
}
"""

SPACING_CSS = (
    "* { line-height: 1.5 !important; letter-spacing: 0.12em !important;"
    " word-spacing: 0.16em !important; } p { margin-bottom: 2em !important; }"
)

CLIPPED = """
() => {
  const bad = [];
  for (const e of document.querySelectorAll('body *')) {
    if (e.offsetParent === null) continue;
    const s = getComputedStyle(e);
    if (e.closest('.visually-hidden') || (s.clip && s.clip !== 'auto') || s.clipPath !== 'none') continue;
    if (e.closest('details:not([open])') && e.tagName !== 'SUMMARY') continue;
    const hidesOverflow = s.overflow !== 'visible' || s.overflowX !== 'visible' || s.overflowY !== 'visible';
    const spills = e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1;
    if (hidesOverflow && spills && !['auto', 'scroll'].includes(s.overflowY)) {
      bad.push(e.tagName.toLowerCase() + (e.id ? '#' + e.id : ''));
    }
  }
  return bad;
}
"""


def competitions(*none: str) -> dict[str, object]:
    document = json.loads(Path(DATA / "competitions.json").read_text(encoding="utf-8"))
    for competition in document["competitions"]:
        if competition["id"] in none:
            competition["coverage"] = "none"
    return document  # type: ignore[no-any-return]


CHOICES = {
    STORAGE_KEY: json.dumps(
        {
            "version": 1,
            "teams": ["palmeiras", "real-madrid"],
            "services": ["globoplay"],
            "onlyWatchable": True,
        }
    )
}

# Every state of the page worth walking: nothing chosen, everything open, and with choices made.
STATES: dict[str, dict[str, Any]] = {
    "first-visit": {"path": "/index.html"},
    "everything-open": {
        "path": "/index.html?view=week",
        "changed_data": {"competitions": competitions("amistosos-selecoes")},
        "open": ("#filters summary", "#uncovered-summary"),
    },
    "with-choices": {"path": "/index.html", "saved": CHOICES},
    "every-card-state": {"path": GALLERY},
}
MIN_STOPS = {"first-visit": 8, "everything-open": 8, "with-choices": 8, "every-card-state": 1}
SIZES = list(VIEWPORTS)
SCHEMES = ["light", "dark"]


def state_call(name: str, **extra: Any) -> dict[str, Any]:
    options = {k: v for k, v in STATES[name].items() if k != "open"}
    return {**options, **extra}


def open_panels(page: Page, name: str) -> None:
    for selector in STATES[name].get("open", ()):
        page.locator(selector).click()


def walk(page: Page) -> list[dict[str, Any]]:
    """Press Tab through the whole page. Returns what each stop looked like."""
    page.evaluate("document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0)")
    stops: list[dict[str, Any]] = []
    for _ in range(MAX_STOPS):
        page.keyboard.press("Tab")
        settle(page)  # a skip link slides in: measure it where it comes to rest
        found = page.evaluate(DESCRIBE_FOCUSED)
        if found is None:
            return stops  # the focus left the page: it was not trapped
        if stops and found["label"] == stops[0]["label"]:
            return stops  # all the way round
        stops.append(found)
    pytest.fail(f"the focus was still on the page after {MAX_STOPS} Tab presses: a keyboard trap?")


def apply_css(page: Page, css: str) -> None:
    """Add a rule to the page. The page's own CSP forbids an inline <style>, so use a constructed
    style sheet (which is how the page's own limits are kept honest, not worked around)."""
    page.evaluate(
        "(css) => { const sheet = new CSSStyleSheet(); sheet.replaceSync(css);"
        " document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]; }",
        css,
    )


def settle(page: Page) -> None:
    """Wait for the skip link's and the cards' short transitions and entrances to end."""
    page.evaluate(
        "Promise.allSettled(document.getAnimations()"
        ".filter((a) => a.effect.getComputedTiming().iterations !== Infinity)"
        ".map((a) => a.finished))"
    )


# --- the keyboard ---------------------------------------------------------------------------------


@pytest.mark.parametrize("state", list(STATES))
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("scheme", SCHEMES)
def test_every_tab_stop_has_a_clear_unhidden_focus_ring_and_a_big_enough_target(
    browser: Browser, origin: str, scheme: str, size: str, state: str
) -> None:
    for current in visit(browser, origin, scheme, size, **state_call(state)):
        page = current.page
        settle(page)
        open_panels(page, state)
        stops = walk(page)
        assert len(stops) >= MIN_STOPS[state], f"only {len(stops)} tab stops"
        problems: list[str] = []
        for stop in stops:
            name = stop["label"]
            if not stop["ring"]:
                problems.append(f"{name}: no visible focus ring")
            elif stop["ringContrast"] is not None and stop["ringContrast"] < 3:
                problems.append(f"{name}: focus ring contrast {stop['ringContrast']}:1")
            if stop["obscured"] or not stop["inViewport"]:
                problems.append(f"{name}: focus hidden behind something or off screen")
            if (stop["width"] < 24 or stop["height"] < 24) and not stop["inline"]:
                problems.append(f"{name}: target {stop['width']}x{stop['height']} px")
        assert problems == []


def test_shift_tab_goes_back_through_the_same_stops(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, **state_call("with-choices")):
        page = current.page
        settle(page)
        page.evaluate(
            "document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0)"
        )
        forward: list[str] = []
        for _ in range(12):
            page.keyboard.press("Tab")
            settle(page)
            forward.append(page.evaluate(DESCRIBE_FOCUSED)["label"])
        back: list[str] = []
        for _ in range(len(forward) - 1):
            page.keyboard.press("Shift+Tab")
            settle(page)
            back.append(page.evaluate(DESCRIBE_FOCUSED)["label"])
        assert back == list(reversed(forward[:-1]))


# --- sizes of text and space ----------------------------------------------------------------------


@pytest.mark.parametrize("state", ["first-visit", "everything-open", "every-card-state"])
@pytest.mark.parametrize("size", SIZES)
def test_wider_text_spacing_loses_no_content_and_adds_no_sideways_scroll(
    browser: Browser, origin: str, size: str, state: str
) -> None:
    for current in visit(browser, origin, size=size, **state_call(state)):
        page = current.page
        settle(page)
        open_panels(page, state)
        apply_css(page, SPACING_CSS)
        assert page.evaluate(CLIPPED) == []
        widths = page.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        assert widths[0] <= widths[1], widths


@pytest.mark.parametrize("state", ["first-visit", "everything-open", "every-card-state"])
@pytest.mark.parametrize("size", SIZES)
def test_text_at_200_percent_still_fits_without_sideways_scroll_or_clipping(
    browser: Browser, origin: str, size: str, state: str
) -> None:
    for current in visit(browser, origin, size=size, **state_call(state)):
        page = current.page
        settle(page)
        open_panels(page, state)
        apply_css(page, "html { font-size: 200% !important; }")
        assert page.evaluate(CLIPPED) == []
        widths = page.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        assert widths[0] <= widths[1], widths


# --- high contrast and motion ---------------------------------------------------------------------


@pytest.mark.parametrize("state", ["first-visit", "everything-open", "every-card-state"])
def test_in_forced_colours_axe_finds_nothing_and_the_focus_ring_survives(
    browser: Browser, origin: str, state: str
) -> None:
    for current in visit(
        browser, origin, size="mobile", forced_colors="active", **state_call(state)
    ):
        page = current.page
        settle(page)
        open_panels(page, state)
        assert axe_violations(page) == []
        for stop in walk(page):
            assert stop["ring"], f"{stop['label']}: no focus ring in forced colours"


@pytest.mark.parametrize("scheme", SCHEMES)
def test_with_reduced_motion_nothing_keeps_moving(
    browser: Browser, origin: str, scheme: str
) -> None:
    for current in visit(
        browser, origin, scheme, reduced_motion="reduce", **state_call("every-card-state")
    ):
        page = current.page
        settle(page)
        running = page.evaluate(
            "document.getAnimations().filter((a) => a.playState === 'running'"
            " && (a.effect.getComputedTiming().iterations === Infinity"
            " || a.effect.getComputedTiming().endTime > 100)).length"
        )
        assert running == 0
        assert page.locator(".live-dot").count() > 0  # the live card is there to be still


# --- what a screen reader navigates by ------------------------------------------------------------


@pytest.mark.parametrize("state", list(STATES))
@pytest.mark.parametrize("size", ["desktop", "mobile"])
def test_the_page_has_the_structure_a_screen_reader_navigates_by(
    browser: Browser, origin: str, size: str, state: str
) -> None:
    for current in visit(browser, origin, size=size, **state_call(state)):
        page = current.page
        settle(page)
        open_panels(page, state)
        facts = page.evaluate(STRUCTURE)
        levels = facts["levels"]
        assert levels.count(1) == 1, f"h1 count {levels.count(1)}"
        for before, after in zip(levels, levels[1:], strict=False):
            assert after <= before + 1, f"a heading jumps from h{before} to h{after}"
        assert facts["duplicates"] == []
        assert facts["unnamed"] == []
        assert (facts["main"], facts["banner"], facts["contentinfo"]) == (1, 1, 1) or state == (
            "every-card-state"
        )
        assert facts["lang"] == "pt-BR" and facts["title"].strip()


def said(page: Page) -> str:
    """What the picker's live region says. It ends in a non-breaking space that is swapped in and
    out so that the same message twice in a row is still read again."""
    return page.locator("#picker-announcer").inner_text().replace(" ", " ").strip()


def test_choosing_a_team_and_removing_it_is_announced_and_keeps_the_focus(
    browser: Browser, origin: str
) -> None:
    """Onboarding with the keyboard alone: what a screen reader is told at each step (FR-20)."""
    for current in visit(browser, origin):
        page = current.page
        search = page.locator("#team-search")
        search.focus()
        assert search.get_attribute("role") == "combobox"
        page.keyboard.type("palm")
        assert search.get_attribute("aria-expanded") == "true"
        page.keyboard.press("ArrowDown")
        assert search.get_attribute("aria-activedescendant")
        page.keyboard.press("Enter")
        assert said(page) == "Palmeiras adicionado. 1 time escolhido."
        assert page.evaluate("document.activeElement.id") == "team-search"  # not lost
        page.get_by_role("button", name="Remover Palmeiras").focus()
        page.keyboard.press("Enter")
        assert said(page) == "Palmeiras removido. Nenhum time escolhido."
        assert page.evaluate("document.activeElement.id") == "team-search"
