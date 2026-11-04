"""How old the data is, and the links to report a wrong broadcast (FR-30).

The fixtures' clock is Monday 2 November 2026, 12:00 UTC (09:00 in Brazil); their status says
the last success was at 09:00 UTC, three hours before.
"""

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Browser, Page
from site_browser import DATA, STORAGE_KEY, VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

SHOWN_HOST = "github.com"
REPO_PATH = "/raissonls/ubi-ludus/issues/new"


def status_with(last_success: str | None) -> dict[str, dict[str, Any]]:
    document = json.loads(Path(DATA / "status.json").read_text(encoding="utf-8"))
    document["last_success_at"] = last_success
    return {"status": document}


def freshness(page: Page) -> str:
    return page.locator("#freshness").inner_text()


def state(page: Page) -> str | None:
    return page.locator("#freshness").get_attribute("data-state")


def week(page: Page) -> None:
    page.get_by_role("button", name="Esta semana", exact=True).click()


def query(href: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlparse(href).query).items()}


# --- the freshness indicator ---------------------------------------------------------------------


def test_the_page_says_when_the_data_was_updated_in_brazil_time(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        assert freshness(page) == "Atualizado hoje às 06:00"  # 09:00 UTC
        assert state(page) == "fresh"
        assert page.locator("#freshness [aria-hidden]").count() == 0


def test_yesterdays_update_says_yesterday(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, changed_data=status_with("2026-11-01T23:00:00Z")):
        assert freshness(current.page) == "Atualizado ontem às 20:00"
        assert state(current.page) == "fresh"


def test_an_older_update_inside_36_hours_gives_the_date(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, changed_data=status_with("2026-11-01T01:00:00Z")):
        text = freshness(current.page)
        assert text.startswith("Atualizado em ") and "31" in text and text.endswith("às 22:00")
        assert state(current.page) == "fresh"


def test_data_older_than_36_hours_turns_into_a_warning_in_words(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, changed_data=status_with("2026-10-30T09:00:00Z")):
        page = current.page
        assert state(page) == "stale"
        text = freshness(page)
        assert text.startswith("⚠ Dados possivelmente desatualizados. Última atualização: ")
        assert text.endswith(", 06:00.")
        assert page.locator("#freshness [aria-hidden]").count() == 1  # the mark is decoration
        background = page.locator("#freshness").evaluate("e => getComputedStyle(e).backgroundColor")
        assert background != "rgba(0, 0, 0, 0)"


def test_the_warning_starts_just_after_36_hours(browser: Browser, origin: str) -> None:
    # The clock is 12:00 UTC on the 2nd: 36 hours before is 00:00 UTC on 1 November.
    for current in visit(browser, origin, changed_data=status_with("2026-11-01T00:00:00Z")):
        assert state(current.page) == "fresh"
    for current in visit(browser, origin, changed_data=status_with("2026-10-31T23:59:00Z")):
        assert state(current.page) == "stale"


def test_a_pipeline_that_never_succeeded_is_a_warning_too(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, changed_data=status_with(None)):
        page = current.page
        assert state(page) == "unknown"
        assert freshness(page) == "⚠ Ainda não há registro de uma atualização dos dados."


def test_without_the_data_there_is_no_indicator_only_the_error(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, broken={"matches": 500}):
        assert not current.page.locator("#freshness").is_visible()
        assert "Não foi possível carregar" in current.page.locator("#state-panel").inner_text()


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("last", ["2026-11-02T09:00:00Z", "2026-10-29T09:00:00Z", None])
def test_axe_finds_nothing_in_any_freshness_state(
    browser: Browser, origin: str, scheme: str, size: str, last: str | None
) -> None:
    for current in visit(browser, origin, scheme, size, changed_data=status_with(last)):
        assert axe_violations(current.page) == []


def test_the_next_match_is_still_on_screen_on_a_phone_with_the_indicator(
    browser: Browser, origin: str
) -> None:
    saved = {STORAGE_KEY: json.dumps({"version": 1, "teams": ["palmeiras"], "services": []})}
    height = VIEWPORTS["mobile"][1]
    stale = status_with("2026-10-29T09:00:00Z")
    for current in visit(browser, origin, size="mobile", saved=saved, changed_data=stale):
        box = current.page.locator("#matches-list .match-card").first.bounding_box()
        assert box is not None and box["y"] + box["height"] <= height, box


# --- report a wrong broadcast --------------------------------------------------------------------


def test_each_card_has_a_link_that_reports_that_match_with_what_the_site_shows(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        week(page)
        card = page.locator(".match-card", has_text="Palmeiras")
        link = card.get_by_role("link", name="Reportar transmissão errada de Palmeiras x Flamengo")
        assert link.count() == 1  # the name says which match, since every card has the link
        href = link.get_attribute("href") or ""
        parts = urlparse(href)
        assert (parts.scheme, parts.hostname, parts.path) == ("https", SHOWN_HOST, REPO_PATH)
        fields = query(href)
        assert set(fields) == {"template", "title", "match", "shown"}
        assert fields["template"] == "wrong-broadcast.yml"
        assert fields["title"] == "Transmissão errada: Palmeiras x Flamengo"
        assert fields["match"].startswith("Palmeiras x Flamengo · Campeonato Brasileiro Série A · ")
        assert fields["match"].endswith(" · fx-1")
        assert (
            fields["shown"]
            == "SporTV (pela tabela de direitos), TV Globo (pela tabela de direitos)"
        )
        assert link.get_attribute("rel") == "noopener noreferrer"


def test_a_match_with_no_known_broadcaster_can_be_reported_too(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        week(page)
        link = page.locator(".match-card", has_text="Real Madrid").get_by_role("link")
        assert query(link.get_attribute("href") or "")["shown"] == (
            "nenhuma emissora (transmissão não confirmada)"
        )


def test_a_match_that_is_over_or_off_has_nothing_to_report(browser: Browser, origin: str) -> None:
    document = json.loads(Path(DATA / "matches.json").read_text(encoding="utf-8"))
    for match in document["matches"]:
        if match["id"] == "fx-1":
            match["status"] = "cancelled"
    for current in visit(browser, origin, changed_data={"matches": document}):
        page = current.page
        week(page)
        cancelled = page.locator(".match-card[data-state='cancelled']")
        assert cancelled.count() == 1
        assert cancelled.get_by_role("link").count() == 0
        assert page.locator(".match-card").get_by_role("link").count() == 4


def test_the_link_carries_the_match_and_nothing_about_the_visitor(
    browser: Browser, origin: str
) -> None:
    record = {
        "version": 1,
        "teams": ["palmeiras"],
        "services": ["globoplay"],
        "onlyWatchable": True,
    }
    for current in visit(browser, origin, saved={STORAGE_KEY: json.dumps(record)}):
        hrefs = current.page.locator(".match-card__report").evaluate_all("a => a.map(x => x.href)")
        assert hrefs
        for href in hrefs:
            assert set(query(href)) == {"template", "title", "match", "shown"}
            assert "globoplay" not in href and "onlyWatchable" not in href


def test_following_the_link_goes_to_the_new_issue_form_and_only_then(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin):
        page = current.page
        page.route(
            "https://github.com/**", lambda route: route.fulfill(body="<title>issue</title>")
        )
        week(page)
        before = [r for r in current.requests if urlparse(r).hostname == SHOWN_HOST]
        assert before == []  # drawing the page and the cards sends nothing to GitHub
        page.locator(".match-card", has_text="Palmeiras").get_by_role("link").click()
        page.wait_for_url("https://github.com/**")
        assert urlparse(page.url).path == REPO_PATH
        assert query(page.url)["title"] == "Transmissão errada: Palmeiras x Flamengo"


def test_the_footer_links_to_the_form_without_a_match(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin):
        link = current.page.get_by_role("link", name="Viu uma transmissão errada? Avise no GitHub")
        href = link.get_attribute("href") or ""
        assert urlparse(href).path == REPO_PATH
        assert query(href) == {"template": "wrong-broadcast.yml"}
        assert link.get_attribute("rel") == "noopener noreferrer"


def test_the_issue_form_exists_with_the_fields_the_links_fill_in() -> None:
    root = Path(__file__).resolve().parents[2] / ".github" / "ISSUE_TEMPLATE"
    form = (root / "wrong-broadcast.yml").read_text(encoding="utf-8")
    for field_id in ("match", "shown", "correct", "source"):
        assert f"id: {field_id}\n" in form
