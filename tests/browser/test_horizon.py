"""Competitions with a short data horizon (FR-34): the page says the data goes only until tomorrow.

Which competitions are short is read from the published data (`coverage`, set by the pipeline from
the horizon in config/competitions.yml), never from a name in the page. The fixture data has one:
"Amistosos de seleções".
"""

import json
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page
from site_browser import DATA, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

WEEK = "/index.html?view=week"
NOTICE = "#horizon-notice"
SOME = (
    "Para Amistosos de seleções, só temos dados até amanhã. "
    "Jogos depois disso ainda não aparecem aqui."
)
EMPTY = (
    "Para algumas competições só temos dados até amanhã. "
    "Por isso, pode haver jogos que ainda não aparecem aqui."
)
CARD = "Dados desta competição só até amanhã"


def notice(page: Page) -> str | None:
    box = page.locator(NOTICE)
    return box.inner_text() if box.is_visible() else None


def competitions(coverage: str) -> dict[str, object]:
    document = json.loads(Path(DATA / "competitions.json").read_text(encoding="utf-8"))
    for competition in document["competitions"]:
        competition["coverage"] = coverage
    return document  # type: ignore[no-any-return]


def test_the_list_names_the_short_competitions_it_shows(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=WEEK):
        assert notice(current.page) == SOME
        assert current.console == []


def test_only_the_cards_of_a_short_competition_say_so(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=WEEK):
        page = current.page
        short = page.locator(".match-card", has_text="Amistosos de seleções")
        assert short.count() == 1
        assert short.locator(".match-card__horizon").inner_text() == CARD
        assert page.locator(".match-card__horizon").count() == 1  # not on the other cards
        assert page.locator(".match-card[data-horizon='short']").count() == 1


def test_a_list_without_short_competitions_has_no_notice(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=f"{WEEK}&competition=brasileirao-serie-a"):
        page = current.page
        assert page.locator(".match-card").count() > 0
        assert notice(page) is None
        assert page.locator(".match-card__horizon").count() == 0


def test_a_short_competition_asked_for_with_no_matches_still_says_it(
    browser: Browser, origin: str
) -> None:
    for current in visit(
        browser, origin, path="/index.html?view=today&competition=amistosos-selecoes"
    ):
        page = current.page
        assert page.locator("#matches-list").is_hidden()
        assert notice(page) == SOME  # an empty list that is not "there are no matches"


def test_an_empty_list_says_some_competitions_are_known_only_until_tomorrow(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path="/index.html?view=today"):
        page = current.page
        assert page.locator("#matches-empty").inner_text() == "Nenhum jogo hoje."
        assert notice(page) == EMPTY


def test_the_notice_follows_the_data_not_the_page(browser: Browser, origin: str) -> None:
    # The same page with every competition at its full window says nothing.
    for current in visit(
        browser, origin, path=WEEK, changed_data={"competitions": competitions("full")}
    ):
        page = current.page
        assert page.locator(".match-card").count() > 0
        assert notice(page) is None
        assert page.locator(".match-card__horizon").count() == 0
    # And with every one short, every card and the notice say so.
    for current in visit(
        browser, origin, path=WEEK, changed_data={"competitions": competitions("short")}
    ):
        page = current.page
        text = notice(page) or ""
        assert text.startswith("Para ") and "Campeonato Brasileiro Série A" in text
        assert page.locator(".match-card__horizon").count() == page.locator(".match-card").count()


def test_it_follows_the_filters_as_they_change(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=WEEK):
        page = current.page
        assert notice(page) == SOME
        page.locator("#filters summary").click()
        page.select_option("#filter-competition", "brasileirao-serie-a")
        assert notice(page) is None
        page.select_option("#filter-competition", "")
        assert notice(page) == SOME


def test_a_screen_reader_gets_it_in_reading_order_as_a_status(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=WEEK):
        page = current.page
        assert page.locator(NOTICE).get_attribute("role") == "status"
        tree = page.locator("#matches-content").aria_snapshot()
        assert "status" in tree and SOME in tree
        card = page.locator(".match-card", has_text="Amistosos de seleções")
        assert CARD in card.aria_snapshot()  # part of the card, which is read through as a whole


