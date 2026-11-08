// The next match of the teams the visitor follows, as one big card at the top of the home page:
// both shirts, when, and above all where to watch. It says what a match card says (the model
// comes from match-model.js, the broadcasters from match-card.js); only the shape is different.

import { el } from './dom.js';
import { formatDateTime } from './format.js';
import { renderWatch, roundText, stateBadge } from './match-card.js';
import { shirtOf } from './onboarding-model.js';
import { createShirt } from './shirt.js';

/** @param model from describeMatch(); @param translator from i18n.js */
export function renderHero(model, { translator }) {
  const heroId = `hero-${model.id}`;
  const round = roundText(model.round, translator);
  const when = el('p', { class: 'hero__when' }, [
    el('time', { datetime: model.kickoff, text: formatDateTime(model.kickoff) }),
    el('span', { text: ` · ${round ? `${model.competition} · ${round}` : model.competition}` }),
  ]);
  const state = stateBadge(model, translator);
  if (state) when.append(' ', state);

  const side = (part) => createShirt(shirtOf(part.team), 92);
  const name = (part) => part.name ?? translator.t('matches.tbd');
  const card = el('div', { class: 'hero', id: heroId, 'data-state': model.state, 'data-confidence': model.confidence }, [
    when,
    el('div', { class: 'hero__shirts', 'aria-hidden': 'true' }, [
      side(model.home),
      el('span', { class: 'hero__versus', text: translator.t('card.versus') }),
      side(model.away),
    ]),
    el('h4', { class: 'hero__title', id: `${heroId}-title`, text: `${name(model.home)} ${translator.t('card.versus')} ${name(model.away)}` }),
  ]);
  if (model.showBroadcasts) card.append(renderWatch(model, translator, heroId));
  return card;
}
