"""The morning e-mail as written (FR-40, FR-43): HTML and plain text, and everything escaped."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_email_briefing import FIXTURES, NOW, broadcast, documents, match, owner

from ubi_ludus.email.briefing import (
    Briefing,
    BriefingMatch,
    BroadcasterLine,
    build_briefing,
    load_documents,
)
from ubi_ludus.email.render import (
    long_date,
    main,
    render_briefing,
    round_text,
    subject_for,
)
from ubi_ludus.pipeline.window import BRAZIL_TZ

HOSTILE = "<script>alert(1)</script><img src=x onerror=alert(2)>\"'&"
SCRIPT = "<script"


def one(**changes: object) -> BriefingMatch:
    base = BriefingMatch(
        id="a",
        home="Palmeiras",
        away="Flamengo",
        accent="#006437",
        competition="Série A",
        round="34",
        kickoff=datetime(2026, 11, 3, 22, 0, tzinfo=UTC).astimezone(BRAZIL_TZ),
        status="scheduled",
        broadcasters=(),
        access="unknown",
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def briefing(
    mine: tuple[BriefingMatch, ...] = (), notable: tuple[BriefingMatch, ...] = (), **kw: object
) -> Briefing:
    base = Briefing(
        day=date(2026, 11, 3), mine=mine, notable=notable, notable_more=0, stale_since=None
    )
    return replace(base, **kw)  # type: ignore[arg-type]


class Audit(HTMLParser):
    """Everything an e-mail client would have to load or run."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.attrs: list[tuple[str, str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self.attrs.extend((tag, name, value) for name, value in attrs)


def audit(html: str) -> Audit:
    parser = Audit()
    parser.feed(html)
    return parser


# --- words -------------------------------------------------------------------------------------


def test_the_date_is_written_in_portuguese() -> None:
    assert long_date(date(2026, 11, 3)) == "terça-feira, 3 de novembro"
    assert long_date(date(2026, 3, 1)) == "domingo, 1 de março"


def test_a_round_reads_as_a_matchday_or_a_stage() -> None:
    assert round_text("34") == "Rodada 34"
    assert round_text("quarter-finals") == "Quartas de final"
    assert round_text("last-8") == "Last 8"
    assert round_text(None) is None


def test_the_subject_says_the_first_match_and_how_many_more() -> None:
    first = one()
    other = one(id="b", home="Brasil", away="Chile")
    assert subject_for(briefing((first,))) == "Hoje: Palmeiras x Flamengo, 19:00"
    assert subject_for(briefing((first, other))) == "Hoje: Palmeiras x Flamengo, 19:00 (+1 jogo)"
    assert subject_for(briefing((first, other, other))) == (
        "Hoje: Palmeiras x Flamengo, 19:00 (+2 jogos)"
    )
    assert subject_for(briefing(notable=(first,))) == "Hoje: sem jogos dos seus times, 1 destaque"
    assert subject_for(briefing(notable=(first,), notable_more=2)) == (
        "Hoje: sem jogos dos seus times, 3 destaques"
    )
    assert subject_for(briefing()) == "Hoje: sem jogos dos seus times"


def test_the_subject_is_one_line_whatever_the_names() -> None:
    hostile = one(home="Time\r\nBcc: someone@example.org", away="Outro\nTime")
    email = render_briefing(briefing((hostile,)))
    assert "\n" not in email.subject and "\r" not in email.subject


# --- what each match shows --------------------------------------------------------------------


def test_the_kickoff_is_in_brazils_time() -> None:
    email = render_briefing(briefing((one(),)))
    assert "19:00" in email.html and "19:00" in email.text  # 22:00 in UTC
    assert "22:00" not in email.html


def test_broadcasters_say_what_is_confirmed_and_which_the_owner_has() -> None:
    given = documents(
        [
            match(
                "a",
                "palmeiras",
                "flamengo",
                broadcasts=[broadcast("globo", "confirmed"), broadcast("sportv", "rule")],
            )
        ]
    )
    email = render_briefing(build_briefing(given, owner(), NOW))
    assert "Onde assistir:" in email.html
    assert "✔ TV Globo (confirmado); SporTV" in email.html
    assert "✔ TV Globo (confirmado); SporTV" in email.text
    assert "Dá para assistir com os seus serviços" in email.html
    assert "tabela de direitos" in email.html  # SporTV is from the rights table: check again


