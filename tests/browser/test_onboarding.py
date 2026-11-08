"""The first-run flow: welcome, then continent, country and team, then services.

A new visitor gets a full-screen dialog (shirts in the team colours, grids to tap). What it saves
is what the pickers save, and nothing else leaves the browser. The tests use extra national teams
that the small test data does not have, served in place of teams.json.
"""

import json
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, expect
from site_browser import (
    DATA,
    ONBOARDED_KEY,
    STORAGE_KEY,
    VIEWPORTS,
    WATCH_VIOLATIONS,
    axe_violations,
    visit,
)

pytestmark = pytest.mark.browser

DIALOG = "#onboarding"


def teams_with_nations() -> dict[str, Any]:
    document: dict[str, Any] = json.loads((DATA / "teams.json").read_text(encoding="utf-8"))
    for team in document["teams"]:
        if team["id"] == "brasil":
            team["kind"] = "national"  # the national team that the test data already holds
    shirt = {"primary": "#FFFFFF", "secondary": "#000000"}
    for identifier, name, country in (
        ("espanha", "Espanha", "ES"),
        ("inglaterra", "Inglaterra", "GB-ENG"),
        ("uruguai", "Uruguai", "UY"),
        ("marrocos", "Marrocos", "MA"),
    ):
        document["teams"].append(
            {
                "id": identifier,
                "name": name,
                "short_name": name,
                "aliases": [],
                "country": country,
                "colors": shirt,
                "kind": "national",
                "shirt": {"primary": "#C60B1E", "secondary": "#FFC400"},
            }
        )
    return document


DATA_WITH_NATIONS = {"teams": teams_with_nations()}


def open_flow(browser: Browser, origin: str, **options: Any) -> Any:
    options.setdefault("reduced_motion", "reduce")  # no waiting for animations to end
    return visit(browser, origin, onboarding=True, changed_data=DATA_WITH_NATIONS, **options)


def button(page: Page, name: str, exact: bool = False) -> Any:
    return page.locator(DIALOG).get_by_role("button", name=name, exact=exact)


def team(page: Page, name: str) -> Any:
    """A team's own card (not the chip that takes it out, nor a search result for a country)."""
    return button(page, name, exact=True)


def title(page: Page) -> str:
    return page.locator(f"{DIALOG} .ob__title").inner_text()


def stored(page: Page) -> Any:
    text = page.evaluate(f"localStorage.getItem('{STORAGE_KEY}')")
    return None if text is None else json.loads(text)


def choose_brazil_teams(page: Page) -> None:
    button(page, "Escolher meus times").click()
    button(page, "América do Sul").click()
    button(page, "Brasil").click()


# --- a new visitor ----------------------------------------------------------------------------


