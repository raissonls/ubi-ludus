"""Filters and shareable views (FR-27, FR-29).

The fixtures' clock is Monday 2 November 2026. "This week" lists all five matches that are to
come: Palmeiras x Flamengo (Brasileirão, Globo and SporTV), Real Madrid x Barça and Chelsea x
Atleti (Champions League, nothing known), São Paulo x Atlético-MG (Brasileirão, Globo) and Brasil
(friendly, nothing known).
"""

import json
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Browser, Page
from site_browser import STORAGE_KEY, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

BRASILEIRAO = "brasileirao-serie-a"
CHAMPIONS = "uefa-champions-league"
HOME = "/index.html"
WEEK = "?view=week"
TEXT_BOX = "Buscar time nos jogos"


def titles(page: Page) -> list[str]:
    return page.locator("#matches-list .match-card__teams").all_inner_texts()


def address(page: Page) -> str:
    """The page's address now. (page.url learns of a history.replaceState a moment later.)"""
    return str(page.evaluate("location.href"))


def params(page: Page) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(address(page)).query).items()}


def open_filters(page: Page) -> None:
    if not page.locator("#filters").evaluate("e => e.open"):
        page.locator("#filters-summary").click()


def saved_record(page: Page) -> dict[str, object] | None:
    text = page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')")
    return None if text is None else json.loads(text)


# --- the filters ---------------------------------------------------------------------------------


def test_the_filters_wait_closed_and_the_list_is_unfiltered(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=HOME + WEEK):
        page = current.page
        assert not page.locator("#filters").evaluate("e => e.open")
        assert page.locator("#filters-summary").inner_text() == "Filtros"
        assert len(titles(page)) == 5
        assert params(page) == {"view": "week"}


def test_the_competition_filter_narrows_the_list_and_the_address(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=HOME + WEEK):
        page = current.page
        open_filters(page)
        page.get_by_label("Competição").select_option(CHAMPIONS)
        assert titles(page) == ["Real Madrid x Barça", "Chelsea x Atleti"]
        assert params(page) == {"view": "week", "competition": CHAMPIONS}
        assert page.locator("#filters-summary").inner_text() == "Filtros (1)"


def test_the_broadcaster_filter_finds_only_matches_that_name_that_broadcaster(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=HOME + WEEK):
        page = current.page
        open_filters(page)
        page.get_by_label("Emissora").select_option("sportv")
        assert titles(page) == ["Palmeiras x Flamengo"]
        page.get_by_label("Emissora").select_option("globo")
        assert titles(page) == ["Palmeiras x Flamengo", "São Paulo x Atlético-MG"]


def test_the_team_search_ignores_accents_and_case_and_finds_short_names(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=HOME + WEEK):
        page = current.page
        open_filters(page)
        page.get_by_label(TEXT_BOX).fill("SAO paulo")
        assert titles(page) == ["São Paulo x Atlético-MG"]
        page.get_by_label(TEXT_BOX).fill("barca")
        assert titles(page) == ["Real Madrid x Barça"]
        assert params(page)["q"] == "barca"


def test_filters_combine_and_a_match_must_pass_all_of_them(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=HOME + WEEK):
        page = current.page
        open_filters(page)
        page.get_by_label("Competição").select_option(CHAMPIONS)
        page.get_by_label(TEXT_BOX).fill("chelsea")
        assert titles(page) == ["Chelsea x Atleti"]
        assert page.locator("#filters-summary").inner_text() == "Filtros (2)"
        page.get_by_label("Competição").select_option(BRASILEIRAO)
        assert titles(page) == []
        assert (
            page.locator("#matches-empty").inner_text()
            == "Nenhum jogo desta lista com esses filtros."
        )


def test_they_also_combine_with_the_only_what_i_can_watch_filter(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=HOME + WEEK):
        page = current.page
        open_filters(page)
        page.get_by_label("Só o que dá para assistir").check()
        page.get_by_label("Competição").select_option(CHAMPIONS)
        # Nothing is known about these two, so the filter keeps them; Globo is not theirs.
        assert titles(page) == ["Real Madrid x Barça", "Chelsea x Atleti"]
        page.get_by_label("Emissora").select_option("globo")
        assert titles(page) == []
        page.get_by_label("Competição").select_option("")
        assert titles(page) == ["Palmeiras x Flamengo", "São Paulo x Atlético-MG"]


