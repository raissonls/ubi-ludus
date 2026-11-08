"""My teams (FR-20), in the settings panel: the teams chosen so far, one row each with a button to
take it out, and "Adicionar times", which opens the same choice as at the start (continent, country,
team). There is no search box in the panel: typing into a list of suggestions does not work well on
a phone, and the choice of teams has one way in."""

import json

import pytest
from playwright.sync_api import Browser, Page
from site_browser import STORAGE_KEY, VIEWPORTS, add_teams, axe_violations, open_settings, visit

pytestmark = pytest.mark.browser


def saved(*teams: str) -> dict[str, str]:
    return {STORAGE_KEY: json.dumps({"version": 1, "teams": list(teams), "services": []})}


def chosen(page: Page) -> list[str]:
    labels: list[str] = page.locator("#chosen-teams .team-row__remove").evaluate_all(
        "buttons => buttons.map(b => b.getAttribute('aria-label'))"
    )
    return labels


def names(page: Page) -> list[str]:
    return page.locator("#chosen-teams .team-row__name").all_inner_texts()


def listed_matches(page: Page) -> list[str]:
    return page.locator("#matches-list .match-card__teams").all_inner_texts()


# --- the panel has no search box: the choice of teams is the flow -------------------------------


def test_the_panel_has_no_search_box_and_one_way_to_add_teams(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, settings=True):
        page = current.page
        mine = page.locator("section[aria-labelledby=teams-title]")  # (the filters have a text box)
        assert mine.locator("input, [role=combobox], [role=listbox]").count() == 0
        add = page.get_by_role("button", name="Adicionar times")
        box = add.bounding_box()
        assert box is not None and box["height"] >= 44 and box["width"] >= 200


def test_a_new_visitor_adds_a_team_through_the_choice_and_sees_its_matches(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, settings=True):
        page = current.page
        assert listed_matches(page) == []
        assert page.locator("#matches-empty").is_visible()
        assert page.locator("#chosen-empty").is_visible()

        add_teams(page, "palm")

        assert listed_matches(page) == ["Palmeiras x Flamengo"]
        assert not page.locator("#matches-empty").is_visible()
        open_settings(page)
        assert chosen(page) == ["Remover Palmeiras"]


def test_adding_keeps_the_teams_that_were_already_chosen(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved("palmeiras")):
        page = current.page
        add_teams(page, "real")
        open_settings(page)
        assert names(page) == ["Palmeiras", "Real Madrid"]


# --- what the panel lists ---------------------------------------------------------------------


def test_each_team_is_a_row_with_its_shirt_its_name_and_where_it_is_from(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, settings=True, saved=saved("palmeiras", "real-madrid")):
        page = current.page
        assert names(page) == ["Palmeiras", "Real Madrid"]
        countries = page.locator("#chosen-teams .team-row__country").all_inner_texts()
        assert countries == ["Brasil", "Espanha"]
        assert page.locator("#chosen-teams .team-row__shirt").count() == 2
        assert not page.locator("#chosen-empty").is_visible()


def test_the_list_is_named_for_a_screen_reader(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, settings=True, saved=saved("palmeiras")):
        tree = current.page.locator("section[aria-labelledby=teams-title]").aria_snapshot()
        assert 'heading "Meus times"' in tree
        assert 'list "Meus times"' in tree
        assert 'button "Remover Palmeiras"' in tree
        assert 'button "Adicionar times"' in tree


def test_a_saved_team_the_data_no_longer_has_is_quietly_ignored(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, settings=True, saved=saved("gone-fc", "palmeiras")):
        assert chosen(current.page) == ["Remover Palmeiras"]
        assert current.console == []


# --- taking a team out ------------------------------------------------------------------------


def test_a_team_can_be_removed_and_its_matches_go(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, settings=True, saved=saved("palmeiras")):
        page = current.page
        assert listed_matches(page) == ["Palmeiras x Flamengo"]

        page.get_by_role("button", name="Remover Palmeiras").click()

        assert chosen(page) == []
        assert listed_matches(page) == []
        assert page.locator("#chosen-empty").is_visible()
        assert page.evaluate("document.activeElement.id") == "reopen-onboarding"


