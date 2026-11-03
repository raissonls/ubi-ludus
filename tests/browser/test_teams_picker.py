"""The teams picker (FR-20): search, multi-select, keyboard, screen reader, colours, persistence."""

import pytest
from playwright.sync_api import Browser, Page, expect
from site_browser import STORAGE_KEY, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

SEARCH = "#team-search"


def announced(page: Page) -> str:
    return (page.locator("#picker-announcer").text_content() or "").replace("\u00a0", "").strip()


def chosen(page: Page) -> list[str]:
    labels: list[str] = page.locator("#chosen-teams .chip").evaluate_all(
        "chips => chips.map(c => c.getAttribute('aria-label'))"
    )
    return labels


def options(page: Page) -> list[str]:
    return page.locator("[role=option] .option__name").all_inner_texts()


def listed_matches(page: Page) -> list[str]:
    return page.locator("#matches-list .match-card__teams").all_inner_texts()


# --- the goal: a new visitor sees their matches in three interactions or fewer ------------------


def test_a_new_visitor_chooses_a_team_and_sees_its_matches_in_three_interactions(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert listed_matches(page) == []
        assert page.locator("#matches-empty").is_visible()

        page.click(SEARCH)  # 1: click the search box
        page.keyboard.type("palm")  # 2: type a few letters
        page.get_by_role("option", name="Palmeiras").click()  # 3: pick the team

        assert listed_matches(page) == ["Palmeiras x Flamengo"]
        assert not page.locator("#matches-empty").is_visible()


def test_the_keyboard_alone_does_it_in_two_steps(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.keyboard.type("real")  # 1
        page.keyboard.press("Enter")  # 2: the first suggestion
        assert chosen(page) == ["Remover Real Madrid"]
        assert listed_matches(page) == ["Real Madrid x Barça"]


# --- search -------------------------------------------------------------------------------------


def test_search_ignores_accents_case_and_finds_aliases(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.keyboard.type("SAO")
        assert options(page) == ["São Paulo"]
        page.fill(SEARCH, "barca")
        assert options(page) == ["Barcelona"]
        page.fill(SEARCH, "brazil")
        assert options(page) == ["Brasil"]


def test_an_empty_box_suggests_brazilian_teams_first_and_shows_where_each_is_from(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        names = options(page)
        assert names[:5] == ["Atlético Mineiro", "Brasil", "Flamengo", "Palmeiras", "São Paulo"]
        countries = page.locator("[role=option] .option__country").all_inner_texts()
        assert countries[0] == "Brasil"
        assert "Espanha" in countries
        assert "Inglaterra" in countries  # a part of a country, from the strings file


def test_no_match_says_so(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.keyboard.type("zzzz")
        assert options(page) == []
        assert (
            page.locator("#team-no-results").inner_text() == "Nenhum time encontrado para “zzzz”."
        )
        # Said after a short pause, so it does not interrupt typing. expect() waits for it.
        expect(page.locator("#picker-announcer")).to_have_text(
            "Nenhum time encontrado para “zzzz”."
        )


def test_chosen_teams_are_not_offered_again(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "real")
        page.keyboard.press("Enter")
        page.fill(SEARCH, "real")
        assert options(page) == []


# --- keyboard and screen reader -----------------------------------------------------------------


def test_the_combobox_says_what_it_is_to_a_screen_reader(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        box = page.get_by_role("combobox", name="Buscar time")
        assert box.get_attribute("aria-expanded") == "false"
        assert box.get_attribute("aria-autocomplete") == "list"
        assert box.get_attribute("aria-controls") == "team-options"
        box.focus()
        assert box.get_attribute("aria-expanded") == "true"
        assert page.get_by_role("listbox").is_visible()
        description = page.locator("#teams-hint").inner_text()
        assert box.get_attribute("aria-describedby") == "teams-hint"
        assert "Digite o nome do time" in description


def test_arrow_keys_move_through_the_options_and_enter_chooses(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        box = page.locator(SEARCH)
        box.focus()
        page.keyboard.type("atl")
        assert options(page) == ["Atlético de Madrid", "Atlético Mineiro"]
        assert (
            box.get_attribute("aria-activedescendant") is None
        )  # nothing active until a key moves

        page.keyboard.press("ArrowDown")
        assert box.get_attribute("aria-activedescendant") == "team-option-atletico-madrid"
        page.keyboard.press("ArrowDown")
        assert box.get_attribute("aria-activedescendant") == "team-option-atletico-mineiro"
        assert (
            page.locator("#team-option-atletico-mineiro").get_attribute("aria-selected") == "true"
        )
        page.keyboard.press("ArrowDown")  # wraps
        assert box.get_attribute("aria-activedescendant") == "team-option-atletico-madrid"
        page.keyboard.press("ArrowUp")  # and back
        assert box.get_attribute("aria-activedescendant") == "team-option-atletico-mineiro"

        page.keyboard.press("Enter")
        assert chosen(page) == ["Remover Atlético Mineiro"]
        assert page.evaluate("document.activeElement.id") == "team-search"  # focus stays in the box
        assert page.locator(SEARCH).input_value() == ""


def test_escape_closes_the_list_then_clears_the_text(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.keyboard.type("sao")
        page.keyboard.press("Escape")
        assert page.get_by_role("listbox").is_hidden()
        assert page.locator(SEARCH).input_value() == "sao"
        page.keyboard.press("Escape")
        assert page.locator(SEARCH).input_value() == ""


def test_what_happens_is_said_in_a_live_region(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert page.locator("#picker-announcer").get_attribute("role") == "status"
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")
        assert announced(page) == "Palmeiras adicionado. 1 time escolhido."
        page.fill(SEARCH, "flam")
        page.keyboard.press("Enter")
        assert announced(page) == "Flamengo adicionado. 2 times escolhidos."
        page.get_by_role("button", name="Remover Flamengo").click()
        assert announced(page) == "Flamengo removido. 1 time escolhido."
        page.get_by_role("button", name="Remover Palmeiras").click()
        assert announced(page) == "Palmeiras removido. Nenhum time escolhido."


def test_the_accessibility_tree_has_a_labelled_combobox_and_a_named_list_of_choices(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")
        tree = page.locator("section[aria-labelledby=teams-title]").aria_snapshot()
        assert 'heading "Quais times você segue?"' in tree
        assert 'combobox "Buscar time"' in tree
        assert 'list "Times escolhidos"' in tree
        assert 'button "Remover Palmeiras"' in tree


# --- chosen teams -------------------------------------------------------------------------------


def test_a_chosen_team_can_be_removed_and_focus_goes_back_to_the_box(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")
        assert listed_matches(page) == ["Palmeiras x Flamengo"]

        page.get_by_role("button", name="Remover Palmeiras").click()

        assert chosen(page) == []
        assert listed_matches(page) == []
        assert page.locator("#chosen-empty").is_visible()
        assert page.evaluate("document.activeElement.id") == "team-search"


def test_a_chip_can_be_removed_from_the_keyboard(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")
        page.keyboard.press("Tab")  # from the box to the first chosen team (the list is closed)
        assert page.evaluate("document.activeElement.className") == "chip"
        page.keyboard.press("Enter")
        assert chosen(page) == []


def test_several_teams_show_all_their_matches_in_time_order(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        for text in ("barca", "chel", "palm"):
            page.fill(SEARCH, text)
            page.keyboard.press("Enter")
        assert listed_matches(page) == [
            "Palmeiras x Flamengo",  # 3 Nov
            "Real Madrid x Barça",  # 4 Nov
            "Chelsea x Atleti",  # 5 Nov
        ]


def test_a_finished_match_and_an_undecided_opponent(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "brasil")
        page.keyboard.press("Enter")
        assert listed_matches(page) == ["Brasil x A definir"]
        page.fill(SEARCH, "sao")
        page.keyboard.press("Enter")
        # Palmeiras x São Paulo is finished: it is not "upcoming".
        assert "Palmeiras x São Paulo" not in listed_matches(page)
        assert "São Paulo x Atlético-MG" in listed_matches(page)


def test_matches_show_the_local_time_in_brazil(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")
        when = page.locator("#matches-list time")
        assert when.get_attribute("datetime") == "2026-11-03T22:00:00Z"
        assert "19:00" in when.inner_text()  # 22:00 UTC is 19:00 in Brazil


# --- the choices are the visitor's, and stay ----------------------------------------------------


def test_the_choices_survive_a_reload(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")
        assert "palmeiras" in page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')")

        page.reload()
        page.wait_for_selector("html[data-ready='true']")

        assert chosen(page) == ["Remover Palmeiras"]
        assert listed_matches(page) == ["Palmeiras x Flamengo"]


def test_reset_my_data_empties_the_picker_and_the_matches(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")
        page.get_by_role("button", name="Apagar meus dados").click()
        assert chosen(page) == []
        assert listed_matches(page) == []
        assert page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')") is None


def test_a_saved_team_the_data_no_longer_has_is_quietly_ignored(
    browser: Browser, origin: str
) -> None:
    saved = {STORAGE_KEY: '{"version": 1, "teams": ["gone-fc", "palmeiras"], "services": []}'}
    for current in visit(browser, origin, saved=saved):
        assert chosen(current.page) == ["Remover Palmeiras"]
        assert current.console == []


# --- colours, not crests ------------------------------------------------------------------------


def test_team_colours_are_used_as_accents_and_nothing_else_is_drawn(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "palm")
        page.keyboard.press("Enter")

        swatch = page.locator("#chosen-teams .swatch")
        background = swatch.evaluate("e => getComputedStyle(e).backgroundImage")
        assert "rgb(0, 100, 55)" in background  # Palmeiras green, #006437
        assert "rgb(255, 255, 255)" in background
        assert swatch.evaluate("e => e.getAttribute('aria-hidden')") == "true"  # the name is there
        bar = page.locator("#matches-list .match-card").evaluate(
            "e => getComputedStyle(e).borderInlineStartColor"
        )
        assert bar == "rgb(0, 100, 55)"
        assert page.locator("img, svg, canvas, picture").count() == 0  # no crest, no logo
        assert current.console == []  # setting a colour from script is allowed by the policy


# --- accessibility with the picker in use -------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_with_the_list_open_and_teams_chosen(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(browser, origin, scheme, size):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "real")
        page.keyboard.press("Enter")
        page.fill(SEARCH, "a")
        page.keyboard.press("ArrowDown")  # an option is active, the list is open
        assert page.get_by_role("listbox").is_visible()
        assert axe_violations(page) == []


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_when_a_search_has_no_result(
    browser: Browser, origin: str, scheme: str
) -> None:
    for current in visit(browser, origin, scheme):
        page = current.page
        page.locator(SEARCH).focus()
        page.keyboard.type("zzzz")
        assert axe_violations(page) == []


def test_the_open_list_never_makes_the_page_scroll_sideways(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, size="narrow"):
        page = current.page
        page.locator(SEARCH).focus()
        page.fill(SEARCH, "a")
        widths = page.evaluate(
            "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
        )
        assert widths[0] <= widths[1]
