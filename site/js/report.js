// The "report a wrong broadcast" link (FR-30): a new issue on the project's GitHub repository with
// the match and what the site shows already filled in, so the visitor only says what is right.
//
// The link carries the match and its broadcasters, nothing about the visitor: not their teams,
// not their services. Following it is the visitor's own click, and the only time this site sends
// anyone to GitHub.

import { formatDateTime } from './format.js';

export const REPO_URL = 'https://github.com/raissonls/ubi-ludus';
const TEMPLATE = 'wrong-broadcast.yml';

function withQuery(fields) {
  const query = new URLSearchParams({ template: TEMPLATE, ...fields });
  return `${REPO_URL}/issues/new?${query}`;
}

/** The link for no match in particular (the footer's). */
export function generalReportUrl() {
  return withQuery({});
}

/** The link for one match, from describeMatch()'s model. */
export function matchReportUrl(model, translator) {
  const teams = [model.home, model.away]
    .map((side) => side.name ?? translator.t('matches.tbd'))
    .join(` ${translator.t('card.versus')} `);
  const shown =
    model.badges.length === 0
      ? translator.t('report.nothingShown')
      : model.badges
          .map((badge) => `${badge.name} (${translator.t(`card.badge.${badge.confidence}`)})`)
          .join(', ');
  return withQuery({
    title: `${translator.t('report.title')}: ${teams}`,
    match: `${teams} · ${model.competition} · ${formatDateTime(model.kickoff)} · ${model.id}`,
    shown,
  });
}
