"""The match card (FR-24, FR-12, FR-13) in every state, drawn by the test-only gallery page.

The gallery (tests/fixtures/site/gallery) draws one card for each state and variant with the
site's own modules, under the site's own security policy.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Locator, Page
from site_browser import VIEWPORTS, axe_violations, visit

pytestmark = pytest.mark.browser

GALLERY = "/gallery/cards.html"
SNAPSHOT = Path(__file__).resolve().parent / "snapshots" / "match_card_styles.json"
BROADCASTER_NAMES = ["TV Globo", "SporTV", "ESPN", "Premiere", "Globoplay", "Disney+", "CazéTV"]
WATCH_TEXT = "Onde assistir"
UNKNOWN_TEXT = "Transmissão ainda não confirmada"
RULE_TEXT = "Pela tabela de direitos: confira antes do jogo."

# What a card looks like, as numbers the computer can compare. Pixels would differ between
# Windows and the Linux of CI (fonts), colours, borders and words do not.
SIGNATURE = """
() => {
  const read = (element, properties) => {
    const style = getComputedStyle(element);
    return Object.fromEntries(properties.map((p) => [p, style.getPropertyValue(p)]));
  };
  const colours = ['background-color', 'color'];
  const out = {};
  for (const card of document.querySelectorAll('[data-case]')) {
    const state = card.querySelector('.state');
    const confidence = card.querySelector('.confidence');
    const more = card.querySelector('.badges__more');
    out[card.dataset.case] = {
      state: card.dataset.state,
      horizon: card.querySelector('.match-card__horizon')
        ? {
            text: card.querySelector('.match-card__horizon').textContent,
            ...read(card.querySelector('.match-card__horizon'), [...colours, 'font-weight']),
          }
        : null,
      confidence: card.dataset.confidence,
      access: card.dataset.access ?? null,
      accessLine: card.querySelector('.match-card__access')
        ? {
            text: card.querySelector('.match-card__access').textContent,
            ...read(card.querySelector('.match-card__access'), colours),
          }
        : null,
      cardBorder: read(card, ['border-top-style', 'border-inline-start-style']),
      card: read(card, [...colours, 'border-inline-start-color', 'border-inline-start-width']),
      teams: read(
        card.querySelector('.match-card__teams'),
        ['text-decoration-line', 'font-weight']
      ),
      stateLabel: state ? { text: state.textContent.trim(), ...read(state, colours) } : null,
      watchLabel: card.querySelector('.match-card__label')?.textContent ?? null,
      badges: [...card.querySelectorAll('.badge')]
        .filter((badge) => !badge.hidden)
        .map((badge) => ({
          name: badge.querySelector('span:not([aria-hidden]):not(.visually-hidden)').textContent,
          tick: badge.querySelector('[aria-hidden]') !== null,
          kind: badge.className,
          access: badge.dataset.access ?? null,
          outline: read(badge, ['border-top-style', 'border-top-width']),
          ...read(badge, [...colours, 'font-weight']),
        })),
      hiddenBadges: [...card.querySelectorAll('.badge')].filter((badge) => badge.hidden).length,
      more: more ? more.textContent : null,
      confidenceLine: confidence
        ? { text: confidence.textContent, ...read(confidence, colours) }
        : null,
    };
  }
  return out;
}
"""


def card(page: Page, name: str) -> Locator:
    return page.locator(f"[data-case='{name}']")


def text_of(page: Page, name: str, selector: str) -> str:
    return card(page, name).locator(selector).inner_text()


def whole_text(page: Page, name: str) -> str:
    return card(page, name).inner_text()


def signature(page: Page) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = page.evaluate(SIGNATURE)
    return found


# --- what each card says ------------------------------------------------------------------------


def test_a_card_shows_teams_competition_round_local_time_and_broadcasters(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        assert text_of(page, "scheduled-rule", ".match-card__teams") == "Palmeiras x Flamengo"
        assert (
            text_of(page, "scheduled-rule", ".match-card__competition")
            == "Campeonato Brasileiro Série A · Rodada 34"
        )
        when = card(page, "scheduled-rule").locator("time")
        assert when.get_attribute("datetime") == "2026-11-03T22:00:00Z"
        assert "19:00" in when.inner_text()  # 22:00 UTC is 19:00 in Brazil
        names = card(page, "scheduled-rule").locator(
            ".badge span:not([aria-hidden]):not(.visually-hidden)"
        )
        assert names.all_inner_texts() == ["Premiere", "SporTV", "TV Globo"]
        assert text_of(page, "scheduled-rule", ".match-card__label") == WATCH_TEXT


def test_the_heading_of_a_card_is_its_teams(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=GALLERY):
        tree = card(current.page, "scheduled-rule").aria_snapshot()
        assert 'heading "Palmeiras x Flamengo" [level=3]' in tree
        assert "TV Globo (pela tabela de direitos)" in tree  # what a screen reader hears per badge


def test_a_team_colour_is_the_cards_accent_and_nothing_else_is_drawn(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        bar = card(page, "scheduled-rule").evaluate(
            "e => getComputedStyle(e).borderInlineStartColor"
        )
        assert bar == "rgb(0, 100, 55)"  # Palmeiras green
        assert page.locator("img, svg, canvas, picture").count() == 0


def test_rounds_read_as_a_matchday_a_stage_or_nothing(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        assert text_of(page, "knockout-final", ".match-card__competition").endswith("· Final")
        assert text_of(page, "knockout-unknown-stage", ".match-card__competition").endswith(
            "· Last 8"
        )
        assert (
            text_of(page, "teams-not-decided", ".match-card__competition")
            == "Amistosos de seleções"
        )


def test_a_team_not_decided_yet_says_so(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=GALLERY):
        assert (
            text_of(current.page, "teams-not-decided", ".match-card__teams") == "Brasil x A definir"
        )


# --- how sure we are (FR-12, FR-13) -------------------------------------------------------------


def test_an_unknown_match_names_no_broadcaster_and_says_it_is_not_confirmed(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        for name in ("scheduled-unknown", "teams-not-decided"):
            text = whole_text(page, name)
            assert UNKNOWN_TEXT in text
            assert WATCH_TEXT not in text
            assert card(page, name).locator(".badge").count() == 0
            assert not [b for b in BROADCASTER_NAMES if b in text], name
        assert card(page, "scheduled-unknown").get_attribute("data-confidence") == "unknown"


def test_a_confirmed_broadcaster_has_a_tick_and_the_card_says_confirmed(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        assert card(page, "scheduled-confirmed").get_attribute("data-confidence") == "confirmed"
        assert text_of(page, "scheduled-confirmed", ".confidence") == "Confirmado"
        badges = card(page, "scheduled-confirmed").locator(".badge--confirmed")
        assert badges.count() == 2
        assert all("✓" in text for text in badges.all_inner_texts())
        hidden = (
            card(page, "scheduled-confirmed").locator(".badge .visually-hidden").all_text_contents()
        )
        assert hidden == [" (confirmado)", " (confirmado)"]


def test_a_rule_broadcaster_has_no_tick_and_the_card_says_to_check(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        assert card(page, "scheduled-rule").get_attribute("data-confidence") == "rule"
        assert text_of(page, "scheduled-rule", ".confidence") == RULE_TEXT
        assert "✓" not in whole_text(page, "scheduled-rule")


def test_a_card_with_a_confirmed_and_a_rule_broadcaster_is_a_rule_card_with_confirmed_first(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        assert card(page, "scheduled-mixed").get_attribute("data-confidence") == "rule"
        classes = (
            card(page, "scheduled-mixed")
            .locator(".badge")
            .evaluate_all("b => b.map(x => x.className)")
        )
        assert classes == ["badge badge--confirmed", "badge badge--rule", "badge badge--rule"]
        assert "✓ TV Globo" in card(page, "scheduled-mixed").locator(".badge").first.inner_text()


# --- the state of the match ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "label", "shows_broadcasters"),
    [
        ("live", "Ao vivo", True),
        ("rescheduled", "Remarcado", True),
        ("finished", "Encerrado", False),
        ("postponed", "Adiado", False),
        ("cancelled", "Cancelado", False),
    ],
)
def test_every_state_is_a_word_and_only_a_match_to_watch_lists_broadcasters(
    browser: Browser, origin: str, name: str, label: str, shows_broadcasters: bool
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        assert text_of(page, name, ".state").replace("●", "").strip() == label
        assert (card(page, name).locator(".match-card__watch").count() == 1) is shows_broadcasters
        if not shows_broadcasters:
            assert WATCH_TEXT not in whole_text(page, name)


def test_a_plain_scheduled_match_has_no_state_label(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=GALLERY):
        assert card(current.page, "scheduled-rule").locator(".state").count() == 0


def test_a_cancelled_match_is_struck_through_and_a_live_one_has_a_dot(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        line = (
            card(page, "cancelled")
            .locator(".match-card__teams")
            .evaluate("e => getComputedStyle(e).textDecorationLine")
        )
        assert "line-through" in line
        assert "●" in text_of(page, "live", ".state")
        assert (
            card(page, "live").locator(".state [aria-hidden]").count() == 1
        )  # the dot is decoration


# --- many broadcasters --------------------------------------------------------------------------


def test_more_than_four_broadcasters_wait_behind_a_button_that_works_from_the_keyboard(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        many = card(page, "scheduled-many-broadcasters")
        more = many.get_by_role("button", name="Mostrar mais 3 emissoras")
        assert many.locator(".badge:visible").count() == 4
        assert more.inner_text() == "+3"
        assert more.get_attribute("aria-expanded") == "false"
        assert (
            more.get_attribute("aria-controls") == "card-gallery-scheduled-many-broadcasters-badges"
        )

        more.focus()
        page.keyboard.press("Enter")
        assert many.locator(".badge:visible").count() == 7
        shown = many.get_by_role("button", name="Mostrar menos emissoras")
        assert shown.get_attribute("aria-expanded") == "true"
        assert shown.inner_text() == "menos"

        page.keyboard.press("Space")
        assert many.locator(".badge:visible").count() == 4
        assert (
            many.get_by_role("button", name="Mostrar mais 3 emissoras").get_attribute(
                "aria-expanded"
            )
            == "false"
        )


def test_four_or_fewer_broadcasters_have_no_button(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=GALLERY):
        for name in ("scheduled-rule", "scheduled-mixed", "live"):
            assert card(current.page, name).locator(".badges__more").count() == 0


# --- data is text, never markup -----------------------------------------------------------------


def test_names_that_look_like_html_are_shown_as_text_and_run_nothing(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        title = card(page, "hostile-names").locator(".match-card__teams")
        assert title.inner_text() == "<b onmouseover=window.__xss=2>FC</b> x São Paulo"
        assert card(page, "hostile-names").locator("b, img").count() == 0
        card(page, "hostile-names").hover()
        assert page.evaluate("window.__xss") is None
        assert current.console == []


# --- the whole gallery --------------------------------------------------------------------------


def test_the_gallery_loads_cleanly_from_this_origin_only(browser: Browser, origin: str) -> None:
    for current in visit(browser, origin, path=GALLERY):
        page = current.page
        assert page.locator("[data-case]").count() == 16
        assert page.locator("[data-case] time[datetime]").count() == 16
        assert current.console == []
        assert current.failed == []
        assert all(url.startswith(origin + "/") for url in current.requests)
        assert "[" not in page.locator("main").inner_text(), "a missing string shows as [key]"


@pytest.mark.parametrize("size", list(VIEWPORTS))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_nothing_on_any_card_in_any_state(
    browser: Browser, origin: str, scheme: str, size: str
) -> None:
    for current in visit(browser, origin, scheme, size, path=GALLERY):
        page = current.page
        assert axe_violations(page) == []
        # And with the hidden broadcasters shown.
        page.get_by_role("button", name="Mostrar mais 3 emissoras").click()
        assert axe_violations(page) == []


def test_no_card_makes_the_page_scroll_sideways_even_at_320_px(
    browser: Browser, origin: str
) -> None:
    for current in visit(browser, origin, size="narrow", path=GALLERY):
        widths = current.page.evaluate(
            "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
        )
        assert widths[0] <= widths[1]


# --- the states look different (visual regression, as styles) -----------------------------------


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_states_and_confidences_are_told_apart_by_more_than_colour(
    browser: Browser, origin: str, scheme: str
) -> None:
    for current in visit(browser, origin, scheme, path=GALLERY):
        found = signature(current.page)
        states = {
            name: (
                v["stateLabel"]["text"],
                v["stateLabel"]["background-color"],
                v["stateLabel"]["color"],
            )
            for name, v in found.items()
            if v["stateLabel"]
        }
        # Five labelled states, each with its own words, and live, finished, postponed and
        # cancelled with their own colours as well.
        assert len({s[0] for s in states.values()}) == 5
        coloured = {states[n][1:] for n in ("live", "finished", "postponed")}
        assert len(coloured) == 3
        # Confirmed, rule and unknown: three different lines and three different looks.
        lines = {
            found[n]["confidenceLine"]["text"]: found[n]["confidenceLine"]["background-color"]
            for n in ("scheduled-confirmed", "scheduled-rule", "scheduled-unknown")
        }
        assert len(lines) == 3
        badge = {
            k: found["scheduled-mixed"]["badges"][i] for i, k in enumerate(("confirmed", "rule"))
        }
        assert badge["confirmed"]["background-color"] != badge["rule"]["background-color"]
        assert badge["confirmed"]["tick"] is True and badge["rule"]["tick"] is False


@pytest.mark.parametrize("variant", ["", "+services"])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_card_still_looks_as_recorded(
    browser: Browser, origin: str, scheme: str, variant: str
) -> None:
    """Colours, borders, fonts weights and words of every state against the recorded ones.

    "+services" is the same cards for a visitor who has Premiere. A deliberate change of look is
    recorded with UBI_LUDUS_UPDATE_SNAPSHOTS=1 and the diff of snapshots/match_card_styles.json
    is reviewed with the code.
    """
    key = scheme + variant
    path = GALLERY + ("?services=premiere" if variant else "")
    for current in visit(browser, origin, scheme, path=path):
        found = signature(current.page)
    recorded = json.loads(SNAPSHOT.read_text(encoding="utf-8")) if SNAPSHOT.exists() else {}
    if os.environ.get("UBI_LUDUS_UPDATE_SNAPSHOTS") == "1":
        recorded[key] = found
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(
            json.dumps(recorded, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",  # the same bytes on Windows and Linux
        )
        return
    assert key in recorded, "no recorded look yet: run once with UBI_LUDUS_UPDATE_SNAPSHOTS=1"
    assert set(found) == set(recorded[key]), "a card was added or removed"
    changed = [name for name in found if found[name] != recorded[key][name]]
    assert changed == [], f"these cards look different from the recorded ones: {changed}"
