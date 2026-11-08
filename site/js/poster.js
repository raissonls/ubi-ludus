// A match as a poster, one card in a row ("rail") like a title in a streaming app: both shirts over
// a wash of the two teams' colours, the time, the teams and where to watch. It is light on purpose;
// the whole card is one button that opens the details (js/sheet.js), where every broadcaster, the
// calendar and the report link are. It keeps the match card's attributes and class names
// (data-state, data-kickoff, .match-card__when, .match-card__teams) so the clock, the filters
// and the tests find it the same way.

import { el } from './dom.js';
import { formatDateTime, formatDayMonth, formatTime } from './format.js';
import { renderBadge, roundText, stateBadge } from './match-card.js';
import { shirtOf } from './onboarding-model.js';
import { createShirt, safeColours } from './shirt.js';

const FREE_KINDS = new Set(['free_tv', 'youtube']);
/** How many broadcasters a poster names; the rest are counted. */
export const POSTER_BADGES = 2;

/** Free TV and YouTube cost nobody anything: "free", else "paid", or null when nothing is known. */
export function priceOf(model) {
  if (model.confidence === 'unknown' || !model.showBroadcasts) return null;
  return model.badges.some((badge) => FREE_KINDS.has(badge.kind)) ? 'free' : 'paid';
}

/** The broadcasters to name on a poster: the ones the visitor can watch first, then the free ones. */
export function postersBadges(model) {
  const weight = (badge) => (badge.accessible === true ? 0 : FREE_KINDS.has(badge.kind) ? 1 : 2);
  return [...model.badges].sort((a, b) => weight(a) - weight(b));
}

function washFrom(team) {
  return safeColours(shirtOf(team)).primary;
}

/**
 * @param model       from describeMatch()
 * @param translator  from i18n.js
 * @param followed    true when a team the visitor follows plays
 * @param onOpen      called when the poster is pressed
 */
export function renderPoster(model, { translator, followed = false, onOpen }) {
  const cardId = `card-${model.id}`;
  const name = (side) => side.name ?? translator.t('matches.tbd');
  const teams = `${name(model.home)} ${translator.t('card.versus')} ${name(model.away)}`;
  const price = priceOf(model);
  const named = postersBadges(model);

  const state = stateBadge(model, translator);
  let chip;
  if (state) {
    chip = el('span', { class: 'poster__chip poster__chip--state' }, [state]);
  } else if (price) {
    const words = price === 'free' ? translator.t('poster.free') : translator.t('poster.paid');
    chip = el('span', { class: `poster__chip poster__chip--${price}`, text: words });
  } else {
    chip = el('span', { class: 'poster__chip poster__chip--none', text: translator.t('poster.unknown') });
  }

  const open = el('button', { type: 'button', class: 'poster__open', 'aria-haspopup': 'dialog' }, [teams]);
  open.setAttribute(
    'aria-label',
    [teams, formatDateTime(model.kickoff), named[0]?.name, translator.t('poster.details')].filter(Boolean).join(', '),
  );
  open.addEventListener('click', onOpen);

  const where = el('div', { class: 'poster__where' });
  if (model.showBroadcasts && model.confidence !== 'unknown') {
    where.append(
      el(
        'ul',
        { class: 'badges poster__badges', 'aria-label': translator.t('card.watch') },
        named.slice(0, POSTER_BADGES).map((item) => renderBadge(item, translator)),
      ),
    );
    if (named.length > POSTER_BADGES) {
      where.append(el('span', { class: 'poster__more', text: translator.t('poster.more', { count: named.length - POSTER_BADGES }) }));
    }
  }
  if (model.access === 'yes') {
    where.append(el('span', { class: 'poster__can', text: translator.t('poster.can') }));
  }

  const round = roundText(model.round, translator);
  const card = el(
    'li',
    {
      class: 'match-card match-card--poster',
      id: cardId,
      'data-state': model.state,
      'data-confidence': model.confidence,
      'data-kickoff': model.kickoff, // for live-clock.js
    },
    [
      el('div', { class: 'poster__top' }, [chip, el('span', { class: 'poster__day', text: formatDayMonth(model.kickoff) })]),
      el('div', { class: 'poster__shirts', 'aria-hidden': 'true' }, [
        createShirt(shirtOf(model.home.team), 56),
        createShirt(shirtOf(model.away.team), 56),
      ]),
      el('p', { class: 'match-card__when' }, [el('time', { datetime: model.kickoff, text: formatTime(model.kickoff) })]),
      el('h4', { class: 'match-card__teams', id: `${cardId}-title` }, [open]),
      el('p', { class: 'match-card__competition', text: round ? `${model.competition} · ${round}` : model.competition }),
      where,
    ],
  );
  if (model.access) card.dataset.access = model.access;
  if (followed) card.dataset.followed = 'true';
  if (model.shortHorizon) {
    card.dataset.horizon = 'short';
    card.append(el('p', { class: 'match-card__horizon', text: translator.t('horizon.card') }));
  }
  card.style.setProperty('--home', washFrom(model.home.team));
  card.style.setProperty('--away', washFrom(model.away.team));
  return card;
}