def test_the_remove_button_is_a_comfortable_target_and_works_from_the_keyboard(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, settings=True, size="mobile", saved=saved("palmeiras")):
        page = current.page
        button = page.get_by_role("button", name="Remover Palmeiras")
        box = button.bounding_box()
        assert box is not None and box["width"] >= 44 and box["height"] >= 44
        button.focus()
        page.keyboard.press("Enter")
        assert chosen(page) == []


# --- several teams ----------------------------------------------------------------------------


def test_several_teams_show_all_their_matches_in_time_order(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, settings=True):
        page = current.page
        add_teams(page, "barca", "chel", "palm")
        assert listed_matches(page) == [
            "Palmeiras x Flamengo",  # 3 Nov
            "Real Madrid x Barça",  # 4 Nov
            "Chelsea x Atleti",  # 5 Nov
        ]


def test_a_finished_match_and_an_undecided_opponent(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, settings=True):
        page = current.page
        add_teams(page, "brasil", "sao")
        # Palmeiras x São Paulo is finished: it is not "upcoming".
        assert "Palmeiras x São Paulo" not in listed_matches(page)
        assert "São Paulo x Atlético-MG" in listed_matches(page)
        assert "Brasil x A definir" in listed_matches(page)


def test_matches_show_the_local_time_in_brazil(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved("palmeiras")):
        when = current.page.locator("#matches-list time").first
        assert when.get_attribute("datetime") == "2026-11-03T22:00:00Z"
        assert "19:00" in when.inner_text()  # 22:00 UTC is 19:00 in Brazil


# --- the choices are the visitor's, and stay ----------------------------------------------------


def test_the_choices_survive_a_reload(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, settings=True):
        page = current.page
        add_teams(page, "palm")
        assert "palmeiras" in page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')")

        page.reload()
        page.wait_for_selector("html[data-ready='true']")
        open_settings(page)

        assert chosen(page) == ["Remover Palmeiras"]
        assert listed_matches(page) == ["Palmeiras x Flamengo"]


def test_reset_my_data_empties_the_list_and_the_matches(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, settings=True, saved=saved("palmeiras")):
        page = current.page
        page.get_by_role("button", name="Apagar meus dados").click()
        assert chosen(page) == []
        assert listed_matches(page) == []
        assert page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')") is None


# --- colours, not crests ------------------------------------------------------------------------


def test_team_colours_are_used_as_accents_and_nothing_else_is_drawn(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, settings=True, saved=saved("palmeiras")):
        page = current.page
        shirt = page.locator("#chosen-teams .team-row__shirt")
        assert shirt.locator(".shirt__body").get_attribute("fill") == "#006437"  # Palmeiras green
        assert shirt.get_attribute("aria-hidden") == "true"  # the name is beside it
        wash = page.locator("#matches-list .match-card").first.evaluate(
            "e => e.style.getPropertyValue('--home')"
        )
        assert wash == "#006437"  # the poster's wash starts from Palmeiras green
        # Only the shirts and the small icons of the interface: no crest, no logo of a club.
        assert (
            page.locator(
                "img:not(.brand__logo), canvas, picture, svg:not(.shirt):not(.icon)"
            ).count()
            == 0
        )
        assert current.console == []  # setting a colour from script is allowed by the policy


# --- accessibility and fit ----------------------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_with_teams_listed_in_the_panel(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(
        browser, origin, scheme, size, settings=True, saved=saved("palmeiras", "real-madrid")
    ):
        assert axe_violations(current.page) == []


def test_the_list_never_makes_the_page_scroll_sideways(browser: Browser, origin: str) -> None:
    teams = ("palmeiras", "real-madrid", "flamengo", "brasil")
    for current in visit(browser, origin, settings=True, size="narrow", saved=saved(*teams)):
        page = current.page
        widths = page.evaluate(
            "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
        )
        assert widths[0] <= widths[1]
        body = page.evaluate(
            "(() => { const b = document.querySelector('#settings .drawer__body');"
            " return [b.scrollWidth, b.clientWidth]; })()"
        )
        assert body[0] <= body[1]
