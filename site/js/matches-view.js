// The lists of matches on the home page (FR-23): the next matches of the followed teams, today and
// this week, drawn as match cards, followed teams first. The visitor picks the list with three
// buttons; until they do, the page picks it: their teams if they follow any, else today.

import { el } from './dom.js';
import { defaultView, selectMatches } from './home-views.js';
import { renderMatchCard } from './match-card.js';
import { accessibleBroadcasters, describeMatch } from './match-model.js';

/** Cards after this one enter together, so a long list does not take long to appear. */
const ENTER_STEPS = 6;

export function createMatchesView({ data, translator, clock = () => new Date() }) {
  const list = document.getElementById('matches-list');
  const empty = document.getElementById('matches-empty');
  const status = document.getElementById('matches-status');
  const buttons = [...document.querySelectorAll('#view-switch [data-view]')];
  let teamIds = [];
  let accessible = accessibleBroadcasters([], data);
  let onlyWatchable = false;
  let chosen = null; // the list the visitor picked, if they have

  const current = () => chosen ?? defaultView(teamIds);

  function card(match, index, followedTeam) {
    const item = renderMatchCard(describeMatch(match, data, { accessible }), {
      translator,
      accentTeam: followedTeam,
    });
    item.classList.add('match-card--enter');
    item.style.setProperty('--enter-step', String(Math.min(index, ENTER_STEPS)));
    if (followedTeam) {
      item.dataset.followed = 'true';
    }
    return item;
  }

  function group(matches, followedAll, title) {
    const followed = new Set(teamIds);
    const cards = matches.map((match, index) => {
      const id = [match.home_team_id, match.away_team_id].find((teamId) => followed.has(teamId));
      return card(match, index, followedAll ? (data.teamsById.get(id) ?? null) : null);
    });
    return el('div', { class: 'matches-group' }, [
      ...(title ? [el('p', { class: 'matches-group__title', text: title })] : []),
      el('ul', { class: 'matches' }, cards),
    ]);
  }

  function draw() {
    const view = current();
    const now = clock();
    // Only a match we know the visitor cannot watch is hidden: with no broadcaster known, nothing
    // is known, and a match that is over has nothing to watch either way.
    const canBeWatched = (match) => describeMatch(match, data, { accessible }).access !== 'no';
    const keep = onlyWatchable ? canBeWatched : undefined;
    const { followed, others } = selectMatches(view, data.matches, teamIds, now, keep);
    const total = followed.length + others.length;
    const titled = followed.length > 0 && others.length > 0;
    const groups = [];
    if (followed.length > 0) {
      groups.push(group(followed, true, titled ? translator.t('matches.groupMine') : ''));
    }
    if (others.length > 0) {
      groups.push(group(others, false, titled ? translator.t('matches.groupOthers') : ''));
    }
    list.replaceChildren(...groups);
    list.hidden = total === 0;
    empty.hidden = total > 0;
    const allHidden = onlyWatchable && total === 0 && hasMatches(view, now);
    empty.textContent = translator.t(allHidden ? 'matches.emptyFiltered' : emptyKey(view));
    for (const button of buttons) {
      button.setAttribute('aria-pressed', String(button.dataset.view === view));
    }
    const label = buttons.find((button) => button.dataset.view === view)?.textContent ?? '';
    status.textContent = translator.plural('matches.shown', total, { view: label });
  }

  function hasMatches(view, now) {
    const { followed, others } = selectMatches(view, data.matches, teamIds, now);
    return followed.length + others.length > 0;
  }

  function emptyKey(view) {
    if (view === 'mine') {
      return teamIds.length === 0 ? 'matches.pickPrompt' : 'matches.empty';
    }
    return view === 'today' ? 'matches.emptyToday' : 'matches.emptyWeek';
  }

  for (const button of buttons) {
    button.addEventListener('click', () => {
      chosen = button.dataset.view;
      draw();
    });
  }

  return {
    /** Draw the list for the teams and services the visitor has chosen now. */
    render({ teams, services, onlyWatchable: only }) {
      teamIds = teams;
      accessible = accessibleBroadcasters(services, data);
      onlyWatchable = only;
      draw();
    },
  };
}
