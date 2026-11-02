"""The weekly review report (PRD FR-14): what needs the owner's attention.

Two things are listed, because they are where the broadcast information goes wrong quietly:

* upcoming matches of the teams the owner follows whose broadcast is ``unknown``;
* rights rules that end within 30 days (and rules that ended, with nothing to replace them),
  after which matches silently fall back to ``unknown``.

The report is read from a built warehouse: the ``matches``, ``teams`` and ``competitions`` marts
for the matches, and the rights table for the rules. It is rendered as Markdown; the weekly
workflow publishes it as a GitHub issue.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from ubi_ludus.pipeline.owner import OwnerConfig, load_owner
from ubi_ludus.pipeline.rights import RightsData, RightsRule, load_rights
from ubi_ludus.pipeline.run import build_warehouse
from ubi_ludus.pipeline.window import BRAZIL_TZ, today_in_brazil

DEFAULT_DATABASE = Path(__file__).resolve().parents[3] / "dbt" / "target" / "ubi_ludus.duckdb"
DEFAULT_OUT = Path("review-report.md")
EXPIRY_DAYS = 30
MAX_ROWS = 50
# Not strftime: its day and month names follow the machine's language.
_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


@dataclass(frozen=True)
class FollowedMatch:
    match_id: str
    kickoff: datetime
    """In Brazil's time zone."""
    competition: str
    home: str
    away: str
    confidence: str
    """The match as a whole: ``confirmed`` if any broadcast is, else ``rule``, else ``unknown``."""


@dataclass(frozen=True)
class RuleEnding:
    rule: RightsRule
    days_left: int
    """Negative when the rule has already ended."""


@dataclass(frozen=True)
class ReviewReport:
    generated_at: datetime
    followed: tuple[FollowedMatch, ...]
    """Upcoming matches of followed teams, whatever their broadcasts."""
    ending: tuple[RuleEnding, ...] = field(default=())
    ended_without_successor: tuple[RuleEnding, ...] = field(default=())

    @property
    def unknown(self) -> tuple[FollowedMatch, ...]:
        return tuple(m for m in self.followed if m.confidence == "unknown")

    def count(self, confidence: str) -> int:
        return sum(1 for m in self.followed if m.confidence == confidence)


def build_review(
    database: Path, *, owner: OwnerConfig, rights: RightsData, now: datetime
) -> ReviewReport:
    """Query the marts of ``database`` and the rights table for what needs a look."""
    today = today_in_brazil(now)
    con = duckdb.connect(str(database))
    try:
        rows = con.execute(
            "select m.id, m.kickoff_utc, c.name, coalesce(h.short_name, 'to be decided'), "
            "coalesce(a.short_name, 'to be decided'), "
            "list_transform(m.broadcasts, lambda b: b.confidence) "
            "from matches as m "
            "inner join competitions as c on m.competition_id = c.id "
            "left join teams as h on m.home_team_id = h.id "
            "left join teams as a on m.away_team_id = a.id "
            "where m.status in ('scheduled', 'rescheduled') "
            "and (list_contains(?, m.home_team_id) or list_contains(?, m.away_team_id)) "
            "order by m.kickoff_utc, m.id",
            [list(owner.teams), list(owner.teams)],
        ).fetchall()
    finally:
        con.close()

    followed = []
    for match_id, kickoff_utc, competition, home, away, confidences in rows:
        kickoff = datetime.fromisoformat(kickoff_utc).astimezone(BRAZIL_TZ)
        if kickoff.date() < today:
            continue  # already played or playing today's earlier slot: nothing left to fix
        followed.append(
            FollowedMatch(match_id, kickoff, competition, home, away, _overall(confidences))
        )

    ending, ended = _rule_endings(rights.rules, today)
    return ReviewReport(now.astimezone(UTC), tuple(followed), ending, ended)


def _overall(confidences: Sequence[str]) -> str:
    if "confirmed" in confidences:
        return "confirmed"
    return "unknown" if "unknown" in confidences else "rule"


def _rule_endings(
    rules: Sequence[RightsRule], today: date
) -> tuple[tuple[RuleEnding, ...], tuple[RuleEnding, ...]]:
    ending: list[RuleEnding] = []
    ended: list[RuleEnding] = []
    for rule in rules:
        days_left = (rule.valid_to - today).days
        if 0 <= days_left <= EXPIRY_DAYS:
            ending.append(RuleEnding(rule, days_left))
        elif -EXPIRY_DAYS <= days_left < 0:
            still_covered = any(
                other.competition_id == rule.competition_id
                and other.season == rule.season
                and other.valid_to >= today
                for other in rules
            )
            if not still_covered:
                ended.append(RuleEnding(rule, days_left))
    return tuple(sorted(ending, key=_by_end)), tuple(sorted(ended, key=_by_end))


