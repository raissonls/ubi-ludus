"""The lists of the home page (FR-23): my teams, today and this week, followed teams first.

The fixtures' clock is Monday 2 November 2026, 09:00 in Brazil. Their matches: Palmeiras x
Flamengo on the 3rd, Real Madrid x Barça on the 4th, Chelsea x Atleti on the 5th,
São Paulo x Atlético-MG on the 6th, Brasil on the 8th, and one finished on 30 October.
"""

import json

import pytest
from playwright.sync_api import Browser, Page
from site_browser import STORAGE_KEY, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

SEARCH = "#team-search"
WEEK = [
    "Palmeiras x Flamengo",
    "Real Madrid x Barça",
    "Chelsea x Atleti",
    "São Paulo x Atlético-MG",
    "Brasil x A definir",
]


def following(*teams: str) -> dict[str, str]:
    return {STORAGE_KEY: json.dumps({"version": 1, "teams": list(teams), "services": []})}


def pressed(page: Page) -> list[str]:
    return page.locator("#view-switch [aria-pressed='true']").all_inner_texts()


def listed(page: Page) -> list[str]:
    return page.locator("#matches-list .match-card__teams").all_inner_texts()


def choose(page: Page, name: str) -> None:
    page.get_by_role("button", name=name, exact=True).click()


# --- which list a visitor sees first -------------------------------------------------------------


def test_a_new_visitor_starts_on_today_and_is_told_when_there_is_nothing(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert pressed(page) == ["Hoje"]
        assert listed(page) == []
        assert page.locator("#matches-empty").inner_text() == "Nenhum jogo hoje."


def test_a_visitor_who_follows_teams_starts_on_their_teams(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=following("palmeiras")):
        page = current.page
        assert pressed(page) == ["Meus times"]
        assert listed(page) == ["Palmeiras x Flamengo"]


def test_my_teams_without_teams_points_to_the_picker(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        choose(current.page, "Meus times")
        assert current.page.locator("#matches-empty").inner_text().startswith("Escolha ao menos")


def test_choosing_the_first_team_moves_to_its_matches_unless_a_list_was_picked(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")
        assert pressed(page) == ["Meus times"]
        assert listed(page) == ["Palmeiras x Flamengo"]
    for current in visit(browser, origin):
        page = current.page
        choose(page, "Esta semana")
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")
        assert pressed(page) == ["Esta semana"]  # the visitor's own choice stays
        assert listed(page)[0] == "Palmeiras x Flamengo"


# --- the lists -----------------------------------------------------------------------------------


def test_this_week_lists_the_next_seven_days_soonest_first(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        choose(current.page, "Esta semana")
        assert listed(current.page) == WEEK  # not the match of 30 October


def test_today_lists_the_matches_of_the_day_in_brazil(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.clock.set_fixed_time("2026-11-03T12:00:00Z")  # the morning of the 3rd in Brazil
        choose(page, "Hoje")
        assert listed(page) == ["Palmeiras x Flamengo"]
        assert not page.locator("#matches-empty").is_visible()


def test_the_day_changes_at_midnight_in_brazil_not_in_utc(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        # 00:00 UTC on the 4th is 21:00 on the 3rd in Brazil: still the day of Palmeiras' match.
        page.clock.set_fixed_time("2026-11-04T00:00:00Z")
        choose(page, "Hoje")
        assert listed(page) == ["Palmeiras x Flamengo"]


# --- followed teams first ------------------------------------------------------------------------


def test_followed_teams_come_before_the_other_matches_with_the_groups_named(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=following("sao-paulo")):
        page = current.page
        choose(page, "Esta semana")
        assert listed(page) == [
            "São Paulo x Atlético-MG",
            "Palmeiras x Flamengo",
            "Real Madrid x Barça",
            "Chelsea x Atleti",
            "Brasil x A definir",
        ]
        assert page.locator(".matches-group__title").all_inner_texts() == [
            "Jogos dos seus times",
            "Outros jogos",
        ]
        followed = page.locator(".match-card[data-followed='true'] .match-card__teams")
        assert followed.all_inner_texts() == ["São Paulo x Atlético-MG"]


def test_without_followed_matches_there_are_no_group_titles(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        choose(current.page, "Esta semana")
        assert current.page.locator(".matches-group__title").count() == 0


# --- the buttons ---------------------------------------------------------------------------------


def test_the_lists_switch_from_the_keyboard_and_say_which_is_chosen(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        week = page.get_by_role("button", name="Esta semana", exact=True)
        week.focus()
        page.keyboard.press("Enter")
        assert pressed(page) == ["Esta semana"]
        assert page.locator("#matches-status").inner_text() == "5 jogos em “Esta semana”."
        page.get_by_role("button", name="Hoje", exact=True).focus()
        page.keyboard.press("Space")
        assert pressed(page) == ["Hoje"]
        assert page.locator("#matches-status").inner_text() == "0 jogo em “Hoje”."


def test_the_chosen_list_is_marked_by_more_than_colour(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        weights = page.locator("#view-switch button").evaluate_all(
            "b => b.map(x => getComputedStyle(x).fontWeight)"
        )
        assert sorted(weights) == ["400", "400", "700"]


# --- the next match is in view on a phone --------------------------------------------------------


def test_the_next_match_of_my_teams_is_on_screen_without_scrolling_on_a_phone(
    browser: Browser, origin: str
) -> None:
    height = VIEWPORTS["mobile"][1]
    for current in visit(browser, origin, size="mobile", saved=following("palmeiras", "brasil")):
        page = current.page
        # The big card at the top is the next match: all of it is on screen, broadcasters too.
        box = page.locator("#next-match .hero").bounding_box()
        assert box is not None
        assert box["y"] + box["height"] <= height, box
        assert page.evaluate("window.scrollY") == 0


def test_on_the_smallest_phone_the_next_match_and_its_teams_are_on_screen(
    browser: Browser, origin: str
) -> None:
    height = VIEWPORTS["narrow"][1]
    for current in visit(browser, origin, size="narrow", saved=following("palmeiras")):
        teams = current.page.locator("#next-match .hero__title").bounding_box()
        assert teams is not None
        assert teams["y"] + teams["height"] <= height, teams  # the next match is above the fold


# --- motion --------------------------------------------------------------------------------------


def test_cards_enter_calmly_and_not_at_all_when_motion_is_reduced(
    browser: Browser, origin: str
) -> None:
    script = "e => getComputedStyle(e).animationName"
    for current in visit(browser, origin, saved=following("palmeiras")):
        assert current.page.locator(".match-card").first.evaluate(script) == "card-enter"
    for current in visit(browser, origin, reduced_motion="reduce", saved=following("palmeiras")):
        card = current.page.locator(".match-card").first
        assert card.evaluate(script) == "none"
        assert card.evaluate("e => getComputedStyle(e).opacity") == "1"


def test_the_first_cards_enter_a_beat_apart(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=following("palmeiras", "real-madrid", "chelsea")):
        delays = current.page.locator(".match-card").evaluate_all(
            "c => c.map(x => getComputedStyle(x).animationDelay)"
        )
        assert delays == ["0s", "0.04s", "0.08s"]


# --- the whole page ------------------------------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_on_any_of_the_lists(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(browser, origin, scheme, size, saved=following("sao-paulo")):
        page = current.page
        for name in ("Meus times", "Hoje", "Esta semana"):
            choose(page, name)
            assert axe_violations(page) == [], name