def test_it_needs_no_keyboard_action_and_does_not_trap_it(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=WEEK):
        page = current.page
        # Plain text: nothing to press, and the Tab order goes on through the cards.
        assert page.locator(f"{NOTICE} a, {NOTICE} button, {NOTICE}[tabindex]").count() == 0
        page.locator("#view-switch button").first.focus()
        for _ in range(3):
            page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement !== document.body")


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_with_the_notice(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(browser, origin, scheme, size, path=WEEK):
        page = current.page
        assert notice(page) == SOME
        assert axe_violations(page) == []
    for current in visit(browser, origin, scheme, size, path="/index.html?view=today"):
        assert notice(current.page) == EMPTY
        assert axe_violations(current.page) == []


# --- the competitions with no data are listed (PRD risk R1) ---------------------------------------

UNCOVERED = "#uncovered"


def with_uncovered(*ids: str) -> dict[str, object]:
    document = json.loads(Path(DATA / "competitions.json").read_text(encoding="utf-8"))
    for competition in document["competitions"]:
        if competition["id"] in ids:
            competition["coverage"] = "none"
    return document  # type: ignore[no-any-return]


def test_the_competitions_with_no_data_are_listed_instead_of_missing(
    browser: Browser, origin: str
) -> None:
    ids = ("amistosos-selecoes", "uefa-champions-league")
    for current in visit(
        browser, origin, path=WEEK, changed_data={"competitions": with_uncovered(*ids)}
    ):
        page = current.page
        summary = page.locator("#uncovered-summary")
        assert summary.inner_text() == "2 competições ainda sem dados"
        assert page.locator(UNCOVERED).get_attribute("open") is None  # closed until asked
        summary.click()
        assert page.locator("#uncovered-list li").all_inner_texts() == [
            "Amistosos de seleções",
            "UEFA Champions League",
        ]
        assert "não quer dizer que não haja jogos" in page.locator(UNCOVERED).inner_text()
        assert current.console == []


def test_one_competition_reads_in_the_singular(browser: Browser, origin: str) -> None:
    changed = {"competitions": with_uncovered("amistosos-selecoes")}
    for current in visit(browser, origin, path=WEEK, changed_data=changed):
        assert current.page.locator("#uncovered-summary").inner_text() == (
            "1 competição ainda sem dados"
        )


def test_nothing_is_shown_when_every_competition_has_data(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=WEEK):
        assert not current.page.locator(UNCOVERED).is_visible()


def test_the_list_is_there_even_when_a_filter_or_a_quiet_day_leaves_no_matches(
    browser: Browser, origin: str
) -> None:
    changed = {"competitions": with_uncovered("amistosos-selecoes")}
    for current in visit(browser, origin, path="/index.html?view=today", changed_data=changed):
        page = current.page
        assert page.locator("#matches-list").is_hidden()
        assert page.locator("#uncovered-summary").is_visible()


def test_the_list_opens_and_closes_from_the_keyboard(browser: Browser, origin: str) -> None:
    changed = {"competitions": with_uncovered("amistosos-selecoes")}
    for current in visit(browser, origin, path=WEEK, changed_data=changed):
        page = current.page
        page.locator("#uncovered-summary").focus()
        page.keyboard.press("Enter")
        assert page.locator(UNCOVERED).get_attribute("open") is not None
        assert page.locator("#uncovered-list li").is_visible()
        page.keyboard.press("Enter")
        assert page.locator(UNCOVERED).get_attribute("open") is None


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_with_the_list_open(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    ids = ("amistosos-selecoes", "uefa-champions-league")
    for current in visit(
        browser,
        origin,
        scheme,
        size,
        path=WEEK,
        changed_data={"competitions": with_uncovered(*ids)},
    ):
        page = current.page
        page.locator("#uncovered-summary").click()
        assert axe_violations(page) == []
