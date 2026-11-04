"""Write the morning e-mail: an HTML layout and a plain-text one (PRD FR-40, FR-43).

The layouts are files in ``templates/`` with ``$name`` holes. Everything that comes from data goes
through :func:`html.escape` before it is put in a hole (or, for the plain text, has its control
characters removed), so a team called ``<script>`` is text. The HTML is what e-mail clients accept:
tables for layout, every colour inline, no script, no image, no external file (so nothing is loaded
when the message is opened: no tracking, no crests, PRD R5).
"""

from __future__ import annotations

import re
import sys
from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from importlib import resources
from pathlib import Path
from string import Template

from ubi_ludus.email.briefing import (
    Briefing,
    BriefingMatch,
    BroadcasterLine,
    build_briefing,
    load_documents,
)
from ubi_ludus.pipeline.owner import OwnerConfig, load_owner
from ubi_ludus.pipeline.window import BRAZIL_TZ

_WEEKDAYS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
_MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
_STAGES = {
    "final": "Final",
    "semi-finals": "Semifinal",
    "quarter-finals": "Quartas de final",
    "last-16": "Oitavas de final",
    "last-32": "16 avos de final",
    "last-64": "32 avos de final",
    "play-offs": "Play-offs",
    "group-stage": "Fase de grupos",
    "league-stage": "Fase de liga",
}
_STATE_WORD = {"postponed": "Adiado", "cancelled": "Cancelado", "live": "Ao vivo"}
CHECK_NOTE = "As emissoras sem “confirmado” vêm da tabela de direitos: confira perto do jogo."
_ACCESS_WORD = {
    "yes": "✔ Dá para assistir com os seus serviços",
    "no": "Fora dos seus serviços",
    "unknown": "Transmissão ainda não confirmada",
}

_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_FALLBACK_ACCENT = "#5b6475"
_SANS = "Arial,Helvetica,sans-serif"
NOTHING_TODAY = "Nenhum jogo dos seus times hoje, nem destaque nas competições que você acompanha."


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


def _template(name: str) -> Template:
    return Template(
        resources.files("ubi_ludus.email").joinpath("templates", name).read_text("utf-8")
    )


def _clean(value: object) -> str:
    """Text from data on one line: control characters (line breaks too) become one space."""
    flat = _CONTROL.sub(" ", str(value)).replace("\r", " ").replace("\n", " ")
    return re.sub(r" {2,}", " ", flat).strip()


def _safe_url(url: str | None) -> str | None:
    """An address we may link to: http or https, with nothing that could end an attribute."""
    if url and re.fullmatch(r"https?://[^\s\"'<>`]+", url):
        return url
    return None


# --- words ----------------------------------------------------------------------------------


def long_date(day: date) -> str:
    return f"{_WEEKDAYS[day.weekday()]}, {day.day} de {_MONTHS[day.month - 1]}"


def round_text(value: str | None) -> str | None:
    if not value:
        return None
    if value.isdigit():
        return f"Rodada {int(value)}"
    return _STAGES.get(value) or value.replace("-", " ").capitalize()


def teams_text(match: BriefingMatch) -> str:
    return f"{_clean(match.home or 'A definir')} x {_clean(match.away or 'A definir')}"


def when_text(match: BriefingMatch) -> str:
    """The time in Brazil, or the word when the match is not on at that time."""
    if match.status in ("postponed", "cancelled"):
        return _STATE_WORD[match.status]
    return match.kickoff.astimezone(BRAZIL_TZ).strftime("%H:%M")


def _competition_text(match: BriefingMatch) -> str:
    round_label = round_text(match.round)
    name = _clean(match.competition)
    return f"{name} · {_clean(round_label)}" if round_label else name


def broadcaster_text(line: BroadcasterLine) -> str:
    mark = "✔ " if line.accessible else ""
    sure = " (confirmado)" if line.confidence == "confirmed" else ""
    return f"{mark}{_clean(line.name)}{sure}"


def subject_for(briefing: Briefing) -> str:
    if briefing.mine:
        first = briefing.mine[0]
        extra = len(briefing.mine) - 1
        more = f" (+{extra} {'jogo' if extra == 1 else 'jogos'})" if extra else ""
        return f"Hoje: {teams_text(first)}, {when_text(first)}{more}"
    if briefing.notable:
        count = len(briefing.notable) + briefing.notable_more
        word = "destaque" if count == 1 else "destaques"
        return f"Hoje: sem jogos dos seus times, {count} {word}"
    return "Hoje: sem jogos dos seus times"


def _heading(briefing: Briefing) -> str:
    if briefing.is_empty:
        return "Hoje não há jogos"
    return "Jogos de hoje"