def test_all_confirmed_asks_for_no_check() -> None:
    given = documents(
        [match("a", "palmeiras", "flamengo", broadcasts=[broadcast("globo", "confirmed")])]
    )
    email = render_briefing(build_briefing(given, owner(), NOW))
    assert "tabela de direitos" not in email.html + email.text


def test_a_match_the_owner_cannot_watch_says_so_in_words() -> None:
    given = documents([match("a", "palmeiras", "flamengo", broadcasts=[broadcast("sportv")])])
    email = render_briefing(build_briefing(given, owner(services=()), NOW))
    assert "Fora dos seus serviços" in email.html and "Fora dos seus serviços" in email.text


def test_a_match_with_no_known_broadcaster_names_none_and_says_so() -> None:
    given = documents(
        [match("a", "palmeiras", "flamengo", broadcasts=[broadcast(None, "unknown")])]
    )
    email = render_briefing(build_briefing(given, owner(), NOW))
    assert "Transmissão ainda não confirmada" in email.html
    assert not re.search(r"Globo|SporTV|Onde assistir", email.html + email.text)


def test_a_postponed_match_says_so_instead_of_a_time_and_names_no_broadcaster() -> None:
    off = one(status="postponed", access=None, broadcasters=())
    email = render_briefing(briefing((off,)))
    assert "Adiado" in email.html and "Adiado" in email.text
    assert "19:00" not in email.html
    assert "Onde assistir" not in email.html


def test_a_match_on_now_says_so() -> None:
    assert "Ao vivo" in render_briefing(briefing((one(status="live"),))).html


# --- sections, notes and the footer -----------------------------------------------------------


def test_the_sections_are_in_order_and_the_extra_notable_ones_are_counted() -> None:
    email = render_briefing(
        briefing((one(),), (one(id="b", home="Inter", away="PSG"),), notable_more=2)
    )
    assert email.html.index("Jogos dos seus times") < email.html.index("Destaques do dia")
    assert email.text.index("JOGOS DOS SEUS TIMES") < email.text.index("DESTAQUES DO DIA")
    assert "E mais 2 jogos nesta competição hoje." in email.html
    assert "E mais 2 jogos nesta competição hoje." in email.text


def test_an_empty_day_says_so() -> None:
    email = render_briefing(briefing())
    assert "Hoje não há jogos" in email.html and "Hoje não há jogos" in email.text
    assert "Nenhum jogo dos seus times hoje" in email.html
    assert "Jogos dos seus times" not in email.html  # no empty section


def test_old_data_is_said_up_top() -> None:
    since = datetime(2026, 11, 1, 7, 0, tzinfo=BRAZIL_TZ)
    email = render_briefing(briefing((one(),), stale_since=since))
    assert "podem estar desatualizados" in email.html
    assert "1/11 às 07:00" in email.text
    assert email.html.index("desatualizados") < email.html.index("Jogos dos seus times")
    assert "desatualizados" not in render_briefing(briefing((one(),))).html


def test_the_link_to_the_site_is_kept_only_if_it_is_a_web_address() -> None:
    email = render_briefing(briefing((one(),)), site_url="https://example.org/ubi-ludus/")
    assert 'href="https://example.org/ubi-ludus/"' in email.html
    assert "https://example.org/ubi-ludus/" in email.text
    for bad in ("javascript:alert(1)", 'https://x.org/"onmouseover="alert(1)', "//x.org", ""):
        other = render_briefing(briefing((one(),)), site_url=bad)
        assert "href=" not in other.html
        assert "Ver todos os jogos" not in other.text


# --- everything is escaped ---------------------------------------------------------------------


def test_names_from_the_data_are_text_not_markup() -> None:
    hostile = one(
        home=HOSTILE,
        away="Time\r\nBcc: x",
        competition=HOSTILE,
        round=HOSTILE,
        broadcasters=(BroadcasterLine(HOSTILE, "confirmed", True),),
        access="yes",
    )
    email = render_briefing(briefing((hostile,), (hostile,)), site_url="https://x.org/?a=1&b=2")
    found = audit(email.html)
    assert SCRIPT not in email.html.lower()
    assert "img" not in found.tags and "script" not in found.tags
    assert all(name != "onerror" for _, name, _ in found.attrs)
    assert "&lt;script&gt;" in email.html
    assert "?a=1&amp;b=2" in email.html  # an & in an address is escaped
    # The plain text has no markup to break, but no line break can be smuggled into a line.
    assert "Time Bcc: x" in email.text