def _by_end(entry: RuleEnding) -> tuple[date, str]:
    return entry.rule.valid_to, entry.rule.competition_id


# --- Markdown ----------------------------------------------------------------------------------


def render_markdown(report: ReviewReport) -> str:
    """The report as Markdown: a title line, a summary, then one section per list."""
    local = report.generated_at.astimezone(BRAZIL_TZ)
    lines = [
        f"# Weekly review: {local.day} {_MONTHS[local.month - 1]} {local.year}",
        "",
        f"Generated {report.generated_at:%Y-%m-%d %H:%M} UTC ({local:%H:%M} in Brazil) "
        "from the latest pipeline run.",
        "",
        "## Summary",
        "",
        f"- Upcoming matches of your teams: **{len(report.followed)}** "
        f"({report.count('confirmed')} confirmed, {report.count('rule')} from rules, "
        f"**{report.count('unknown')} unknown**)",
        f"- Rights rules ending within {EXPIRY_DAYS} days: **{len(report.ending)}**",
        f"- Rights rules that ended with nothing to replace them: "
        f"**{len(report.ended_without_successor)}**",
        "",
        "## Unknown matches of your teams",
        "",
    ]
    lines += _unknown_section(report)
    lines += ["", f"## Rights rules ending within {EXPIRY_DAYS} days", ""]
    lines += _rules_section(report.ending, "None. Nothing runs out soon.")
    lines += ["", "## Rules that ended without a replacement", ""]
    lines += _rules_section(
        report.ended_without_successor,
        "None. Every competition that lost a rule in the last "
        f"{EXPIRY_DAYS} days has another one in force.",
    )
    return "\n".join(lines) + "\n"


def _unknown_section(report: ReviewReport) -> list[str]:
    unknown = report.unknown
    if not unknown:
        return ["None. Every upcoming match of your teams has a broadcaster."]
    lines = [
        "Nothing is known about where these will be shown. Find out, then add an override to "
        "`data/rights/overrides.yml` (or add a rights rule if the whole competition is missing).",
        "",
        "| When (Brazil) | Competition | Match | Match id |",
        "|---|---|---|---|",
    ]
    for match in unknown[:MAX_ROWS]:
        k = match.kickoff
        when = f"{_DAYS[k.weekday()]} {k.day:02d} {_MONTHS[k.month - 1]}, {k:%H:%M}"
        lines.append(
            f"| {when} | {match.competition} | {match.home} x {match.away} | `{match.match_id}` |"
        )
    if len(unknown) > MAX_ROWS:
        lines.append(f"| ... | {len(unknown) - MAX_ROWS} more | | |")
    lines += [
        "",
        "```yaml",
        "# data/rights/overrides.yml",
        "- match_id: <match id above>",
        "  action: replace",
        "  broadcasters: [<broadcaster ids from broadcasters.yml>]",
        '  reason: "Where you found out, and when"',
        f"  added_at: {report.generated_at.astimezone(BRAZIL_TZ):%Y-%m-%d}",
        "```",
    ]
    return lines


def _rules_section(entries: Sequence[RuleEnding], empty: str) -> list[str]:
    if not entries:
        return [empty]
    lines = [
        "| Last day | Days | Competition | Season | Covers | Broadcasters | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in entries[:MAX_ROWS]:
        rule = entry.rule
        covers = "all matches" if rule.scope == "all" else f"{rule.scope} {rule.scope_value}"
        days = f"in {entry.days_left}" if entry.days_left >= 0 else f"{-entry.days_left} ago"
        lines.append(
            f"| {rule.valid_to:%Y-%m-%d} | {days} | `{rule.competition_id}` | {rule.season} | "
            f"{covers} | {', '.join(rule.broadcasters)} | {rule.source} |"
        )
    return lines


# --- command line ------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m ubi_ludus.pipeline.review``: write the report as a Markdown file."""
    parser = argparse.ArgumentParser(description="Write the weekly review report as Markdown.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--run",
        action="store_true",
        help="run the pipeline first (calls the providers; needs their keys in the environment)",
    )
    parser.add_argument("--cache-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    if args.run:
        build_warehouse(args.database, now=now, cache_dir=args.cache_dir)
    rights = load_rights()
    report = build_review(args.database, owner=load_owner(rights=rights), rights=rights, now=now)
    args.out.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {args.out}: {len(report.unknown)} unknown, {len(report.ending)} ending")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