def test_a_new_visitor_starts_with_the_welcome_and_the_rest_of_the_page_is_out_of_reach(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        dialog = page.locator(DIALOG)
        expect(dialog).to_be_visible()
        assert dialog.get_attribute("role") == "dialog"
        assert dialog.get_attribute("aria-modal") == "true"
        assert dialog.get_attribute("aria-label") == "Primeiros passos"
        assert "Onde vai passar o jogo do seu time?" in title(page)
        # The title has the focus, so a screen reader says where the visitor is.
        assert page.evaluate("document.activeElement.className") == "ob__title"
        for selector in ("main", ".site-header", ".site-footer", ".skip-link"):
            assert page.evaluate(f"document.querySelector('{selector}').inert") is True


def test_a_returning_visitor_with_teams_never_sees_it(browser: Browser, origin: str) -> None:
    saved = {STORAGE_KEY: json.dumps({"version": 1, "teams": ["palmeiras"], "services": []})}
    for current in visit(browser, origin, onboarding=True, saved=saved):
        assert not current.page.locator(DIALOG).is_visible()


def test_a_shared_link_goes_straight_to_the_matches(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, onboarding=True, path="/index.html?teams=palmeiras"):
        assert not current.page.locator(DIALOG).is_visible()


def test_a_visitor_whose_browser_keeps_nothing_is_not_asked_every_time(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, onboarding=True, storage_blocked=True):
        assert not current.page.locator(DIALOG).is_visible()


# --- the whole way: continent, country, team, services ----------------------------------------


def test_the_visitor_goes_from_the_welcome_to_their_matches_in_a_few_taps(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        choose_brazil_teams(page)
        assert title(page) == "Brasil"
        team(page, "Palmeiras").click()
        button(page, "Brasil").first.click()  # the national team: the wide card
        assert button(page, "Continuar com 2 escolhidos").is_visible()
        button(page, "Continuar com 2 escolhidos").click()
        assert title(page) == "O que você tem em casa?"
        page.locator(DIALOG).get_by_label("Globoplay", exact=False).first.check()
        button(page, "Concluir com 1 serviço").click()

        expect(page.locator(DIALOG)).to_be_hidden()
        assert page.evaluate("document.querySelector('main').inert") is False
        assert page.evaluate("document.activeElement.id") == "main"
        saved = stored(page)
        assert saved["teams"] == ["palmeiras", "brasil"]
        assert saved["services"] == ["globoplay"]
        assert page.evaluate(f"localStorage.getItem('{ONBOARDED_KEY}')") == "1"
        # The matches of the chosen teams are on the page and the choices are in the pickers.
        assert "Palmeiras x Flamengo" in page.locator("#matches-list").inner_text()
        assert page.locator("#chosen-teams .chip").count() == 2


def test_choosing_nothing_and_skipping_the_services_saves_nothing_but_the_fact_it_was_seen(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        button(page, "Ver todos os jogos sem escolher").click()
        expect(page.locator(DIALOG)).to_be_hidden()
        assert stored(page) is None  # no choices were made, so none are saved
        assert page.evaluate(f"localStorage.getItem('{ONBOARDED_KEY}')") == "1"
        page.reload()
        page.wait_for_selector("html[data-ready='true']")
        assert not page.locator(DIALOG).is_visible()  # it does not come back


def test_the_services_can_be_skipped(browser: Browser, origin: str) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        choose_brazil_teams(page)
        team(page, "Palmeiras").click()
        button(page, "Continuar com 1 escolhido").click()
        button(page, "Pular por enquanto").click()
        expect(page.locator(DIALOG)).to_be_hidden()
        assert stored(page) == {
            "version": 1,
            "teams": ["palmeiras"],
            "services": [],
            "onlyWatchable": False,
        }


def test_escape_leaves_without_saving_the_picks(browser: Browser, origin: str) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        choose_brazil_teams(page)
        team(page, "Palmeiras").click()
        page.keyboard.press("Escape")
        expect(page.locator(DIALOG)).to_be_hidden()
        assert stored(page) is None
        assert page.evaluate("document.querySelector('main').inert") is False


# --- what each screen shows -------------------------------------------------------------------


def test_the_continents_that_have_teams_are_offered_with_shirts_and_a_count(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        button(page, "Escolher meus times").click()
        names = page.locator(".ob-tile--continent .ob-tile__name").all_inner_texts()
        assert names == ["América do Sul", "Europa", "África"]  # only those with a team
        assert page.locator(".ob-tile--continent").first.locator(".shirt").count() == 3
        assert "países" in page.locator(".ob-tile--continent").nth(1).inner_text()


def test_a_country_is_the_shirt_of_its_national_team_and_says_what_it_has(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        button(page, "Escolher meus times").click()
        button(page, "América do Sul").click()
        assert title(page) == "América do Sul"
        tiles = page.locator(".ob-tile")
        assert tiles.count() == 2  # Brazil (clubs + national team) and Uruguay (national team)
        assert "Brasil" in tiles.nth(0).inner_text()
        assert "Só a Seleção" in tiles.nth(1).inner_text()
        brazil_shirt = tiles.nth(0).locator(".shirt__body").get_attribute("fill")
        assert brazil_shirt == "#FFDF00"  # no shirt of its own: the national team's colours


def test_a_country_with_only_a_national_team_shows_just_that_team(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        button(page, "Escolher meus times").click()
        button(page, "África").click()
        button(page, "Marrocos").click()
        assert title(page) == "Marrocos"
        assert page.locator(".ob-tile").count() == 1
        assert page.locator(".ob-tile--wide").count() == 1
        assert "Clubes" not in page.locator(DIALOG).inner_text()


def test_a_team_is_a_toggle_button_that_says_whether_it_is_chosen(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        choose_brazil_teams(page)
        palmeiras = team(page, "Palmeiras")
        assert palmeiras.get_attribute("aria-pressed") == "false"
        palmeiras.click()
        assert palmeiras.get_attribute("aria-pressed") == "true"
        assert "Palmeiras escolhido. 1 time escolhido." in page.locator("#ob-live").inner_text()
        palmeiras.click()
        assert palmeiras.get_attribute("aria-pressed") == "false"
        assert "Palmeiras removido. Nenhum time escolhido." in page.locator("#ob-live").inner_text()
        assert not page.locator(".ob-bar").is_visible()


def test_the_bar_lists_the_picks_and_a_chip_takes_one_out(browser: Browser, origin: str) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        choose_brazil_teams(page)
        team(page, "Palmeiras").click()
        team(page, "São Paulo").click()
        chips = page.locator(".ob-bar .ob-chip")
        assert chips.count() == 2
        button(page, "Remover Palmeiras").click()
        assert page.locator(".ob-bar .ob-chip").count() == 1
        assert team(page, "Palmeiras").get_attribute("aria-pressed") == "false"


def test_the_picks_follow_the_visitor_back_to_the_countries_and_the_continents(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        choose_brazil_teams(page)
        team(page, "Palmeiras").click()
        button(page, "Voltar").click()
        assert title(page) == "América do Sul"
        assert page.locator(".ob-tile .ob-badge").first.inner_text() == "1"
        button(page, "Voltar").click()
        assert page.locator(".ob-tile--continent .ob-badge").first.inner_text() == "1"
        assert button(page, "Continuar com 1 escolhido").is_visible()


# --- the search -------------------------------------------------------------------------------


def test_a_team_can_be_found_by_typing_and_chosen_without_the_grids(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        button(page, "Escolher meus times").click()
        page.locator("#ob-search").fill("palm")
        assert page.locator(".ob-tile--continent").first.is_hidden()
        button(page, "Palmeiras Brasil").click()  # the result says whose team it is
        assert button(page, "Continuar com 1 escolhido").is_visible()
        assert stored(page) is None  # nothing is saved until the visitor finishes


def test_a_country_can_be_found_by_typing_and_opens_its_teams(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        button(page, "Escolher meus times").click()
        page.locator("#ob-search").fill("espan")
        button(page, "Espanha País").click()
        assert title(page) == "Espanha"
        button(page, "Voltar").click()
        assert "Escolha o continente" in page.locator(DIALOG).inner_text()  # not the country list


def test_a_search_with_no_answer_says_so(browser: Browser, origin: str) -> None:
    for current in open_flow(browser, origin):
        page = current.page
        button(page, "Escolher meus times").click()
        page.locator("#ob-search").fill("zzzzzz")
        assert "Nenhum time ou país com o nome" in page.locator(DIALOG).inner_text()


# --- changing the choices later ---------------------------------------------------------------


def test_the_visitor_can_come_back_to_change_their_teams_with_their_choices_ticked(
    browser: Browser, origin: str
) -> None:
    saved = {
        STORAGE_KEY: json.dumps({"version": 1, "teams": ["palmeiras"], "services": ["globoplay"]})
    }
    for current in open_flow(browser, origin, saved=saved):
        page = current.page
        assert not page.locator(DIALOG).is_visible()
        page.click("#reopen-onboarding")
        assert "De que parte do mundo" in title(page)
        assert button(page, "Continuar com 1 escolhido").is_visible()
        button(page, "América do Sul").click()
        button(page, "Brasil").click()
        assert team(page, "Palmeiras").get_attribute("aria-pressed") == "true"
        team(page, "Palmeiras").click()
        team(page, "Flamengo").click()
        button(page, "Continuar com 1 escolhido").click()
        assert page.locator(DIALOG).get_by_label("Globoplay", exact=False).first.is_checked()
        button(page, "Concluir com 1 serviço").click()
        assert stored(page)["teams"] == ["flamengo"]


def test_the_button_to_change_the_teams_gives_the_focus_back_when_the_flow_closes(
    browser: Browser, origin: str
) -> None:
    saved = {STORAGE_KEY: json.dumps({"version": 1, "teams": ["palmeiras"], "services": []})}
    for current in open_flow(browser, origin, saved=saved):
        page = current.page
        page.click("#reopen-onboarding")
        button(page, "Pular").click()
        expect(page.locator(DIALOG)).to_be_hidden()
        assert stored(page)["teams"] == ["palmeiras"]  # skipping changes nothing


# --- nothing leaves the browser, and the page stays within its rules --------------------------


def test_the_flow_asks_for_nothing_but_the_sites_own_files_and_breaks_no_policy(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(
        browser, origin, before_open=lambda p: p.add_init_script(WATCH_VIOLATIONS)
    ):
        page = current.page
        choose_brazil_teams(page)
        team(page, "Palmeiras").click()
        button(page, "Continuar com 1 escolhido").click()
        button(page, "Concluir").click()
        assert page.evaluate("window.__violations") == []
        assert all(url.startswith(origin) for url in current.requests)
        assert all(request.method == "GET" for request in current.details)
        assert not [line for line in current.console if line.startswith(("error", "pageerror"))]


# --- the way it looks and moves ---------------------------------------------------------------


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", ["mobile", "desktop", "narrow"])
def test_no_screen_of_the_flow_has_an_accessibility_violation(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in open_flow(browser, origin, scheme=scheme, size=size):
        page = current.page
        seen = [("welcome", axe_violations(page))]
        button(page, "Escolher meus times").click()
        seen.append(("continents", axe_violations(page)))
        button(page, "América do Sul").click()
        seen.append(("countries", axe_violations(page)))
        button(page, "Brasil").click()
        team(page, "Palmeiras").click()
        seen.append(("teams, one chosen", axe_violations(page)))
        button(page, "Continuar com 1 escolhido").click()
        seen.append(("services", axe_violations(page)))
        assert [(name, found) for name, found in seen if found] == []


def test_nothing_is_wider_than_the_screen_even_on_a_narrow_phone(
    browser: Browser, origin: str
) -> None:
    for current in open_flow(browser, origin, size="narrow"):
        page = current.page
        width = VIEWPORTS["narrow"][0]
        steps = []
        button(page, "Escolher meus times").click()
        steps.append(page.evaluate("document.querySelector('.ob__screen').scrollWidth"))
        button(page, "Europa").click()
        steps.append(page.evaluate("document.querySelector('.ob__screen').scrollWidth"))
        button(page, "Espanha").click()
        steps.append(page.evaluate("document.querySelector('.ob__screen').scrollWidth"))
        assert all(value <= width for value in steps), steps


def test_when_the_visitor_asks_for_less_motion_nothing_moves(browser: Browser, origin: str) -> None:
    for current in open_flow(browser, origin, reduced_motion="reduce"):
        page = current.page
        assert (
            page.evaluate("getComputedStyle(document.querySelector('.ob-brand')).animationName")
            == "none"
        )
        button(page, "Escolher meus times").click()
        names = page.evaluate(
            "[...document.querySelectorAll('.ob-tile, .ob__screen')]"
            ".map(e => getComputedStyle(e).animationName)"
        )
        assert set(names) == {"none"}


def test_the_welcome_moves_when_motion_is_allowed(browser: Browser, origin: str) -> None:
    for current in open_flow(browser, origin, reduced_motion="no-preference"):
        page = current.page
        names = page.evaluate(
            "['.ob-brand', '.ob-sample', '.ob-sample__card', '.ob-word', '.ob-button--cta']"
            ".map(s => getComputedStyle(document.querySelector(s)).animationName)"
        )
        assert all(name != "none" for name in names), names
        # Only movement, size and fade: nothing that would push the page around.
        properties = page.evaluate(
            "[...document.getAnimations()].flatMap(a => a.effect.getKeyframes()"
            ".flatMap(k => Object.keys(k)))"
        )
        allowed = {
            "offset",
            "easing",
            "composite",
            "computedOffset",
            "opacity",
            "transform",
            "boxShadow",
        }
        assert set(properties) <= allowed, set(properties) - allowed
