"""Live now and the countdown to kickoff (FR-26), with a clock the test winds.

Palmeiras x Flamengo kicks off at 2026-11-03T22:00:00Z. The page's clock stands where the test puts
it and moves only with run_for(), so "around kickoff" is checked to the second.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Locator, Page
from site_browser import DATA, VIEWPORTS, Visit, axe_violations, visit

pytestmark = pytest.mark.browser

WEEK = "/index.html?view=week"
SECOND = 1000
MINUTE = 60 * SECOND
HOUR = 60 * MINUTE


def card(page: Page, text: str = "Palmeiras") -> Locator:
    return page.locator(".match-card", has_text=text).first


def clock(page: Page) -> str:
    line = card(page).locator(".clock")
    return line.inner_text() if line.count() else ""


def with_status(status: str) -> dict[str, dict[str, Any]]:
    document = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    for match in document["matches"]:
        if match["id"] == "fx-1":
            match["status"] = status
    return {"matches": document}


def at(browser: Browser, origin: str, moment: str, **options: Any) -> Iterator[Visit]:
    """The week's lists with the page's clock standing at `moment` and moved only by the test."""
    return visit(browser, origin, path=WEEK, now=moment, ticking=True, **options)


# --- the countdown -------------------------------------------------------------------------------


def test_within_a_day_of_kickoff_the_card_counts_down(browser: Browser, origin: str) -> None:
    for current in at(browser, origin, "2026-11-03T19:30:00Z"):
        page = current.page
        assert clock(page) == "Começa em 2 h 30 min"
        assert card(page).get_attribute("data-phase") == "countdown"
        # The other matches are further than a day away: only their date is shown.
        assert card(page, "Real Madrid").locator(".clock").count() == 0


def test_the_countdown_follows_the_clock_without_a_reload(browser: Browser, origin: str) -> None:
    for current in at(browser, origin, "2026-11-03T19:30:00Z"):
        page = current.page
        page.evaluate("window.__same_page = true")
        page.clock.run_for(30 * MINUTE)
        assert clock(page) == "Começa em 2 h"
        page.clock.run_for(HOUR + 18 * MINUTE)  # 20:00 + 1h18 = 21:18
        assert clock(page) == "Começa em 42 min"
        page.clock.run_for(41 * MINUTE)  # 21:59
        assert clock(page) == "Começa em 1 min"
        assert page.evaluate("window.__same_page") is True  # never reloaded


def test_the_card_changes_at_kickoff_to_the_second(browser: Browser, origin: str) -> None:
    for current in at(browser, origin, "2026-11-03T21:59:00Z"):
        page = current.page
        assert clock(page) == "Começa em 1 min"
        page.clock.run_for(30 * SECOND)  # 21:59:30, thirty seconds to go
        assert clock(page) == "Começa em 1 min"
        page.clock.run_for(10 * SECOND)  # 21:59:40, twenty seconds to go
        assert clock(page) == "Começa em instantes"
        page.clock.run_for(10 * SECOND)  # 21:59:50, ten seconds to go
        assert clock(page) == "Começa em instantes"
        page.clock.run_for(10 * SECOND)  # 22:00:00: kickoff
        assert clock(page) == "● Em andamento"
        assert card(page).get_attribute("data-phase") == "live"


def test_a_match_that_has_already_started_is_in_progress(browser: Browser, origin: str) -> None:
    for current in at(browser, origin, "2026-11-03T22:40:00Z"):
        page = current.page
        assert clock(page) == "● Em andamento"
        # The data says "scheduled", so no "Ao vivo" label: the clock claims no more than the time.
        assert card(page).locator(".state").count() == 0
        assert "Ao vivo" not in card(page).inner_text()


def test_after_the_longest_normal_match_it_is_probably_over(browser: Browser, origin: str) -> None:
    for current in at(browser, origin, "2026-11-04T00:59:50Z"):
        page = current.page
        assert clock(page) == "● Em andamento"  # 2 h 59 min 50 s after kickoff
        page.clock.run_for(10 * SECOND)  # exactly three hours
        assert clock(page) == "Provavelmente encerrado"
        assert card(page).get_attribute("data-phase") == "over"


# --- what the data says --------------------------------------------------------------------------


def test_a_match_the_data_calls_live_says_so_once(browser: Browser, origin: str) -> None:
    for current in visit(
        browser,
        origin,
        path=WEEK,
        now="2026-11-03T22:30:00Z",
        ticking=True,
        changed_data=with_status("live"),
    ):
        page = current.page
        text = card(page).inner_text()
        assert text.count("Ao vivo") == 1
        assert "Em andamento" not in text  # no second label saying the same
        assert card(page).get_attribute("data-phase") == "live"


def test_data_that_still_says_live_hours_later_is_not_believed(
    browser: Browser, origin: str
) -> None:
    for current in visit(
        browser,
        origin,
        path=WEEK,
        now="2026-11-04T00:30:00Z",
        ticking=True,
        changed_data=with_status("live"),
    ):
        page = current.page
        assert "Ao vivo" in card(page).inner_text()
        page.clock.run_for(30 * MINUTE)  # three hours after kickoff
        text = card(page).inner_text()
        assert "Provavelmente encerrado" in text
        assert "Ao vivo" not in text  # the stale label is hidden


@pytest.mark.parametrize("status", ["finished", "postponed", "cancelled"])
def test_a_match_that_is_over_or_off_never_gets_a_clock(
    browser: Browser, origin: str, status: str
) -> None:
    for current in visit(
        browser,
        origin,
        path=WEEK,
        now="2026-11-03T21:00:00Z",
        ticking=True,
        changed_data=with_status(status),
    ):
        page = current.page
        for hours in (0, 1, 1, 3):  # 21:00, 22:00, 23:00, 02:00
            page.clock.run_for(hours * HOUR)
            assert card(page).locator(".clock").count() == 0, f"{status} at +{hours}h"


# --- the page ------------------------------------------------------------------------------------


def test_a_tab_in_the_background_does_nothing_and_catches_up_when_it_returns(
    browser: Browser, origin: str
) -> None:
    for current in at(browser, origin, "2026-11-03T19:30:00Z"):
        page = current.page
        hide = "Object.defineProperty(document, 'hidden', {value: true, configurable: true})"
        show = (
            "Object.defineProperty(document, 'hidden', {value: false, configurable: true});"
            "document.dispatchEvent(new Event('visibilitychange'))"
        )
        page.evaluate(hide)
        page.clock.run_for(HOUR)
        assert clock(page) == "Começa em 2 h 30 min"  # nobody was looking, nothing was done
        page.evaluate(show)
        assert clock(page) == "Começa em 1 h 30 min"  # caught up at once


def test_switching_lists_keeps_the_clock_on_the_cards(browser: Browser, origin: str) -> None:
    for current in at(browser, origin, "2026-11-03T19:30:00Z"):
        page = current.page
        page.get_by_role("button", name="Hoje", exact=True).click()
        assert clock(page) == "Começa em 2 h 30 min"
        page.get_by_role("button", name="Esta semana", exact=True).click()
        assert clock(page) == "Começa em 2 h 30 min"


def test_the_clock_does_not_move_the_cards_around(browser: Browser, origin: str) -> None:
    for current in at(browser, origin, "2026-11-03T21:00:00Z"):
        page = current.page
        before = page.locator(".match-card__teams").all_inner_texts()
        page.clock.run_for(4 * HOUR)
        assert page.locator(".match-card__teams").all_inner_texts() == before


# --- motion --------------------------------------------------------------------------------------


def test_the_live_pulse_is_off_when_motion_is_reduced(browser: Browser, origin: str) -> None:
    script = "e => getComputedStyle(e).animationName"
    for current in at(browser, origin, "2026-11-03T22:10:00Z"):
        assert card(current.page).locator(".live-dot").evaluate(script) == "live-pulse"
    for current in at(browser, origin, "2026-11-03T22:10:00Z", reduced_motion="reduce"):
        assert card(current.page).locator(".live-dot").evaluate(script) == "none"


def test_the_pulse_of_a_match_the_data_calls_live_is_off_too(browser: Browser, origin: str) -> None:
    script = "e => getComputedStyle(e).animationName"
    options: dict[str, Any] = {"changed_data": with_status("live"), "reduced_motion": "reduce"}
    for current in visit(
        browser, origin, path=WEEK, now="2026-11-03T22:10:00Z", ticking=True, **options
    ):
        assert card(current.page).locator(".live-dot").evaluate(script) == "none"


# --- the whole page ------------------------------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize(
    ("moment", "status"),
    [
        ("2026-11-03T19:30:00Z", "scheduled"),  # counting down
        ("2026-11-03T22:10:00Z", "scheduled"),  # on, by the clock
        ("2026-11-03T22:10:00Z", "live"),  # on, and the data says so
        ("2026-11-04T02:00:00Z", "live"),  # the data still says live, long after
    ],
)
def test_axe_finds_nothing_in_any_phase(
    browser: Browser, origin: str, scheme: str, size: str, moment: str, status: str
) -> None:
    options: dict[str, Any] = {"changed_data": with_status(status)}
    for current in visit(
        browser, origin, scheme, size, path=WEEK, now=moment, ticking=True, **options
    ):
        assert card(current.page).get_attribute("data-phase") is not None
        current.page.clock.resume()  # axe waits on timers, which a paused clock never fires
        assert axe_violations(current.page) == []
