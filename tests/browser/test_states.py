"""Loading, offline, empty and error screens, and the saved copy (FR-32).

Every screen the visitor can end up on besides the lists: waiting for the data, no connection, a
server that fails, a page older than its data, no data yet, something unexpected, and the data of
the last good load shown when the new one fails.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Browser, Page, Route
from site_browser import (
    CHOICES,
    DATA,
    SECRET_TEAM,
    VIEWPORTS,
    axe_violations,
    open_settings,
    visit,
)

pytestmark = pytest.mark.browser

DATA_FILES = "**/data/*.json"
RETRY = "Tentar de novo"
WEEK = "/index.html?view=week"
WEEK_MATCHES = 5


def refuse_the_data(page: Page) -> None:
    """The data files cannot be reached, as when there is no connection."""
    page.route(DATA_FILES, lambda route: route.abort("internetdisconnected"))


def fail_the_data(page: Page) -> None:
    page.route(DATA_FILES, lambda route: route.fulfill(status=503))


def allow_the_data(page: Page) -> None:
    page.unroute(DATA_FILES)


def holding(held: list[Route]) -> Callable[[Page], None]:
    def hold(page: Page) -> None:
        page.route(DATA_FILES, lambda route: held.append(route))

    return hold


def status_with(last_success: str | None) -> dict[str, dict[str, Any]]:
    document = json.loads(Path(DATA / "status.json").read_text(encoding="utf-8"))
    document["last_success_at"] = last_success
    return {"status": document}


def panel(page: Page) -> str:
    return page.locator("#state-panel").inner_text()


def kind(page: Page) -> str | None:
    return page.locator("#state-panel").get_attribute("data-kind")


def titles(page: Page) -> list[str]:
    return page.locator("#matches-list .match-card__teams").all_inner_texts()


def reload_without_the_data(page: Page, how: Callable[[Page], None] = refuse_the_data) -> None:
    how(page)
    page.reload()
    page.wait_for_selector("html[data-ready='true']")


# --- loading -------------------------------------------------------------------------------------


def test_while_the_data_is_on_its_way_there_is_a_loading_screen(
    browser: Browser, origin: str
) -> None:
    held: list[Route] = []
    for current in visit(browser, origin, wait_ready=False, before_open=holding(held)):
        page = current.page
        page.locator("#matches-loading").wait_for(state="visible")
        assert page.locator("#matches-loading").inner_text() == "Carregando os jogos…"
        assert page.locator("#matches-section").get_attribute("aria-busy") == "true"
        assert page.locator(".skeleton").get_attribute("aria-hidden") == "true"
        assert page.locator("#matches-loading").get_attribute("role") == "status"
        # Nothing that needs the data is offered yet.
        assert not page.locator("#matches-content").is_visible()
        assert not page.locator("#state-panel").is_visible()
        assert not page.locator("#reopen-onboarding").is_visible()
        assert not page.locator("#service-options").is_visible()
        # The page is usable meanwhile: the footer, the reset control.
        open_settings(page)
        assert page.get_by_role("button", name="Apagar meus dados").is_visible()
        while len(held) < 5:
            page.wait_for_timeout(50)
        for route in held:
            route.continue_()
        page.wait_for_selector("html[data-ready='true']")
        assert page.locator("#matches-section").get_attribute("aria-busy") == "false"
        assert not page.locator("#matches-loading").is_visible()
        assert page.locator("#matches-content").is_visible()
        open_settings(page)
        assert page.locator("#reopen-onboarding").is_visible()


def test_the_loading_cards_shimmer_but_not_when_motion_is_reduced(
    browser: Browser, origin: str
) -> None:
    script = "e => getComputedStyle(e).animationName"
    held: list[Route] = []
    for current in visit(browser, origin, wait_ready=False, before_open=holding(held)):
        card = current.page.locator(".skeleton__card").first
        card.wait_for(state="visible")
        assert card.evaluate(script) == "skeleton-shimmer"
    for current in visit(
        browser, origin, reduced_motion="reduce", wait_ready=False, before_open=holding(held)
    ):
        card = current.page.locator(".skeleton__card").first
        card.wait_for(state="visible")
        assert card.evaluate(script) == "none"


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_on_the_loading_screen(
    browser: Browser, origin: str, scheme: str
) -> None:
    held: list[Route] = []
    for current in visit(browser, origin, scheme, wait_ready=False, before_open=holding(held)):
        current.page.locator("#matches-loading").wait_for(state="visible")
        assert axe_violations(current.page) == []


# --- offline and errors --------------------------------------------------------------------------


def test_without_a_connection_the_page_says_so_and_offers_to_try_again(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, before_open=refuse_the_data):
        page = current.page
        assert kind(page) == "offline"
        assert panel(page).startswith("Sem conexão com os jogos")
        assert "Quando a conexão voltar, tentamos de novo sozinhos." in panel(page)
        assert page.locator("#state-panel").get_attribute("role") == "alert"
        assert page.get_by_role("button", name=RETRY).is_visible()
        link = page.locator("#state-panel").get_by_role("link", name="Avisar o projeto no GitHub")
        assert urlparse(link.get_attribute("href") or "").path == "/raissonls/ubi-ludus/issues/new"
        assert link.get_attribute("rel") == "noopener noreferrer"
        # Nothing that needs the data is offered, and no stale indicator is made up.
        assert not page.locator("#matches-content").is_visible()
        assert not page.locator("#reopen-onboarding").is_visible()
        assert not page.locator("#freshness").is_visible()


def test_trying_again_loads_the_lists_once_the_connection_is_back(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=WEEK, before_open=refuse_the_data):
        page = current.page
        assert kind(page) == "offline"
        allow_the_data(page)
        page.get_by_role("button", name=RETRY).click()
        page.locator("#matches-content").wait_for(state="visible")
        assert len(titles(page)) == WEEK_MATCHES
        assert not page.locator("#state-panel").is_visible()
        assert page.locator("#freshness").is_visible()


def test_the_retry_button_keeps_the_keyboard_users_place(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, before_open=fail_the_data):
        page = current.page
        button = page.get_by_role("button", name=RETRY)
        button.focus()
        page.keyboard.press("Enter")  # still failing: the screen comes back
        page.locator("#state-panel").wait_for(state="visible")
        assert page.evaluate("document.activeElement.id") == "matches-title"


def test_when_the_connection_comes_back_by_itself_the_page_tries_again(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=WEEK, before_open=refuse_the_data):
        page = current.page
        assert kind(page) == "offline"
        allow_the_data(page)
        page.evaluate("window.dispatchEvent(new Event('online'))")
        page.locator("#matches-content").wait_for(state="visible")
        assert len(titles(page)) == WEEK_MATCHES


def test_a_server_that_fails_gets_its_own_words(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, before_open=fail_the_data):
        page = current.page
        assert kind(page) == "error"
        assert panel(page).startswith("Não foi possível carregar os jogos")
        assert "Tente de novo em alguns minutos." in panel(page)
        assert page.get_by_role("button", name=RETRY).is_visible()


def test_a_file_that_is_not_what_the_page_reads_is_an_error_too(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, changed_data={"teams": {"schema_version": "1.0"}}):
        assert kind(current.page) == "error"  # no "teams" list


def test_a_page_older_than_its_data_asks_to_be_reloaded(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, newer_format="teams"):
        page = current.page
        assert kind(page) == "outdated"
        assert panel(page).startswith("Esta página ficou desatualizada")
        assert page.get_by_role("button", name="Recarregar a página").is_visible()
        assert page.get_by_role("button", name=RETRY).count() == 0  # trying again cannot help
        with page.expect_navigation():
            page.get_by_role("button", name="Recarregar a página").click()


def test_something_unexpected_gets_a_screen_and_not_a_blank_page(
    browser: Browser, origin: str
) -> None:
    broken = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    broken["matches"][0]["kickoff_utc"] = "not a date"
    for current in visit(browser, origin, changed_data={"matches": broken}):
        page = current.page
        assert kind(page) == "unexpected"
        assert panel(page).startswith("Algo deu errado")
        assert page.get_by_role("button", name="Recarregar a página").is_visible()
        assert any("Not a date" in line for line in current.console)


# --- no data yet ---------------------------------------------------------------------------------


def test_data_with_no_matches_is_a_calm_screen_of_its_own(browser: Browser, origin: str) -> None:
    empty = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    empty["matches"] = []
    for current in visit(browser, origin, changed_data={"matches": empty}):
        page = current.page
        assert kind(page) == "empty"
        assert panel(page).startswith("Ainda não há jogos publicados")
        assert page.locator("#state-panel").get_attribute("role") == "status"
        assert page.locator("#freshness").is_visible()  # the data is there, and its age is known
        assert not page.locator("#matches-content").is_visible()
        assert page.locator("#state-panel").get_by_role("link").count() == 0  # nothing broke


def test_the_empty_screen_can_look_again(browser: Browser, origin: str) -> None:
    empty = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    empty["matches"] = []
    for current in visit(browser, origin, path=WEEK, changed_data={"matches": empty}):
        page = current.page
        page.unroute("**/data/matches.json")  # the pipeline has published matches since
        page.get_by_role("button", name=RETRY).click()
        page.locator("#matches-content").wait_for(state="visible")
        assert len(titles(page)) == WEEK_MATCHES


# --- the copy kept from the last good load --------------------------------------------------------


def test_when_the_load_fails_the_last_good_data_is_shown_with_a_notice(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=WEEK):
        page = current.page
        assert len(titles(page)) == WEEK_MATCHES
        assert not page.locator("#saved-notice").is_visible()
        reload_without_the_data(page)
        assert len(titles(page)) == WEEK_MATCHES
        notice = page.locator("#saved-notice")
        assert notice.is_visible()
        assert notice.inner_text().startswith("Não conseguimos atualizar os jogos agora.")
        assert notice.get_attribute("role") == "status"
        assert not page.locator("#state-panel").is_visible()
        open_settings(page)
        assert page.locator("#reopen-onboarding").is_visible()  # the page works on the copy
        assert page.locator("#freshness").get_attribute("data-state") == "fresh"


def test_a_server_error_falls_back_to_the_copy_as_well(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=WEEK):
        reload_without_the_data(current.page, fail_the_data)
        assert len(titles(current.page)) == WEEK_MATCHES
        assert current.page.locator("#saved-notice").is_visible()


def test_an_old_copy_is_shown_with_the_freshness_warning(browser: Browser, origin: str) -> None:
    old = status_with("2026-10-28T09:00:00Z")
    for current in visit(browser, origin, path=WEEK, changed_data=old):
        page = current.page
        reload_without_the_data(page)
        assert len(titles(page)) == WEEK_MATCHES
        assert page.locator("#saved-notice").is_visible()
        warning = page.locator("#freshness")
        assert warning.get_attribute("data-state") == "stale"
        assert warning.inner_text().startswith("⚠ Dados possivelmente desatualizados.")


def test_a_choice_survives_a_failed_load_and_the_copy_shows_the_followed_teams(
    browser: Browser, origin: str
) -> None:
    saved = {
        "ubi-ludus:preferences": json.dumps({"version": 1, "teams": ["palmeiras"], "services": []})
    }
    for current in visit(browser, origin, saved=saved):
        page = current.page
        assert titles(page) == ["Palmeiras x Flamengo"]
        reload_without_the_data(page)
        assert titles(page) == ["Palmeiras x Flamengo"]


def test_the_copy_holds_the_published_data_and_nothing_about_the_visitor(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, saved=CHOICES):
        page = current.page
        kept = page.evaluate(
            """async () => {
                const out = {};
                for (const name of await caches.keys()) {
                    const cache = await caches.open(name);
                    for (const request of await cache.keys()) {
                        out[request.url] = await (await cache.match(request)).text();
                    }
                }
                return out;
            }"""
        )
        assert sorted(urlparse(url).path for url in kept) == [
            f"/data/{name}.json"
            for name in ("broadcasters", "competitions", "matches", "status", "teams")
        ]
        assert all(SECRET_TEAM not in body for body in kept.values())
        assert page.evaluate("caches.keys()") == ["ubi-ludus-data-v1"]


def test_without_cache_storage_the_page_works_and_a_failed_load_is_an_error(
    browser: Browser, origin: str
) -> None:
    def no_cache_storage(page: Page) -> None:
        page.add_init_script("Object.defineProperty(window, 'caches', { value: undefined });")

    for current in visit(browser, origin, path=WEEK, before_open=no_cache_storage):
        page = current.page
        assert len(titles(page)) == WEEK_MATCHES
        assert current.console == []
        reload_without_the_data(page)
        assert kind(page) == "offline"


def test_a_copy_that_no_longer_fits_the_site_is_not_shown(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.evaluate(
            """async () => {
                const cache = await caches.open('ubi-ludus-data-v1');
                const request = (await cache.keys()).find((r) => r.url.endsWith('/matches.json'));
                await cache.put(request, new Response(JSON.stringify({ schema_version: '0.1' })));
            }"""
        )
        reload_without_the_data(page)
        assert kind(page) == "offline"


# --- the whole page ------------------------------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("how", ["offline", "error", "outdated", "empty", "unexpected", "saved"])
def test_axe_finds_nothing_on_any_screen(
    browser: Browser, origin: str, scheme: str, size: str, how: str
) -> None:
    empty = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    broken = json.loads(json.dumps(empty))
    empty["matches"] = []
    broken["matches"][0]["kickoff_utc"] = "not a date"
    choices: dict[str, dict[str, Any]] = {
        "offline": {"before_open": refuse_the_data},
        "error": {"before_open": fail_the_data},
        "outdated": {"newer_format": "teams"},
        "empty": {"changed_data": {"matches": empty}},
        "unexpected": {"changed_data": {"matches": broken}},
        "saved": {"path": WEEK},
    }
    for current in visit(browser, origin, scheme, size, **choices[how]):
        if how == "saved":
            reload_without_the_data(current.page)
            assert current.page.locator("#saved-notice").is_visible()
        assert axe_violations(current.page) == []
