"""Add to calendar (FR-28): one match, or every upcoming match of the followed teams.

The downloaded files are read back with the `icalendar` library, a strict RFC 5545 parser of the
kind calendar apps are built on, and checked byte by byte for the rules apps are picky about:
CRLF line ends, lines of at most 75 octets, escaped text.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from icalendar import Calendar
from playwright.sync_api import Browser, Page
from site_browser import (
    DATA,
    STORAGE_KEY,
    VIEWPORTS,
    WATCH_VIOLATIONS,
    axe_violations,
    open_details,
    open_settings,
    visit,
)

pytestmark = pytest.mark.browser

WEEK = "/index.html?view=week"
ADD = "Adicionar ao calendário"


def following(*teams: str) -> dict[str, str]:
    return {STORAGE_KEY: json.dumps({"version": 1, "teams": list(teams), "services": []})}


def watch_violations(page: Page) -> None:
    page.add_init_script(WATCH_VIOLATIONS)


def save_file(page: Page, click: Callable[[], None]) -> tuple[str, bytes]:
    with page.expect_download() as download:
        click()
    return download.value.suggested_filename, Path(download.value.path()).read_bytes()


def add_button(page: Page, teams: str) -> Any:
    sheet = open_details(page, teams.split(" x ")[0])
    return sheet.get_by_role("button", name=f"{ADD} de {teams}")


def parse(raw: bytes) -> Calendar:
    return Calendar.from_ical(raw)


def events(calendar: Calendar) -> list[Any]:
    return list(calendar.walk("VEVENT"))


# --- one match -----------------------------------------------------------------------------------


def test_a_match_downloads_as_a_calendar_with_that_one_event(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=WEEK):
        page = current.page
        name, raw = save_file(page, add_button(page, "Palmeiras x Flamengo").click)
        assert name == "ubi-ludus-fx-1.ics"
        calendar = parse(raw)
        assert calendar["VERSION"] == "2.0"
        assert str(calendar["PRODID"]).startswith("-//Ubi Ludus//")
        [event] = events(calendar)
        assert str(event["UID"]) == "fx-1@ubi-ludus"
        assert str(event["SUMMARY"]) == "Palmeiras x Flamengo"
        start = event["DTSTART"].dt
        assert start == datetime(2026, 11, 3, 22, 0, tzinfo=UTC)  # the kickoff, in UTC
        assert event["DTEND"].dt - start == datetime(2026, 11, 4, 0, 0, tzinfo=UTC) - start
        assert event["DTSTAMP"].dt == datetime(2026, 11, 2, 12, 0, tzinfo=UTC)  # the page's clock
        assert str(event["URL"]) == f"{origin}/index.html"
        description = str(event["DESCRIPTION"])
        assert description.startswith("Campeonato Brasileiro Série A · Rodada 34\n")
        assert (
            "Onde assistir: SporTV (pela tabela de direitos), TV Globo (pela tabela de direitos)."
            in description
        )
        assert "Confira a emissora perto do jogo." in description


def test_the_file_follows_the_rules_calendar_apps_are_picky_about(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=WEEK):
        page = current.page
        _, raw = save_file(page, add_button(page, "Palmeiras x Flamengo").click)
        assert not raw.startswith(b"\xef\xbb\xbf")  # no byte order mark
        assert raw.startswith(b"BEGIN:VCALENDAR\r\n") and raw.endswith(b"END:VCALENDAR\r\n")
        assert b"\n" not in raw.replace(b"\r\n", b"")  # every line break is CRLF
        lines = raw.split(b"\r\n")[:-1]
        assert all(len(line) <= 75 for line in lines), [
            len(line) for line in lines if len(line) > 75
        ]
        raw.decode("utf-8")  # valid UTF-8


def test_a_match_with_no_known_broadcaster_names_none_in_the_file(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=WEEK):
        page = current.page
        _, raw = save_file(page, add_button(page, "Real Madrid x Barça").click)
        [event] = events(parse(raw))
        description = str(event["DESCRIPTION"])
        assert "Transmissão ainda não confirmada" in description
        assert "Onde assistir" not in description
        assert not [b for b in ("Globo", "SporTV", "ESPN", "Premiere") if b in description]


def test_the_button_names_its_match_and_works_from_the_keyboard(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=WEEK):
        page = current.page
        button = add_button(page, "São Paulo x Atlético-MG")
        assert button.count() == 1
        button.focus()
        name, _ = save_file(page, partial(page.keyboard.press, "Enter"))
        assert name == "ubi-ludus-fx-4.ics"
        assert page.locator("#calendar-status").inner_text() == "Arquivo do calendário baixado."


def test_matches_that_are_over_or_off_have_no_calendar_button(
    browser: Browser, origin: str
) -> None:
    document = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    for match in document["matches"]:
        if match["id"] == "fx-1":
            match["status"] = "cancelled"
    for current in visit(browser, origin, path=WEEK, changed_data={"matches": document}):
        page = current.page
        assert page.locator(".match-card--poster").count() == 5
        # The button is in the details of each match that is still on, and not in a cancelled one.
        assert (
            open_details(page, "Palmeiras").get_by_role("button", name=ADD, exact=False).count()
            == 0
        )
        assert (
            open_details(page, "Real Madrid").get_by_role("button", name=ADD, exact=False).count()
            == 1
        )


# --- text from the data is escaped ----------------------------------------------------------------


def test_names_that_try_to_break_the_file_stay_inside_one_property(
    browser: Browser, origin: str
) -> None:
    teams = json.loads(Path(DATA / "teams.json").read_text(encoding="utf-8"))
    for team in teams["teams"]:
        if team["id"] == "palmeiras":
            hostile = "Time\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:Falso; com, vírgula \\ e barra"
            team["name"] = team["short_name"] = hostile
    for current in visit(browser, origin, path=WEEK, changed_data={"teams": teams}):
        page = current.page
        button = open_details(page, "Flamengo").locator(".match-card__calendar")
        _, raw = save_file(page, button.click)
        lines = raw.split(b"\r\n")
        assert lines.count(b"BEGIN:VEVENT") == 1 and lines.count(b"END:VEVENT") == 1
        [event] = events(parse(raw))
        summary = str(event["SUMMARY"])
        assert (
            "END:VEVENT" in summary and "Falso; com, vírgula \\ e barra" in summary
        )  # kept as text


# --- the followed teams ---------------------------------------------------------------------------


def test_all_the_followed_teams_matches_download_as_one_calendar(
    browser: Browser, origin: str
) -> None:
    saved = following("palmeiras", "real-madrid", "chelsea")
    for current in visit(browser, origin, saved=saved):
        page = current.page
        open_settings(page)
        button = page.get_by_role("button", name="Baixar calendário dos meus times (3 jogos)")
        assert button.is_visible()
        name, raw = save_file(page, button.click)
        assert name == "ubi-ludus-meus-times.ics"
        calendar = parse(raw)
        assert str(calendar["X-WR-CALNAME"]) == "Ubi Ludus: jogos dos meus times"
        found = events(calendar)
        assert [str(e["UID"]) for e in found] == [
            "fx-1@ubi-ludus",
            "fx-2@ubi-ludus",
            "fx-3@ubi-ludus",
        ]
        assert [e["DTSTART"].dt for e in found] == sorted(e["DTSTART"].dt for e in found)
        assert (
            page.locator("#calendar-status").inner_text()
            == "Arquivo do calendário baixado com 3 jogos."
        )


def test_it_ignores_the_filters_of_the_list(browser: Browser, origin: str) -> None:
    saved = following("palmeiras", "real-madrid")
    for current in visit(
        browser, origin, path=f"{WEEK}&competition=brasileirao-serie-a", saved=saved
    ):
        page = current.page
        shown = page.locator("#matches-list .match-card__teams").all_inner_texts()
        assert shown == ["Palmeiras x Flamengo", "São Paulo x Atlético-MG"]  # the Brasileirão only
        open_settings(page)
        _, raw = save_file(page, page.locator("#calendar-all").click)
        # The calendar is of the followed teams, whatever the list shows.
        assert [str(e["UID"]) for e in events(parse(raw))] == ["fx-1@ubi-ludus", "fx-2@ubi-ludus"]


def test_one_match_reads_in_the_singular(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=following("brasil")):
        open_settings(current.page)
        button = current.page.get_by_role(
            "button", name="Baixar calendário dos meus times (1 jogo)"
        )
        assert button.is_visible()


def test_without_followed_teams_there_is_no_calendar_of_them(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        open_settings(current.page)
        assert not current.page.locator("#calendar-all").is_visible()
        assert not current.page.locator("#calendar-all-row").is_visible()


def test_the_followed_calendar_follows_the_choices_as_they_change(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        open_settings(page)
        page.fill("#team-search", "palm")
        page.keyboard.press("Enter")
        assert (
            page.locator("#calendar-all").inner_text()
            == "Baixar calendário dos meus times (1 jogo)"
        )
        page.get_by_role("button", name="Remover Palmeiras").click()
        assert not page.locator("#calendar-all-row").is_visible()


# --- nothing leaves the page ----------------------------------------------------------------------


def test_saving_a_calendar_sends_nothing_and_breaks_no_security_rule(
    browser: Browser, origin: str
) -> None:
    for current in visit(
        browser, origin, saved=following("palmeiras"), before_open=watch_violations
    ):
        page = current.page
        before = len(current.requests)
        open_settings(page)
        save_file(page, page.locator("#calendar-all").click)
        save_file(page, add_button(page, "Palmeiras x Flamengo").click)
        later = [r for r in current.requests[before:] if not r.endswith("/assets/favicon.svg")]
        assert all(r.startswith("blob:") for r in later), later  # the file is made on the page
        assert page.evaluate("window.__violations") == []
        assert current.console == []


def test_the_files_say_nothing_about_the_visitors_choices(browser: Browser, origin: str) -> None:
    record = {
        "version": 1,
        "teams": ["palmeiras"],
        "services": ["globoplay"],
        "onlyWatchable": True,
    }
    for current in visit(browser, origin, saved={STORAGE_KEY: json.dumps(record)}):
        page = current.page
        open_settings(page)
        _, raw = save_file(page, page.locator("#calendar-all").click)
        text = raw.decode("utf-8").lower()
        assert "globoplay" not in text and "onlywatchable" not in text and "preferences" not in text


# --- the whole page ------------------------------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_with_the_calendar_buttons(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    saved = following("palmeiras", "real-madrid")
    for current in visit(browser, origin, scheme, size, path=WEEK, saved=saved):
        page = current.page
        open_settings(page)
        assert page.locator("#calendar-all").is_visible()
        assert axe_violations(page) == []
        save_file(page, page.locator("#calendar-all").click)
        assert axe_violations(page) == []