def test_clearing_the_filters_brings_everything_back_and_empties_the_address(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=HOME + WEEK):
        page = current.page
        open_filters(page)
        page.get_by_label("Emissora").select_option("sportv")
        page.get_by_label(TEXT_BOX).fill("palm")
        page.get_by_role("button", name="Limpar filtros").click()
        assert len(titles(page)) == 5
        assert params(page) == {"view": "week"}
        assert page.locator("#filters-summary").inner_text() == "Filtros"
        assert page.get_by_label(TEXT_BOX).input_value() == ""


def test_the_filters_work_inside_the_my_teams_list_too(browser: Browser, origin: str) -> None:
    record = {"version": 1, "teams": ["palmeiras", "real-madrid"], "services": []}
    for current in visit(browser, origin, saved={STORAGE_KEY: json.dumps(record)}):
        page = current.page
        assert titles(page) == ["Palmeiras x Flamengo", "Real Madrid x Barça"]
        open_filters(page)
        page.get_by_label("Competição").select_option(CHAMPIONS)
        assert titles(page) == ["Real Madrid x Barça"]


# --- the address ---------------------------------------------------------------------------------


def test_a_view_in_the_address_is_applied_and_survives_a_reload(
    browser: Browser, origin: str
) -> None:
    address = f"{HOME}?view=week&competition={CHAMPIONS}&q=chelsea"
    for current in visit(browser, origin, path=address):
        page = current.page
        assert titles(page) == ["Chelsea x Atleti"]
        assert page.locator("#filters").evaluate("e => e.open")  # a filtered view shows its filters
        assert page.get_by_label("Competição").input_value() == CHAMPIONS
        assert page.get_by_label(TEXT_BOX).input_value() == "chelsea"
        assert (
            page.get_by_role("button", name="Esta semana", exact=True).get_attribute("aria-pressed")
            == "true"
        )
        page.reload()
        page.wait_for_selector("html[data-ready='true']")
        assert titles(page) == ["Chelsea x Atleti"]


def test_what_the_site_does_not_have_in_the_address_is_ignored(
    browser: Browser, origin: str
) -> None:
    address = (
        f"{HOME}?view=evil&competition=nope&broadcaster=hbo-max&teams=gone-fc&services=nothing"
    )
    for current in visit(browser, origin, path=address):
        page = current.page
        assert titles(page) == []  # today has no match, and nothing was filtered
        assert (
            page.get_by_role("button", name="Hoje", exact=True).get_attribute("aria-pressed")
            == "true"
        )
        assert page.locator("#filters-summary").inner_text() == "Filtros"
        assert current.console == []


def test_markup_in_the_address_is_text_and_runs_nothing(browser: Browser, origin: str) -> None:
    hostile = "%3Cimg%20src%3Dx%20onerror%3Dwindow.__xss%3D1%3E"
    for current in visit(browser, origin, path=f"{HOME}?view=week&q={hostile}"):
        page = current.page
        assert page.get_by_label(TEXT_BOX).input_value() == "<img src=x onerror=window.__xss=1>"
        assert page.locator("main img, #filters img").count() == 0
        assert page.evaluate("window.__xss") is None
        assert current.console == []


def test_a_very_long_search_in_the_address_is_cut(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=f"{HOME}?view=week&q={'a' * 500}"):
        assert len(current.page.get_by_label(TEXT_BOX).input_value()) == 60


def test_the_address_never_carries_the_visitors_teams_unless_they_share(
    browser: Browser, origin: str
) -> None:
    record = {
        "version": 1,
        "teams": ["palmeiras"],
        "services": ["globoplay"],
        "onlyWatchable": True,
    }
    for current in visit(browser, origin, saved={STORAGE_KEY: json.dumps(record)}):
        page = current.page
        open_filters(page)
        page.get_by_label("Competição").select_option(BRASILEIRAO)
        page.get_by_label(TEXT_BOX).fill("pal")
        assert set(params(page)) == {"competition", "q"}
        assert "palmeiras" not in address(page) and "globoplay" not in address(page).lower()


# --- sharing -------------------------------------------------------------------------------------


def share(page: Page) -> str:
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    open_filters(page)
    page.get_by_role("button", name="Copiar link desta visão").click()
    return str(page.evaluate("navigator.clipboard.readText()"))