def test_a_colour_from_the_data_is_used_only_if_it_is_a_hex_colour() -> None:
    good = render_briefing(briefing((one(accent="#112233"),))).html
    assert "border-left:6px solid #112233" in good
    for bad in ("red;background:url(//evil.example/x)", "#12", 'expression("x")', "#12345g"):
        html = render_briefing(briefing((one(accent=bad),))).html
        assert "evil.example" not in html and "expression" not in html
        assert "border-left:6px solid #5b6475" in html  # the grey one


# --- what an e-mail client may be asked to load ----------------------------------------------


def test_the_html_loads_nothing_and_runs_nothing() -> None:
    given = documents(
        [
            match("a", "palmeiras", "flamengo", broadcasts=[broadcast("globo", "confirmed")]),
            match("b", "inter", "psg", competition="champions"),
        ]
    )
    email = render_briefing(build_briefing(given, owner(), NOW), site_url="https://example.org/")
    found = audit(email.html)
    forbidden = {"script", "img", "link", "iframe", "object", "embed", "form", "video", "audio"}
    assert forbidden.isdisjoint(found.tags)
    sources = [
        (tag, name, value)
        for tag, name, value in found.attrs
        if name in {"src", "srcset", "background"}
    ]
    assert sources == []  # no image, no tracking pixel
    assert [v for t, n, v in found.attrs if n == "href"] == ["https://example.org/"]
    assert not re.search(r"url\(|@import|<link", email.html)
    assert not any(name.startswith("on") for _, name, _ in found.attrs)


def test_the_html_is_a_complete_accessible_document_made_of_tables() -> None:
    email = render_briefing(briefing((one(),)))
    found = audit(email.html)
    assert email.html.startswith("<!doctype html>")
    assert ("html", "lang", "pt-BR") in found.attrs
    assert ("meta", "name", "viewport") in found.attrs
    assert ("meta", "name", "color-scheme") in found.attrs
    assert "title" in found.tags and "h1" in found.tags and "h2" in found.tags
    tables = [(t, n, v) for t, n, v in found.attrs if t == "table" and n == "role"]
    assert tables and all(v == "presentation" for _, _, v in tables)
    assert found.tags.count("table") == len(tables)  # every table is layout, none is data


def test_every_colour_is_inline_so_a_client_that_drops_style_still_reads_it() -> None:
    html = render_briefing(briefing((one(access="yes"),))).html
    body = html.split("</style>", 1)[1]
    assert "background:#f2f4f7" in body and "color:#1a1d23" in body
    assert "background:#e3f4e8;color:#0b5d2a" in body  # the "can watch" strip
    # The only rules in <style> are for dark mode.
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    assert "prefers-color-scheme: dark" in style
    assert not re.search(
        r"^\s*[.#a-z][^{]*\{",
        re.sub(r"@media[^{]*\{(.*)\}\s*$", "", style.strip(), flags=re.S),
        re.M,
    )


def test_the_text_and_the_html_say_the_same_things() -> None:
    given = documents(
        [
            match(
                "a",
                "palmeiras",
                "flamengo",
                "2026-11-03T22:00:00Z",
                broadcasts=[broadcast("globo", "confirmed")],
            ),
            match("b", "brasil", None, "2026-11-03T15:00:00Z", broadcasts=[broadcast("sportv")]),
            match("c", "inter", "psg", "2026-11-03T20:00:00Z", competition="champions"),
        ]
    )
    email = render_briefing(build_briefing(given, owner(), NOW))
    for needle in (
        "Palmeiras x Flamengo",
        "Brasil x A definir",
        "Inter x PSG",
        "12:00",
        "19:00",
        "17:00",
        "TV Globo",
    ):
        assert needle in email.html, needle
        assert needle in email.text, needle
    assert email.text.index("12:00") < email.text.index("19:00")  # by time


# --- from the real files ----------------------------------------------------------------------


def test_the_real_published_data_renders() -> None:
    real = build_briefing(
        load_documents(FIXTURES), owner(teams=("palmeiras",), services=("globoplay",)), NOW
    )
    email = render_briefing(real)
    assert "Palmeiras x Flamengo" in email.html
    assert not re.search(r"\$\w|\[\w+\.\w+\]", email.html + email.text)  # no hole left unfilled


def test_the_preview_command_writes_both_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["--data", str(FIXTURES), "--out", str(tmp_path), "--now", "2026-11-03T11:00:00Z"])
        == 0
    )
    assert (tmp_path / "briefing.html").read_text("utf-8").startswith("<!doctype html>")
    assert "Jogos de hoje" in (tmp_path / "briefing.txt").read_text("utf-8")
    assert "Hoje:" in capsys.readouterr().out
