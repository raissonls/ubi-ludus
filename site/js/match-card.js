// The match card (FR-24): the teams, the competition and round, the kickoff in Brazil's time, where
// to watch and how sure we are of it. What it says comes from match-model.js; this only draws it,
// with safe DOM calls (text is always text).
//
// A state is never told by colour alone: every one has a word ("Ao vivo", "Adiado"), and a
// broadcaster we are sure of has a tick next to it. FR-13: when nothing is known no broadcaster is
// named, only "Transmissão ainda não confirmada".

import { el, setAccent } from './dom.js';
import { formatDateTime } from './format.js';

/** Past this many badges the rest wait behind a "+N" button, so a card stays short. */
export const BADGES_SHOWN = 4;

const STATE_KEY = {
  live: 'card.states.live',
  finished: 'card.states.finished',
  postponed: 'card.states.postponed',
  cancelled: 'card.states.cancelled',
  rescheduled: 'card.states.rescheduled',
};
// What a screen reader adds after a broadcaster's name; short, because it repeats on every badge.
const BADGE_KEY = { confirmed: 'card.badge.confirmed', rule: 'card.badge.rule' };
const CONFIDENCE_KEY = {
  confirmed: 'card.confidence.confirmed',
  rule: 'card.confidence.rule',
  unknown: 'card.confidence.unknown',
};

function roundText(round, translator) {
  if (!round) return null;
  if (round.kind === 'matchday') return translator.t('card.round', { number: round.number });
  const key = ['card.stages', round.slug].join('.');
  if (translator.has(key)) return translator.t(key);
  // A stage we have no word for yet: "last-8" reads as "Last 8" rather than not at all.
  const words = round.slug.replace(/-/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function team(side, translator) {
  const swatch = el('span', { class: 'swatch', 'aria-hidden': 'true' });
  if (side.team) setAccent(swatch, side.team);
  return [swatch, ' ', side.name ?? translator.t('matches.tbd')];
}

function badge(item, translator) {
  const sure = item.confidence === 'confirmed';
  return el('li', { class: `badge badge--${item.confidence}` }, [
    sure ? el('span', { 'aria-hidden': 'true', text: '✓ ' }) : '',
    el('span', { text: item.name }),
    el('span', {
      class: 'visually-hidden',
      text: ` (${translator.t(BADGE_KEY[item.confidence])})`,
    }),
  ]);
}

function watch(model, translator, cardId) {
  if (model.confidence === 'unknown') {
    return el('p', { class: 'confidence confidence--unknown', text: translator.t(CONFIDENCE_KEY.unknown) });
  }
  const badges = model.badges.map((item) => badge(item, translator));
  const list = el('ul', { class: 'badges', id: `${cardId}-badges`, 'aria-labelledby': `${cardId}-watch` }, badges);
  const children = [el('p', { class: 'match-card__label', id: `${cardId}-watch`, text: translator.t('card.watch') }), list];

  const hidden = badges.slice(BADGES_SHOWN);
  if (hidden.length > 0) {
    for (const item of hidden) item.hidden = true;
    const more = el('button', { type: 'button', class: 'badges__more', 'aria-expanded': 'false', 'aria-controls': list.id });
    const label = (open) => {
      more.textContent = open ? translator.t('card.less') : translator.t('card.more', { count: hidden.length });
      more.setAttribute('aria-label', open ? translator.t('card.lessLabel') : translator.plural('card.moreLabel', hidden.length));
    };
    label(false);
    more.addEventListener('click', () => {
      const open = more.getAttribute('aria-expanded') !== 'true';
      more.setAttribute('aria-expanded', String(open));
      for (const item of hidden) item.hidden = !open;
      label(open);
    });
    children.push(more);
  }
  children.push(el('p', { class: `confidence confidence--${model.confidence}`, text: translator.t(CONFIDENCE_KEY[model.confidence]) }));
  return el('div', { class: 'match-card__watch' }, children);
}

/**
 * One card, as a list item.
 *
 * @param model     from describeMatch()
 * @param translator  from i18n.js
 * @param accentTeam a team whose colours become the card's accent bar (the followed team), or null
 */
export function renderMatchCard(model, { translator, accentTeam = null }) {
  const cardId = `card-${model.id}`;
  const when = el('p', { class: 'match-card__when' }, [
    el('time', { datetime: model.kickoff, text: formatDateTime(model.kickoff) }),
  ]);
  if (STATE_KEY[model.state]) {
    const live = model.state === 'live';
    when.append(
      el('span', { class: `state state--${model.state}` }, [
        live ? el('span', { 'aria-hidden': 'true', text: '● ' }) : '',
        el('span', { text: translator.t(STATE_KEY[model.state]) }),
      ]),
    );
  }

  const title = el('h3', { class: 'match-card__teams', id: `${cardId}-title` }, [
    ...team(model.home, translator),
    ` ${translator.t('card.versus')} `,
    ...team(model.away, translator),
  ]);
  const round = roundText(model.round, translator);
  const competition = el('p', {
    class: 'match-card__competition',
    text: round ? `${model.competition} · ${round}` : model.competition,
  });

  const card = el(
    'li',
    { class: 'match-card', id: cardId, 'data-state': model.state, 'data-confidence': model.confidence },
    [when, title, competition],
  );
  if (model.showBroadcasts) card.append(watch(model, translator, cardId));
  if (accentTeam) setAccent(card, accentTeam);
  return card;
}
