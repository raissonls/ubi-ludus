"""What the visitor can watch (FR-25): marks on the cards and the "only what I can watch" filter.

The fixtures' matches are changed here so every case exists: from the 3rd to the 8th, the matches
have SporTV and Globo (Palmeiras), SporTV (Real Madrid), Premiere and ESPN (Chelsea), Globo
(São Paulo) and nothing known (Brasil).
"""

import json
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Page
from site_browser import DATA, STORAGE_KEY, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

GALLERY = "/gallery/cards.html"
SEARCH = "#team-search"
FILTER = "Só o que dá para assistir"
YES = "Dá para assistir com os seus serviços."
NO = "Nenhuma dessas emissoras está nos seus serviços."


def rule(broadcaster: str) -> dict[str, str]:
    return {
        "broadcaster_id": broadcaster,
        "confidence": "rule",
        "source": "rights_rule",
        "updated_at": "2026-11-02T09:00:00Z",
    }


def changed_matches() -> dict[str, dict[str, Any]]:
    document = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    broadcasts = {"fx-2": [rule("sportv")], "fx-3": [rule("premiere"), rule("espn")]}
    for match in document["matches"]:
        if match["id"] in broadcasts:
            match["broadcasts"] = broadcasts[match["id"]]
    return {"matches": document}


def saved(*services: str, teams: tuple[str, ...] = (), only: bool = False) -> dict[str, str]:
    record = {"version": 1, "teams": list(teams), "services": list(services), "onlyWatchable": only}
    return {STORAGE_KEY: json.dumps(record)}


def week(page: Page) -> None:
    page.get_by_role("button", name="Esta semana", exact=True).click()


def access(page: Page) -> list[str | None]:
    found: list[str | None] = page.locator("#matches-list .match-card").evaluate_all(
        "c => c.map(x => x.dataset.access)"
    )
    return found


def titles(page: Page) -> list[str]:
    return page.locator("#matches-list .match-card__teams").all_inner_texts()


# --- marks on the cards --------------------------------------------------------------------------


def test_each_card_says_whether_the_visitor_can_watch_with_what_they_have(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, changed_data=changed_matches()):
        page = current.page
        week(page)
        # Palmeiras (Globo is free), Real Madrid (SporTV only), Chelsea (Premiere, ESPN),
        # São Paulo (Globo), Brasil (nothing known).
        assert access(page) == ["yes", "no", "no", "yes", "unknown"]
        lines = page.locator(".match-card__access").all_inner_texts()
        assert lines == [YES, NO, NO, YES]
        assert "assistir" not in page.locator(".match-card[data-access='unknown']").inner_text()


def test_the_broadcasters_the_visitor_has_are_marked_on_each_badge(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved("premiere"), changed_data=changed_matches()):
        page = current.page
        week(page)
        chelsea = page.locator(".match-card", has_text="Chelsea")
        marks = chelsea.locator(".badge").evaluate_all(
            """b => Object.fromEntries(b.map(x => [
                x.querySelector('span:not([aria-hidden]):not(.visually-hidden)').textContent,
                x.dataset.access,
            ]))"""
        )
        assert marks == {"ESPN": "other", "Premiere": "yours"}  # Premiere is the visitor's
        hidden = chelsea.locator(".badge .visually-hidden").all_text_contents()
        assert " (você tem)" in hidden
        assert " (fora dos seus serviços)" in hidden


def test_ticking_a_service_updates_the_cards_at_once(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, changed_data=changed_matches()):
        page = current.page
        week(page)
        assert access(page) == ["yes", "no", "no", "yes", "unknown"]
        page.get_by_label("Premiere (pay-per-view)").check()  # Chelsea's match has Premiere
        assert access(page) == ["yes", "no", "yes", "yes", "unknown"]
        page.get_by_label("TV por assinatura").check()  # SporTV, for Real Madrid's
        assert access(page) == ["yes", "yes", "yes", "yes", "unknown"]


def test_a_service_that_includes_a_broadcaster_of_another_gives_it(
    browser: Browser, origin: str
) -> None:
    for current in visit(
        browser, origin, saved=saved("disney-plus"), changed_data=changed_matches()
    ):
        page = current.page
        week(page)
        assert access(page)[2] == "yes"  # ESPN, which the Disney+ plan includes


