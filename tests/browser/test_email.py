"""The morning e-mail drawn in a browser (FR-43): no sideways scroll, no accessibility finding.

This stands in for the clients only as far as a browser can: layout at phone widths, light and dark
colours, and axe (contrast included). Gmail and Apple Mail are checked by hand before launch; the
preview command writes the files for that (``python -m ubi_ludus.email.render``).
"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Page
from site_browser import VIEWPORTS, axe_violations

from ubi_ludus.email.briefing import BroadcasterLine, Documents, build_briefing, load_documents
from ubi_ludus.email.render import render_briefing
from ubi_ludus.pipeline.owner import OwnerConfig

pytestmark = pytest.mark.browser

DATA = Path(__file__).resolve().parents[1] / "fixtures" / "site" / "data"
NOW = datetime(2026, 11, 3, 11, 0, tzinfo=UTC)
OWNER = OwnerConfig(
    teams=("palmeiras",),
    services=("globoplay",),
    notable_competitions=("uefa-champions-league",),
    preferred_broadcasters=(),
    preferred_kinds=(),
)


def documents() -> Documents:
    """The fixture files plus a Champions League match the same day, so both sections show."""
    loaded = load_documents(DATA)
    extra = {**next(m for m in loaded.matches if m["id"] == "fx-3"), "id": "fx-extra"}
    extra["kickoff_utc"] = "2026-11-03T20:00:00Z"
    extra["broadcasts"] = [{"broadcaster_id": "globo", "confidence": "confirmed", "source": "x"}]
    return replace(loaded, matches=[*loaded.matches, extra])


def full_email() -> str:
    briefing = build_briefing(documents(), OWNER, NOW)
    assert briefing.mine and briefing.notable
    return render_briefing(briefing, site_url="https://example.org/ubi-ludus/").html


def page_for(browser: Browser, html: str, scheme: str, size: str) -> Any:
    width, height = VIEWPORTS[size]
    context = browser.new_context(
        viewport={"width": width, "height": height},
        color_scheme=scheme,  # type: ignore[arg-type]
    )
    page: Page = context.new_page()
    page.set_content(html)
    return context, page


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_in_the_email(browser: Browser, scheme: str, size: str) -> None:
    context, page = page_for(browser, full_email(), scheme, size)
    try:
        assert axe_violations(page) == []
    finally:
        context.close()


@pytest.mark.parametrize("size", list(VIEWPORTS))
def test_the_email_never_scrolls_sideways(browser: Browser, size: str) -> None:
    context, page = page_for(browser, full_email(), "light", size)
    try:
        widths = page.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        assert widths[0] <= widths[1], widths
    finally:
        context.close()


def test_long_names_wrap_instead_of_pushing_the_page_wide(browser: Browser) -> None:
    briefing = build_briefing(documents(), OWNER, NOW)
    long_word = "Supercalifragilisticoespialidoso" * 3
    first = briefing.mine[0]
    wide = first.__class__(
        **{
            **first.__dict__,
            "home": long_word,
            "broadcasters": (BroadcasterLine(long_word, "confirmed", True),),
        }
    )
    changed = briefing.__class__(**{**briefing.__dict__, "mine": (wide,)})
    context, page = page_for(browser, render_briefing(changed).html, "light", "narrow")
    try:
        widths = page.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        assert widths[0] <= widths[1], widths
    finally:
        context.close()


def test_the_dark_scheme_changes_the_colours(browser: Browser) -> None:
    colours = {}
    for scheme in ("light", "dark"):
        context, page = page_for(browser, full_email(), scheme, "mobile")
        try:
            colours[scheme] = page.evaluate(
                "[getComputedStyle(document.body).backgroundColor,"
                " getComputedStyle(document.querySelector('h1')).color]"
            )
        finally:
            context.close()
    assert colours["light"] != colours["dark"]
    assert colours["light"][0] == "rgb(242, 244, 247)"


def test_nothing_is_requested_when_the_email_is_opened(browser: Browser) -> None:
    context, page = page_for(browser, full_email(), "light", "desktop")
    requests: list[str] = []
    try:
        page.on("request", lambda request: requests.append(request.url))
        page.set_content(full_email())
        assert [r for r in requests if not r.startswith(("data:", "about:"))] == []
    finally:
        context.close()