def _stale_text(briefing: Briefing) -> str | None:
    if briefing.stale_since is None:
        return None
    since = briefing.stale_since
    return (
        "Atenção: os dados podem estar desatualizados "
        f"(última atualização em {since.day}/{since.month:02d} às {since:%H:%M}). "
        "Confira a emissora e o horário perto do jogo."
    )


# --- HTML -----------------------------------------------------------------------------------


def _html_match(match: BriefingMatch) -> str:
    accent = match.accent if match.accent and _COLOUR.fullmatch(match.accent) else _FALLBACK_ACCENT
    when = escape(when_text(match))
    state = _STATE_WORD.get(match.status)
    badge = ""
    if state and match.status == "live":
        badge = f" <strong>· {escape(state)}</strong>"
    rows = [
        f'<p class="muted" style="margin:0 0 2px 0;font-size:14px;line-height:20px;color:#4a5160;">'
        f'<strong class="text" style="font-size:18px;color:#1a1d23;">{when}</strong>'
        f"{badge}</p>",
        f'<h3 class="text" style="margin:0;font-size:17px;line-height:23px;color:#1a1d23;">'
        f"{escape(teams_text(match))}</h3>",
        f'<p class="muted" style="margin:2px 0 0 0;font-size:14px;line-height:20px;color:#4a5160;">'
        f"{escape(_competition_text(match))}</p>",
    ]
    # A postponed or cancelled match has the word at the top and no broadcaster: it is not on.
    if match.status not in ("postponed", "cancelled") and match.broadcasters:
        names = "; ".join(escape(broadcaster_text(line)) for line in match.broadcasters)
        rows.append(
            '<p class="text" style="margin:8px 0 0 0;font-size:14px;line-height:20px;'
            'color:#1a1d23;">'
            f"<strong>Onde assistir:</strong> {names}</p>"
        )
        if any(line.confidence != "confirmed" for line in match.broadcasters):
            rows.append(
                '<p class="muted" style="margin:2px 0 0 0;font-size:13px;line-height:19px;'
                'color:#4a5160;">'
                f"{escape(CHECK_NOTE)}</p>"
            )
    if match.access is not None:
        kind = {"yes": "good", "no": "warn", "unknown": "muted"}[match.access]
        style = {
            "good": "background:#e3f4e8;color:#0b5d2a;",
            "warn": "background:#fff1de;color:#7a3b00;",
            "muted": "background:#eceff3;color:#33394a;",
        }[kind]
        rows.append(
            f'<p class="{kind}" style="margin:8px 0 0 0;padding:4px 8px;font-size:14px;'
            f'line-height:20px;font-weight:bold;border-radius:4px;{style}">'
            f"{escape(_ACCESS_WORD[match.access])}</p>"
        )
    body = "\n".join(rows)
    return (
        '<tr><td style="padding:0 0 10px 0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'class="card" style="table-layout:fixed;background:#ffffff;border:1px solid #c9ced6;'
        f'border-left:6px solid {accent};border-radius:6px;">'
        f'<tr><td style="padding:12px 14px;font-family:{_SANS};word-break:break-word;'
        f'overflow-wrap:anywhere;">\n{body}\n</td></tr>'
        "</table></td></tr>"
    )


def _html_section(title: str, matches: Sequence[BriefingMatch], more: int = 0) -> str:
    if not matches:
        return ""
    rows = [
        f'<tr><td style="padding:8px 4px 8px 4px;font-family:{_SANS};">'
        f'<h2 class="text" style="margin:0;font-size:17px;line-height:23px;color:#1a1d23;">'
        f"{escape(title)}</h2></td></tr>"
    ]
    rows += [_html_match(match) for match in matches]
    if more:
        word = "jogo" if more == 1 else "jogos"
        rows.append(
            f'<tr><td style="padding:0 4px 10px 4px;font-family:{_SANS};">'
            '<p class="muted" style="margin:0;font-size:14px;line-height:20px;color:#4a5160;">'
            f"E mais {more} {word} nesta competição hoje.</p></td></tr>"
        )
    return "\n".join(rows)


def _html_note(text: str, kind: str) -> str:
    style = {
        "warn": "background:#fff1de;color:#7a3b00;border:1px solid #e0b27a;",
        "plain": "background:#eceff3;color:#33394a;border:1px solid #c9ced6;",
    }[kind]
    css = "warn" if kind == "warn" else "muted"
    return (
        f'<tr><td style="padding:0 0 12px 0;font-family:{_SANS};">'
        f'<p class="{css}" style="margin:0;padding:10px 12px;font-size:14px;line-height:20px;'
        f'border-radius:6px;{style}">{escape(text)}</p></td></tr>'
    )


