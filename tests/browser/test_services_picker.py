"""The services picker (FR-21): checkboxes for each subscription, saved with the other choices."""

import json

import pytest
from playwright.sync_api import Browser, Locator, Page, expect
from site_browser import STORAGE_KEY, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

SERVICES = [
    "TV por assinatura (cabo, satélite ou operadora)",
    "Premiere (pay-per-view)",
    "Globoplay",
    "Disney+ (plano com ESPN)",
]
NONE_CHOSEN = "Nenhum serviço marcado: vamos considerar só a TV aberta e o YouTube."


def box(page: Page, name: str) -> Locator:
    return page.get_by_role("checkbox", name=name)


def saved(page: Page) -> dict[str, list[str]]:
    stored = page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')")
    return json.loads(stored) if stored else {}


def ticked(page: Page) -> list[str]:
    names: list[str] = page.locator("#service-options input:checked").evaluate_all(
        "boxes => boxes.map(b => b.value)"
    )
    return names


def test_every_service_of_the_catalogue_is_offered_with_what_it_includes(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        labels = page.locator("#service-options label").all_inner_texts()
        assert labels == SERVICES
        assert page.locator("#service-premiere-includes").inner_text() == "Inclui: Premiere."
        assert (
            page.locator("#service-tv-por-assinatura-includes").inner_text()
            == "Inclui: SporTV e ESPN."
        )
        assert (
            page.locator("#service-disney-plus-includes").inner_text() == "Inclui: Disney+ e ESPN."
        )


def test_nothing_is_ticked_by_default_and_the_page_says_what_that_means(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert ticked(page) == []
        assert page.locator("#services-summary").inner_text() == NONE_CHOSEN
        assert (
            "TV aberta e YouTube não precisam de assinatura"
            in page.locator("#services-hint").inner_text()
        )


def test_ticking_a_service_saves_it_and_says_how_many(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        box(page, "Globoplay").check()
        assert saved(page)["services"] == ["globoplay"]
        assert page.locator("#services-summary").inner_text() == "1 serviço marcado."
        box(page, "Premiere (pay-per-view)").check()
        assert saved(page)["services"] == ["premiere", "globoplay"]  # in catalogue order
        assert page.locator("#services-summary").inner_text() == "2 serviços marcados."
        box(page, "Globoplay").uncheck()
        assert saved(page)["services"] == ["premiere"]
        box(page, "Premiere (pay-per-view)").uncheck()
        assert saved(page)["services"] == []
        assert page.locator("#services-summary").inner_text() == NONE_CHOSEN


def test_services_and_teams_are_saved_together_and_neither_loses_the_other(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator("#team-search").focus()
        page.fill("#team-search", "palm")
        page.keyboard.press("Enter")
        box(page, "Globoplay").check()
        assert saved(page) == {"version": 1, "teams": ["palmeiras"], "services": ["globoplay"]}
        page.get_by_role("button", name="Remover Palmeiras").click()
        assert saved(page) == {"version": 1, "teams": [], "services": ["globoplay"]}


def test_the_keyboard_ticks_a_service_with_space(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.locator("#service-tv-por-assinatura").focus()
        page.keyboard.press("Space")
        assert ticked(page) == ["tv-por-assinatura"]
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.id") == "service-premiere"
        page.keyboard.press("Space")
        assert ticked(page) == ["tv-por-assinatura", "premiere"]


def test_a_checkbox_has_a_name_and_a_description_for_a_screen_reader(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        disney = box(page, "Disney+ (plano com ESPN)")
        assert disney.get_attribute("aria-describedby") == "service-disney-plus-includes"
        tree = page.locator("section[aria-labelledby=services-title]").aria_snapshot()
        assert 'group "Quais serviços você tem?"' in tree
        assert 'checkbox "Globoplay"' in tree


def test_the_choices_survive_a_reload_and_reset_clears_them(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        box(page, "Disney+ (plano com ESPN)").check()
        page.reload()
        page.wait_for_selector("html[data-ready='true']")
        assert ticked(page) == ["disney-plus"]
        assert page.locator("#services-summary").inner_text() == "1 serviço marcado."

        page.get_by_role("button", name="Apagar meus dados").click()
        assert ticked(page) == []
        assert page.locator("#services-summary").inner_text() == NONE_CHOSEN
        assert page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')") is None


def test_a_saved_service_the_data_no_longer_has_is_ignored(browser: Browser, origin: str) -> None:
    value = {STORAGE_KEY: '{"version": 1, "teams": [], "services": ["gone-tv", "globoplay"]}'}
    for current in visit(browser, origin, saved=value):
        assert ticked(current.page) == ["globoplay"]
        assert current.console == []


def test_the_summary_is_spoken_when_it_changes(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert page.locator("#services-summary").get_attribute("role") == "status"
        box(page, "Premiere (pay-per-view)").check()
        expect(page.locator("#services-summary")).to_have_text("1 serviço marcado.")


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_with_services_ticked(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(browser, origin, scheme, size):
        page = current.page
        box(page, "Globoplay").check()
        box(page, "Disney+ (plano com ESPN)").check()
        assert axe_violations(page) == []
        page.locator("#service-premiere").focus()
        assert axe_violations(page) == []


def test_ticked_choices_never_leave_the_browser(browser: Browser, origin: str) -> None:
    """Ticking sends nothing at all, and no request ever names a chosen service."""
    for current in visit(browser, origin):
        page = current.page
        before = len(current.details)
        box(page, "Globoplay").check()
        box(page, "Premiere (pay-per-view)").check()
        page.get_by_role("button", name="Apagar meus dados").click()
        assert len(current.details) == before, "ticking and resetting make no request"
        for request in current.details:
            text = " ".join([request.url, str(request.post_data), json.dumps(request.headers)])
            assert "globoplay" not in text and "premiere" not in text.replace("premiere.json", "")
            assert request.method == "GET" and request.post_data is None and "?" not in request.url