def test_a_match_that_cannot_be_watched_is_set_apart_by_words_and_a_dashed_edge(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, changed_data=changed_matches()):
        page = current.page
        week(page)
        card = page.locator(".match-card[data-access='no']").first
        style = card.evaluate("e => getComputedStyle(e).borderTopStyle")
        assert style == "dashed"
        assert card.locator(".match-card__access").inner_text() == NO
        assert (
            page.locator(".match-card[data-access='yes']").first.evaluate(
                "e => getComputedStyle(e).borderTopStyle"
            )
            == "solid"
        )


# --- the filter ----------------------------------------------------------------------------------


def test_the_filter_hides_only_what_cannot_be_watched_and_keeps_unknown(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, changed_data=changed_matches()):
        page = current.page
        week(page)
        assert len(titles(page)) == 5
        page.get_by_label(FILTER).check()
        assert titles(page) == [
            "Palmeiras x Flamengo",
            "São Paulo x Atlético-MG",
            "Brasil x A definir",
        ]
        page.get_by_label("Premiere (pay-per-view)").check()
        assert len(titles(page)) == 4  # Chelsea's match is back
        page.get_by_label(FILTER).uncheck()
        assert len(titles(page)) == 5


def test_the_filter_persists_and_comes_back_after_a_reload(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, changed_data=changed_matches()):
        page = current.page
        page.get_by_label(FILTER).check()
        stored = json.loads(page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')"))
        assert stored["onlyWatchable"] is True
        page.reload()
        page.wait_for_selector("html[data-ready='true']")
        assert page.get_by_label(FILTER).is_checked()
        week(page)
        assert len(titles(page)) == 3
        page.get_by_label(FILTER).uncheck()
        stored = json.loads(page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')"))
        assert stored["onlyWatchable"] is False


def test_reset_my_data_turns_the_filter_off(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(only=True)):
        page = current.page
        assert page.get_by_label(FILTER).is_checked()
        page.click("#reset-data")
        assert not page.get_by_label(FILTER).is_checked()


def test_the_filter_comes_before_the_limit_so_my_teams_still_fills_up(
    browser: Browser, origin: str
) -> None:
    only = saved(teams=("real-madrid", "chelsea", "palmeiras"), only=True)
    for current in visit(browser, origin, saved=only, changed_data=changed_matches()):
        page = current.page
        assert titles(page) == ["Palmeiras x Flamengo"]  # Real Madrid's and Chelsea's are hidden


def test_when_the_filter_hides_everything_the_page_says_why(browser: Browser, origin: str) -> None:
    only = saved(teams=("real-madrid",), only=True)
    for current in visit(browser, origin, saved=only, changed_data=changed_matches()):
        page = current.page
        assert titles(page) == []
        text = page.locator("#matches-empty").inner_text()
        assert text == "Nenhum jogo desta lista dá para assistir com os seus serviços."


def test_the_filter_is_a_labelled_checkbox_with_its_hint(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        box = current.page.get_by_role("checkbox", name=FILTER)
        assert not box.is_checked()
        described = box.get_attribute("aria-describedby")
        hint = current.page.locator(f"#{described}").inner_text()
        assert hint == "Jogos sem emissora confirmada continuam na lista."


def test_the_filter_sends_nothing_anywhere(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        before = len(current.requests)
        current.page.get_by_label(FILTER).check()
        current.page.get_by_label("Premiere (pay-per-view)").check()
        assert current.requests[before:] == []


# --- the gallery: the same on every state --------------------------------------------------------


def test_a_match_that_is_over_or_off_says_nothing_about_access(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY + "?services="):
        page = current.page
        for name in ("finished", "postponed", "cancelled"):
            card = page.locator(f"[data-case='{name}']")
            assert card.get_attribute("data-access") is None
            assert card.locator(".match-card__access").count() == 0


def test_a_card_says_nothing_about_access_when_the_services_are_not_known(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        assert current.page.locator("[data-access]").count() == 0


def test_an_unknown_match_is_neither_yes_nor_no(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=GALLERY + "?services="):
        card = current.page.locator("[data-case='scheduled-unknown']")
        assert card.get_attribute("data-access") == "unknown"
        assert card.locator(".match-card__access").count() == 0
        assert "Transmissão ainda não confirmada" in card.inner_text()


# --- the whole page ------------------------------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_with_marks_and_the_filter(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(browser, origin, scheme, size, changed_data=changed_matches()):
        page = current.page
        week(page)
        assert axe_violations(page) == []
        page.get_by_label(FILTER).check()
        assert axe_violations(page) == []
    for current in visit(browser, origin, scheme, size, path=GALLERY + "?services=premiere"):
        assert axe_violations(current.page) == []
