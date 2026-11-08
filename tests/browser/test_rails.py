"""The match lists as rows of posters, the quick-filter chips, and the sheet with the details.

Like a streaming app: rows with a title, posters to scroll sideways, a tap for the details. The
full match card (broadcasters, calendar, report link) lives in the sheet; its own tests are in
test_match_card.py. Here: what is in each row, what a poster says, what the chips do, what the
sheet does, and that all of it is reachable with a keyboard and a screen reader.
"""

import json
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, expect
from site_browser import STORAGE_KEY, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

POSTERS = "#matches-list .match-card--poster"
SHEET = "#match-sheet"


def saved(teams: list[str], services: list[str] | None = None) -> dict[str, str]:
    record = {"version": 1, "teams": teams, "services": services or []}
    return {STORAGE_KEY: json.dumps(record)}


def switch(page: Page, label: str) -> None:
    page.locator("#view-switch [data-view]").get_by_text(label, exact=True).click()


def row_titles(page: Page) -> list[str]:
    titles: list[str] = page.locator("#matches-list .rail__title").all_inner_texts()
    return titles


def poster(page: Page, teams: str) -> Any:
    return page.locator(POSTERS).filter(has=page.locator(".match-card__teams", has_text=teams))


# --- the rows ---------------------------------------------------------------------------------