def _footer(site_url: str | None) -> tuple[str, str]:
    base = "Horários de Brasília. A emissora pode mudar: confira perto do jogo."
    url = _safe_url(site_url)
    if url is None:
        return escape(base), base
    link = (
        f'<a class="link" href="{escape(url)}" style="color:#0b4ea2;">'
        "Ver todos os jogos no Ubi Ludus</a>"
    )
    return f"{escape(base)} {link}", f"{base}\nVer todos os jogos: {url}"


def render_html(briefing: Briefing, *, site_url: str | None = None) -> str:
    stale = _stale_text(briefing)
    sections = [
        _html_note(NOTHING_TODAY, "plain") if briefing.is_empty else "",
        _html_section("Jogos dos seus times", briefing.mine),
        _html_section("Destaques do dia", briefing.notable, briefing.notable_more),
    ]
    footer_html, _ = _footer(site_url)
    return _template("briefing.html").substitute(
        title=escape(subject_for(briefing)),
        preheader=escape(_preheader(briefing)),
        heading=escape(_heading(briefing)),
        date=escape(long_date(briefing.day)),
        stale=_html_note(stale, "warn") if stale else "",
        sections="\n".join(part for part in sections if part),
        footer=footer_html,
    )


def _preheader(briefing: Briefing) -> str:
    matches = [*briefing.mine, *briefing.notable]
    return " · ".join(f"{when_text(m)} {teams_text(m)}" for m in matches[:3])


# --- plain text -----------------------------------------------------------------------------


def _text_match(match: BriefingMatch) -> str:
    lines = [f"* {when_text(match)}  {teams_text(match)}", f"  {_competition_text(match)}"]
    if match.status not in ("postponed", "cancelled") and match.broadcasters:
        lines.append(
            "  Onde assistir: " + "; ".join(broadcaster_text(b) for b in match.broadcasters)
        )
        if any(b.confidence != "confirmed" for b in match.broadcasters):
            lines.append(f"  {CHECK_NOTE}")
    if match.access is not None:
        lines.append(f"  {_ACCESS_WORD[match.access]}")
    return "\n".join(lines)


def _text_section(title: str, matches: Sequence[BriefingMatch], more: int = 0) -> str:
    if not matches:
        return ""
    body = "\n\n".join(_text_match(match) for match in matches)
    tail = (
        f"\nE mais {more} {'jogo' if more == 1 else 'jogos'} nesta competição hoje." if more else ""
    )
    return f"{title.upper()}\n{'-' * len(title)}\n{body}{tail}\n\n"


def render_text(briefing: Briefing, *, site_url: str | None = None) -> str:
    stale = _stale_text(briefing)
    parts = [f"{stale}\n\n" if stale else ""]
    if briefing.is_empty:
        parts.append(f"{NOTHING_TODAY}\n\n")
    parts.append(_text_section("Jogos dos seus times", briefing.mine))
    parts.append(_text_section("Destaques do dia", briefing.notable, briefing.notable_more))
    _, footer_text = _footer(site_url)
    return _template("briefing.txt").substitute(
        heading=_heading(briefing),
        date=long_date(briefing.day),
        stale=parts[0],
        sections="".join(parts[1:]),
        footer=footer_text,
    )


def render_briefing(briefing: Briefing, *, site_url: str | None = None) -> RenderedEmail:
    """Subject, HTML and plain text of the morning e-mail."""
    return RenderedEmail(
        subject=_clean(subject_for(briefing)),
        html=render_html(briefing, site_url=site_url),
        text=render_text(briefing, site_url=site_url),
    )


# --- a preview to look at, for the manual check in mail clients ----------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Write today's e-mail from the published data to two files, to open or send to oneself."""
    parser = ArgumentParser(description="Render the morning e-mail from the published data.")
    parser.add_argument("--data", type=Path, default=Path("site/data"))
    parser.add_argument("--out", type=Path, default=Path("email-preview"))
    parser.add_argument("--now", help="a moment in ISO 8601, e.g. 2026-11-03T11:00:00Z")
    parser.add_argument("--site-url", default=None)
    args = parser.parse_args(argv)
    now = (
        datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now
        else datetime.now(BRAZIL_TZ)
    )
    owner: OwnerConfig = load_owner()
    briefing = build_briefing(load_documents(args.data), owner, now)
    email = render_briefing(briefing, site_url=args.site_url)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "briefing.html").write_text(email.html, encoding="utf-8", newline="\n")
    (args.out / "briefing.txt").write_text(email.text, encoding="utf-8", newline="\n")
    print(f"{email.subject}\n-> {args.out}/briefing.html and briefing.txt")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
