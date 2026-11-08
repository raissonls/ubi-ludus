"""The header with the logo and the settings button, the strip with the visitor's teams, and the
settings panel that holds the teams, the services and the filters (they used to be a form at the end
of the page)."""

import json

import pytest
from playwright.sync_api import Browser, Page, expect
from site_browser import STORAGE_KEY, VIEWPORTS, axe_violations, open_settings, visit

pytestmark = pytest.mark.browser

PANEL = "#settings"


def saved(teams: list[str], services: list[str] | None = None) -> dict[str, str]:
    record = {"version": 1, "teams": teams, "services": services or []}
    return {STORAGE_KEY: json.dumps(record)}


# --- the header ---------------------------------------------------------------------------------


def test_the_header_has_the_logo_the_name_and_a_settings_button(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        logo = page.locator(".site-header .brand__logo")
        assert logo.get_attribute("src") == "assets/logo.svg"
        assert logo.get_attribute("alt") == ""  # the name beside it says it
        assert page.locator(".site-header .brand__name").inner_text() == "Ubi Ludus"
        button = page.locator("#settings-open")
        assert button.get_attribute("aria-label") == "Abrir os ajustes"
        assert button.get_attribute("aria-haspopup") == "dialog"
        box = button.bounding_box()
        assert box is not None and box["width"] >= 44 and box["height"] >= 44


def test_the_header_stays_at_the_top_while_the_page_scrolls(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, size="mobile", saved=saved(["palmeiras"])):
        page = current.page
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(200)
        top = page.evaluate("document.querySelector('.site-header').getBoundingClientRect().top")
        assert top == 0


def test_the_logo_is_the_icon_of_the_site_too(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        href = current.page.locator("link[rel=icon]").get_attribute("href")
        assert href == "assets/favicon.svg"


# --- the strip with the visitor's teams ----------------------------------------------------------


def test_the_strip_shows_the_teams_and_the_services_the_visitor_chose(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras", "flamengo"], ["globoplay"])):
        page = current.page
        strip = page.locator("#team-strip")
        assert page.locator("#team-strip-teams").inner_text() == "Palmeiras e Flamengo"
        assert "Globoplay" in page.locator("#team-strip-services").inner_text()
        assert strip.locator(".strip__shirt").count() == 2
        assert strip.get_attribute("aria-haspopup") == "dialog"


def test_the_strip_names_two_and_counts_the_rest(browser: Browser, origin: str) -> None:
    for current in visit(
        browser, origin, saved=saved(["palmeiras", "flamengo", "sao-paulo", "real-madrid"])
    ):
        assert current.page.locator("#team-strip-teams").inner_text() == (
            "Palmeiras, Flamengo e mais 2"
        )
        assert (
            current.page.locator("#team-strip .strip__shirt").count() == 3
        )  # three shirts at most


def test_without_teams_the_strip_asks_to_choose_and_opens_the_first_run_choice(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert page.locator("#team-strip-teams").inner_text() == "Escolha seus times"
        page.click("#team-strip")
        expect(page.locator("#onboarding")).to_be_visible()
        assert "De que parte do mundo" in page.locator("#onboarding .ob__title").inner_text()


def test_pressing_the_strip_opens_the_settings(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        current.page.click("#team-strip")
        expect(current.page.locator(PANEL)).to_be_visible()


# --- the settings panel -------------------------------------------------------------------------


def test_the_settings_hold_the_teams_the_services_the_filters_and_the_rest(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"], ["globoplay"])):
        page = current.page
        panel = open_settings(page)
        headings = [t.lower() for t in panel.locator("h3").all_inner_texts()]  # shown in capitals
        assert headings == ["meus times", "o que tenho em casa", "o que mostrar", "mais"]
        assert panel.locator("#team-search").is_visible()
        assert panel.locator("#only-watchable").is_visible()
        assert panel.locator("#filters").is_visible()
        assert panel.get_by_role("button", name="Adicionar times").is_visible()
        assert panel.get_by_role("button", name="Apagar meus dados").is_visible()


def test_the_page_no_longer_ends_with_the_pickers(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert page.locator("main > section.picker").count() == 0
        assert page.locator("main #team-search").count() == 0
        assert page.locator("main #service-options").count() == 0


def test_the_panel_closes_with_the_button_escape_or_a_press_outside_and_gives_the_focus_back(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        for how in ("button", "escape", "outside"):
            page.locator("#settings-open").focus()
            page.keyboard.press("Enter")
            expect(page.locator(PANEL)).to_be_visible()
            assert page.evaluate("document.activeElement.closest('#settings') !== null")
            if how == "button":
                page.click("#settings-close")
            elif how == "escape":
                page.keyboard.press("Escape")
            else:
                page.mouse.click(5, 300)  # the dim area, left of the panel
            expect(page.locator(PANEL)).to_be_hidden()
            assert page.evaluate("document.activeElement.id") == "settings-open"


def test_the_panel_is_modal_so_the_page_behind_cannot_be_reached(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        open_settings(page)
        assert page.evaluate("document.querySelector('#settings').matches(':modal')") is True


def test_the_settings_open_before_the_data_arrives(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, wait_ready=False):
        page = current.page
        page.wait_for_selector("#settings-open")
        page.click("#settings-open")
        expect(page.locator(PANEL)).to_be_visible()
        assert page.get_by_role("button", name="Apagar meus dados").is_visible()


def test_add_teams_closes_the_panel_and_opens_the_choice_with_the_current_teams_ticked(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=saved(["palmeiras"])):
        page = current.page
        open_settings(page)
        page.click("#reopen-onboarding")
        expect(page.locator(PANEL)).to_be_hidden()
        expect(page.locator("#onboarding")).to_be_visible()
        assert page.get_by_role("button", name="Continuar com 1 escolhido").is_visible()


def test_the_competition_chip_opens_the_settings_at_the_filters(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.click("#quick-filters [data-quick='competition']")
        expect(page.locator(PANEL)).to_be_visible()
        assert page.evaluate("document.activeElement.id") == "filter-competition"


def test_the_services_are_switches_that_a_screen_reader_still_reads_as_checkboxes(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, settings=True):
        page = current.page
        box = page.get_by_role("checkbox", name="Globoplay", exact=False).first
        assert box.evaluate("e => getComputedStyle(e).appearance") == "none"  # drawn as a switch
        before = box.evaluate("e => getComputedStyle(e).backgroundColor")
        box.check()
        assert box.evaluate("e => getComputedStyle(e).backgroundColor") != before


def test_the_footer_is_short_and_keeps_the_privacy_notice_and_the_attribution(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        lines = current.page.locator("footer").inner_text().splitlines()
        # The attribution football-data.org's terms ask for, as its own line (a whole line, not a
        # piece of text that merely contains a host name).
        assert "Football data provided by the Football-Data.org API" in lines
        assert any("cookies" in line for line in lines)  # the privacy notice
        assert "Apagar meus dados" not in lines  # it is in the settings now


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", list(VIEWPORTS))
def test_the_header_the_strip_and_the_settings_have_no_accessibility_violation(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(
        browser,
        origin,
        scheme=scheme,
        size=size,
        saved=saved(["palmeiras", "brasil"], ["globoplay"]),
        reduced_motion="reduce",
    ):
        page: Page = current.page
        assert axe_violations(page) == []
        open_settings(page)
        page.locator("#filters summary").click()
        assert axe_violations(page) == []