def test_the_week_has_a_row_for_each_day_with_a_title(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        switch(page, "Esta semana")
        titles = row_titles(page)
        assert titles[0] in {"Hoje", "Amanhã"} or titles[0][0].isupper()
        assert len(titles) == len(set(titles)) and len(titles) >= 2
        assert page.locator("#matches-list .rail").count() == len(titles)


def test_a_row_is_a_labelled_region_of_posters(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        switch(page, "Esta semana")
        first = page.locator("#matches-list .rail").first
        title_id = first.locator(".rail__title").get_attribute("id")
        assert first.get_attribute("aria-labelledby") == title_id
        assert first.locator(".rail__track > .match-card--poster").count() >= 1
        # The track scrolls sideways.
        assert (
            first.locator(".rail__track").evaluate("e => getComputedStyle(e).overflowX") == "auto"
        )


def test_a_visitors_teams_come_first_in_their_own_row_on_today(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"]), now="2026-11-03T12:00:00Z"):
        page = current.page
        switch(page, "Hoje")
        assert row_titles(page)[0] == "Jogos dos seus times"
        assert page.locator("#matches-list .rail").first.locator(POSTERS.split()[-1]).count() >= 1
        assert poster(page, "Palmeiras x Flamengo").get_attribute("data-followed") == "true"


def three_on_the_same_day() -> dict[str, Any]:
    """The test data with two more matches on 3 November, so that one row holds three posters."""
    from pathlib import Path  # noqa: PLC0415

    from site_browser import DATA  # noqa: PLC0415

    document = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    first = next(m for m in document["matches"] if m["id"] == "fx-1")
    for suffix, hour in (("b", "20"), ("c", "21")):
        document["matches"].append(
            {**first, "id": f"fx-1{suffix}", "kickoff_utc": f"2026-11-03T{hour}:00:00Z"}
        )
    return {"matches": document}


def test_a_row_with_many_posters_can_open_into_a_grid(browser: Browser, origin: str) -> None:
    for current in visit(
        browser, origin, now="2026-11-03T12:00:00Z", changed_data=three_on_the_same_day()
    ):
        page = current.page
        switch(page, "Hoje")
        rail = page.locator("#matches-list .rail", has=page.locator(".rail__more")).first
        assert rail.locator(POSTERS.split()[-1]).count() == 3
        more = rail.locator(".rail__more")
        assert more.get_attribute("aria-expanded") == "false"
        assert "Ver tudo em" in (more.get_attribute("aria-label") or "")
        more.click()
        assert more.get_attribute("aria-expanded") == "true"
        assert rail.locator(".rail__track").evaluate("e => getComputedStyle(e).display") == "grid"
        more.click()
        assert rail.locator(".rail__track").evaluate("e => getComputedStyle(e).display") == "flex"


# --- a poster ---------------------------------------------------------------------------------


def test_a_poster_says_the_time_the_teams_and_where_to_watch(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"], ["globoplay"])):
        page = current.page
        card = poster(page, "Palmeiras x Flamengo")
        assert card.locator(".match-card__when time").inner_text() == "19:00"
        assert card.locator(".poster__shirts .shirt").count() == 2
        assert card.locator(".poster__chip").inner_text() in {"Grátis", "Pago"}
        assert card.locator(".poster__badges .badge").count() >= 1
        assert card.get_attribute("data-access") in {"yes", "no", "unknown"}


def test_the_whole_poster_is_one_button_with_a_name_that_says_what_it_does(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        button = poster(page, "Palmeiras x Flamengo").locator(".poster__open")
        assert button.get_attribute("aria-haspopup") == "dialog"
        label = button.get_attribute("aria-label") or ""
        assert label.startswith("Palmeiras x Flamengo, ")
        assert label.endswith("Ver detalhes")
        # Its hit area covers the card, so a press anywhere on it opens the details.
        poster(page, "Palmeiras x Flamengo").click()  # the middle of the card, not the name
        expect(page.locator(SHEET)).to_be_visible()


def test_posters_show_shirts_in_the_colours_of_the_teams(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        fills = (
            poster(page, "Palmeiras x Flamengo")
            .locator(".shirt__body")
            .evaluate_all("e => e.map(x => x.getAttribute('fill'))")
        )
        assert fills == ["#006437", "#C52613"]


# --- the sheet --------------------------------------------------------------------------------


def test_pressing_a_poster_opens_the_full_card_in_a_sheet_that_names_the_match(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"], ["globoplay"])):
        page = current.page
        poster(page, "Palmeiras x Flamengo").locator(".poster__open").click()
        sheet = page.locator(SHEET)
        expect(sheet).to_be_visible()
        assert (
            sheet.get_attribute("aria-labelledby")
            == "card-"
            + (page.locator(f"{SHEET} .match-card").get_attribute("id") or "").removeprefix("card-")
            + "-title"
        )
        text = sheet.inner_text()
        assert "Palmeiras" in text and "Onde assistir" in text
        assert (
            sheet.get_by_role(
                "link", name="Reportar transmissão errada de Palmeiras x Flamengo"
            ).count()
            == 1
        )
        assert sheet.get_by_role("button", name="Adicionar ao calendário").count() == 1
        # The page behind cannot be reached while it is open.
        assert page.evaluate("document.querySelector('#match-sheet').matches(':modal')") is True


def test_the_sheet_closes_with_the_button_escape_or_a_press_outside_and_gives_the_focus_back(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        opener = poster(page, "Palmeiras x Flamengo").locator(".poster__open")
        for close in ("button", "escape", "outside"):
            opener.focus()
            page.keyboard.press("Enter")
            expect(page.locator(SHEET)).to_be_visible()
            assert page.evaluate("document.activeElement.closest('#match-sheet') !== null")
            if close == "button":
                page.click("#match-sheet-close")
            elif close == "escape":
                page.keyboard.press("Escape")
            else:
                page.mouse.click(5, 5)
            expect(page.locator(SHEET)).to_be_hidden()
            assert page.evaluate("document.activeElement.className") == "poster__open"
            expect(page.locator("#match-sheet-card")).to_be_empty()


def test_the_sheets_calendar_button_saves_the_match(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        poster(page, "Palmeiras x Flamengo").locator(".poster__open").click()
        page.get_by_role("button", name="Adicionar ao calendário").click()
        assert "calendário" in page.locator("#calendar-status").inner_text().lower()


# --- the chips --------------------------------------------------------------------------------


def chip(page: Page, name: str) -> Any:
    return page.locator(f"#quick-filters [data-quick='{name}']")


def test_the_chips_start_with_everything_and_say_which_is_on(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert chip(page, "all").get_attribute("aria-pressed") == "true"
        for name in ("live", "watchable", "free"):
            assert chip(page, name).get_attribute("aria-pressed") == "false"


def test_free_only_keeps_matches_with_free_tv_or_youtube(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        switch(page, "Esta semana")
        before = page.locator(POSTERS).count()
        chip(page, "free").click()
        assert chip(page, "free").get_attribute("aria-pressed") == "true"
        assert chip(page, "all").get_attribute("aria-pressed") == "false"
        kept = page.locator(POSTERS)
        assert 0 < kept.count() <= before
        assert kept.locator(".poster__chip--free").count() == kept.count()
        chip(page, "all").click()
        assert page.locator(POSTERS).count() == before


def test_can_watch_is_the_same_choice_as_the_one_in_the_filters(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved([], ["globoplay"])):
        page = current.page
        chip(page, "watchable").click()
        assert chip(page, "watchable").get_attribute("aria-pressed") == "true"
        page.locator("#filters summary").click()
        assert page.locator("#only-watchable").is_checked()
        chip(page, "watchable").click()
        assert not page.locator("#only-watchable").is_checked()


def test_the_competition_chip_opens_the_filters_at_the_competition(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        chip(page, "competition").click()
        assert page.locator("#filters").get_attribute("open") is not None
        assert page.evaluate("document.activeElement.id") == "filter-competition"


def test_live_now_with_nothing_live_says_so(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        chip(page, "live").click()
        assert page.locator(POSTERS).count() == 0
        assert page.locator("#matches-empty").is_visible()


# --- the live row -----------------------------------------------------------------------------


def status_of_fx1(status: str) -> dict[str, Any]:
    from pathlib import Path  # noqa: PLC0415

    from site_browser import DATA  # noqa: PLC0415

    document = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    for match in document["matches"]:
        if match["id"] == "fx-1":
            match["status"] = status
    return {"matches": document}


def test_a_match_on_now_is_in_the_live_row_first_and_not_repeated(
    browser: Browser, origin: str
) -> None:
    # Palmeiras x Flamengo kicks off at 22:00 UTC on the 3rd: an hour later it is on.
    for current in visit(browser, origin, saved=saved(["palmeiras"]), now="2026-11-03T23:00:00Z"):
        page = current.page
        switch(page, "Hoje")
        assert row_titles(page)[0] == "Ao vivo agora"
        assert poster(page, "Palmeiras x Flamengo").count() == 1


def test_a_match_the_data_still_calls_live_long_after_is_not_on_now(
    browser: Browser, origin: str
) -> None:
    for current in visit(
        browser,
        origin,
        saved=saved(["palmeiras"]),
        now="2026-11-04T02:30:00Z",  # four and a half hours later: long over
        changed_data=status_of_fx1("live"),
    ):
        page = current.page
        switch(page, "Hoje")
        assert poster(page, "Palmeiras x Flamengo").count() == 1  # still listed ...
        assert "Ao vivo agora" not in row_titles(page)  # ... but not as on now


# --- the page stays within its rules ----------------------------------------------------------


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", list(VIEWPORTS))
def test_the_rows_the_chips_and_the_sheet_have_no_accessibility_violation(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    options: dict[str, Any] = {
        "saved": saved(["palmeiras"], ["globoplay"]),
        "reduced_motion": "reduce",
    }
    for current in visit(browser, origin, scheme=scheme, size=size, **options):
        page = current.page
        switch(page, "Esta semana")
        assert axe_violations(page) == []
        poster(page, "Palmeiras x Flamengo").locator(".poster__open").click()
        expect(page.locator(SHEET)).to_be_visible()
        assert axe_violations(page) == []


def test_a_row_is_reached_with_the_keyboard_and_scrolls_to_the_poster_in_focus(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, size="mobile"):
        page = current.page
        switch(page, "Esta semana")
        last = page.locator("#matches-list .rail").first.locator(".poster__open").last
        last.focus()
        box = last.evaluate("e => e.closest('.match-card').getBoundingClientRect().right")
        assert box <= VIEWPORTS["mobile"][0] + 1, box  # scrolled into view, not off to the side


def test_the_page_is_never_wider_than_the_screen_with_rows(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, size="narrow"):
        page = current.page
        switch(page, "Esta semana")
        assert page.evaluate("document.documentElement.scrollWidth") <= VIEWPORTS["narrow"][0]
