"""The next match of the followed teams, as one big card (and shirts in the match cards).

It is the answer to "when does my team play and where do I watch it?" at the top of the page:
both shirts in the team colours, when, and the broadcasters. It uses the match card's own words
and styles for the broadcasters, the state and the access line.
"""

import json
from typing import Any

import pytest
from playwright.sync_api import Browser, Page
from site_browser import STORAGE_KEY, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

HERO = "#next-match .hero"


def saved(teams: list[str], services: list[str] | None = None) -> dict[str, str]:
    record = {"version": 1, "teams": teams, "services": services or []}
    return {STORAGE_KEY: json.dumps(record)}


def hero_title(page: Page) -> str:
    return page.locator(f"{HERO} .hero__title").inner_text()


def hero_text(page: Page) -> str:
    return page.locator(HERO).inner_text()


def test_a_visitor_who_follows_a_team_sees_its_next_match_first(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        section = page.locator("#next-match")
        assert section.is_visible()
        assert "Seu próximo jogo" in (section.text_content() or "")  # shown in capitals
        assert page.locator(f"{HERO} .hero__title").inner_text() == "Palmeiras x Flamengo"
        assert page.locator(f"{HERO} .hero__shirts .shirt").count() == 2
        assert "Onde assistir" in hero_text(page)
        # It sits above the list of matches, below the three buttons.
        order = page.evaluate(
            "[...document.querySelectorAll('#view-switch, #next-match, #matches-list')]"
            ".map(e => e.id)"
        )
        assert order == ["view-switch", "next-match", "matches-list"]


def test_a_visitor_who_follows_nobody_has_no_next_match(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        assert not current.page.locator("#next-match").is_visible()


def test_a_team_with_no_match_to_come_has_no_next_match(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["time-que-nao-existe"])):
        assert not current.page.locator("#next-match").is_visible()


def test_it_follows_the_list_the_visitor_is_looking_at(browser: Browser, origin: str) -> None:
    """Never a match from another day: on "Hoje" it is today's, on the week the week's."""
    # The test data's clock is 2 November; Palmeiras play Flamengo on the 3rd.
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        switch = page.locator("#view-switch [data-view]")
        switch.get_by_text("Hoje", exact=True).click()
        assert not page.locator("#next-match").is_visible()  # nothing of theirs today
        switch.get_by_text("Esta semana", exact=True).click()
        assert hero_title(page) == "Palmeiras x Flamengo"
        switch.get_by_text("Meus times", exact=True).click()
        assert hero_title(page) == "Palmeiras x Flamengo"


def test_on_the_day_their_team_plays_today_it_is_that_match(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"]), now="2026-11-03T12:00:00Z"):
        page = current.page
        page.locator("#view-switch [data-view]").get_by_text("Hoje", exact=True).click()
        assert hero_title(page) == "Palmeiras x Flamengo"


def test_it_follows_the_choice_of_teams(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        page.click("#chosen-teams .chip")  # take Palmeiras out
        assert not page.locator("#next-match").is_visible()
        page.click("#team-search")
        page.keyboard.type("real")
        page.keyboard.press("Enter")
        assert page.locator(f"{HERO} .hero__title").inner_text() == "Real Madrid x Barça"


def test_it_says_whether_the_visitor_can_watch_it(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"], ["globoplay"])):
        page = current.page
        assert page.locator(f"{HERO} .match-card__access").count() == 1
        assert page.locator(f"{HERO} .badge").count() >= 1


def test_the_shirts_are_in_the_colours_of_the_teams_and_hold_no_crest(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        fills = page.locator(f"{HERO} .shirt__body").evaluate_all(
            "e => e.map(x => x.getAttribute('fill'))"
        )
        assert fills == ["#006437", "#C52613"]  # Palmeiras and Flamengo
        assert page.locator(f"{HERO} img, {HERO} image, {HERO} canvas").count() == 0
        assert page.locator(f"{HERO} .shirt").first.get_attribute("aria-hidden") == "true"


def test_the_match_cards_show_shirts_in_place_of_colour_dots(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        card = page.locator("#matches-list .match-card").first
        assert card.locator(".match-card__teams .shirt").count() == 2
        assert card.locator(".swatch").count() == 0
        assert (
            card.locator(".match-card__teams .shirt").first.get_attribute("aria-hidden") == "true"
        )


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", list(VIEWPORTS))
def test_the_page_with_its_next_match_has_no_accessibility_violation(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    options: dict[str, Any] = {
        "saved": saved(["palmeiras"], ["globoplay"]),
        "reduced_motion": "reduce",
    }
    for current in visit(browser, origin, scheme=scheme, size=size, **options):
        assert current.page.locator(HERO).is_visible()
        assert axe_violations(current.page) == []


def test_it_moves_only_when_motion_is_allowed(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"]), reduced_motion="reduce"):
        name = current.page.evaluate(
            f"getComputedStyle(document.querySelector('{HERO}')).animationName"
        )
        assert name == "none"
    for current in visit(
        browser, origin, saved=saved(["palmeiras"]), reduced_motion="no-preference"
    ):
        page = current.page
        name = page.evaluate(f"getComputedStyle(document.querySelector('{HERO}')).animationName")
        assert name != "none"
        properties = page.evaluate(
            "[...document.getAnimations()].flatMap(a => a.effect.getKeyframes()"
            ".flatMap(k => Object.keys(k)))"
        )
        allowed = {
            "offset",
            "easing",
            "composite",
            "computedOffset",
            "opacity",
            "transform",
            "boxShadow",
        }
        assert set(properties) <= allowed, set(properties) - allowed