def test_the_share_button_copies_a_link_with_the_filters_teams_and_services(
    browser: Browser, origin: str
) -> None:
    record = {
        "version": 1,
        "teams": ["palmeiras", "brasil"],
        "services": ["globoplay"],
        "onlyWatchable": True,
    }
    for current in visit(browser, origin, saved={STORAGE_KEY: json.dumps(record)}):
        page = current.page
        open_filters(page)
        page.get_by_label("Competição").select_option(BRASILEIRAO)
        link = share(page)
        parts = urlparse(link)
        assert link.startswith(origin + HOME + "?")
        assert {k: v[0] for k, v in parse_qs(parts.query).items()} == {
            "competition": BRASILEIRAO,
            "teams": "palmeiras,brasil",
            "services": "globoplay",
            "watchable": "1",
        }
        assert page.locator("#share-status").inner_text() == "Link copiado."
        assert page.locator("#share-link").input_value() == link


def test_when_the_clipboard_refuses_the_link_is_shown_to_copy_by_hand(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.evaluate(
            "Object.defineProperty(navigator, 'clipboard', "
            "{value: {writeText: () => Promise.reject(new Error('no'))}})"
        )
        open_filters(page)
        page.get_by_role("button", name="Copiar link desta visão").click()
        assert "selecione o link abaixo" in page.locator("#share-status").inner_text()
        assert page.locator("#share-link").is_visible()


def test_opening_a_shared_link_shows_the_same_view_on_another_device(
    browser: Browser, origin: str
) -> None:
    link = f"{HOME}?view=week&broadcaster=globo&teams=palmeiras&services=globoplay&watchable=1"
    for current in visit(browser, origin, path=link):  # a fresh browser: nothing saved there
        page = current.page
        assert titles(page) == ["Palmeiras x Flamengo", "São Paulo x Atlético-MG"]
        assert page.get_by_role("button", name="Remover Palmeiras").count() == 1
        assert page.get_by_label("Globoplay").is_checked()
        assert page.get_by_label("Só o que dá para assistir").is_checked()
        assert page.get_by_label("Emissora").input_value() == "globo"
        assert page.locator("#shared-notice").is_visible()
        assert saved_record(page) is None  # nothing was saved on this device


def test_a_shared_link_does_not_touch_what_the_visitor_had_saved(
    browser: Browser, origin: str
) -> None:
    mine = {"version": 1, "teams": ["real-madrid"], "services": [], "onlyWatchable": False}
    for current in visit(
        browser, origin, saved={STORAGE_KEY: json.dumps(mine)}, path=f"{HOME}?teams=brasil"
    ):
        page = current.page
        assert titles(page) == ["Brasil x A definir"]
        assert saved_record(page) == mine


def test_changing_the_choices_in_a_shared_view_makes_them_the_visitors_own(
    browser: Browser, origin: str
) -> None:
    link = f"{HOME}?view=week&teams=palmeiras&services=globoplay"
    for current in visit(browser, origin, path=link):
        page = current.page
        page.get_by_label("Premiere (pay-per-view)").check()
        assert saved_record(page) == {
            "version": 1,
            "teams": ["palmeiras"],
            "services": ["premiere", "globoplay"],
            "onlyWatchable": False,
        }
        assert not page.locator("#shared-notice").is_visible()
        assert set(params(page)) == {"view"}  # the choices left the address


def test_a_plain_visit_has_no_shared_notice(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        assert not current.page.locator("#shared-notice").is_visible()


def test_ids_the_site_does_not_have_are_dropped_from_a_shared_link(
    browser: Browser, origin: str
) -> None:
    link = f"{HOME}?teams=gone-fc,palmeiras,../x&services=nope"
    for current in visit(browser, origin, path=link):
        page = current.page
        assert page.get_by_role("button", name="Remover Palmeiras").count() == 1
        assert page.locator("#chosen-teams li").count() == 1
        assert page.locator("#service-options input:checked").count() == 0


def test_following_filters_or_sharing_sends_nothing_anywhere(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=HOME + WEEK):
        page = current.page
        before = len(current.requests)
        open_filters(page)
        page.get_by_label(TEXT_BOX).fill("palm")
        page.get_by_label("Competição").select_option(BRASILEIRAO)
        page.get_by_role("button", name="Copiar link desta visão").click()
        later = [r for r in current.requests[before:] if not r.endswith("/assets/favicon.svg")]
        assert later == []  # the tab's icon may load late; nothing else does


# --- the whole page ------------------------------------------------------------------------------


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_with_the_filters_open_and_a_shared_view(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    link = f"{HOME}?view=week&competition={BRASILEIRAO}&q=pal&teams=palmeiras&services=globoplay"
    for current in visit(browser, origin, scheme, size, path=link):
        page = current.page
        assert page.locator("#filters").evaluate("e => e.open")
        assert axe_violations(page) == []
        page.get_by_role("button", name="Copiar link desta visão").click()
        assert axe_violations(page) == []
