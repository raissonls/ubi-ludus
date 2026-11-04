// The lists of matches on the home page (FR-23): the next matches of the followed teams, today and
// this week, drawn as match cards, followed teams first. The visitor picks the list with three
// buttons; until they do, the page picks it: their teams if they follow any, else today.

import { el } from './dom.js';
import { EMPTY_FILTERS, activeCount, createMatchFilter } from './filters.js';
import { defaultView, selectMatches } from './home-views.js';
import { createCalendar } from './calendar.js';
import { createLiveClock } from './live-clock.js';
import { renderMatchCard } from './match-card.js';
import { accessibleBroadcasters, describeMatch } from './match-model.js';
import { matchReportUrl } from './report.js';

/** Cards after this one enter together, so a long list does not take long to appear. */
const ENTER_STEPS = 6;

/**
 * @param initial        {view, filters} from the address, if it said anything
 * @param onStateChange  called after the visitor picks a list or a filter changes
 */
export function createMatchesView({
  data,
  translator,
  clock = () => new Date(),
  initial = {},
  onStateChange = () => {},
}) {
  const list = document.getElementById('matches-list');
  const calendarRow = document.getElementById('calendar-all-row');
  const calendarAll = document.getElementById('calendar-all');
  const calendarStatus = document.getElementById('calendar-status');
  const calendar = createCalendar({
    data,
    translator,
    clock,
    url: `${location.origin}${location.pathname}`,
  });
  const empty = document.getElementById('matches-empty');
  const status = document.getElementById('matches-status');
  const buttons = [...document.querySelectorAll('#view-switch [data-view]')];
  // Cards say where their match stands (a countdown, live, probably over) and keep saying it as
  // time passes.
  const liveClock = createLiveClock({ root: list, translator, clock });
  liveClock.start();
  let teamIds = [];
  let accessible = accessibleBroadcasters([], data);
  let onlyWatchable = false;
  let chosen = initial.view ?? null; // the list the visitor picked, if they have
  let filters = { ...EMPTY_FILTERS, ...initial.filters };

  const current = () => chosen ?? defaultView(teamIds);

  function card(match, index, followedTeam) {
    const model = describeMatch(match, data, { accessible });
    const item = renderMatchCard(model, {
      translator,
      accentTeam: followedTeam,
      reportHref: matchReportUrl(model, translator),
      onCalendar: () => {
        calendar.saveMatch(match);
        calendarStatus.textContent = translator.t('calendar.saved');
      },
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
    const passesFilters = createMatchFilter(data, filters);
    const keep = (match) => passesFilters(match) && (!onlyWatchable || canBeWatched(match));
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
    liveClock.update();
    showCalendarAll();
    list.hidden = total === 0;
    empty.hidden = total > 0;
    const allHidden = total === 0 && hasMatches(view, now);
    let emptyText = emptyKey(view);
    if (allHidden) {
      emptyText = activeCount(filters) > 0 ? 'matches.emptyFilters' : 'matches.emptyFiltered';
    }
    empty.textContent = translator.t(emptyText);
    for (const button of buttons) {
      button.setAttribute('aria-pressed', String(button.dataset.view === view));
    }
    const label = buttons.find((button) => button.dataset.view === view)?.textContent ?? '';
    status.textContent = translator.plural('matches.shown', total, { view: label });
  }

  // "All my teams" in one file: offered when the visitor follows teams that have matches to come.
  function showCalendarAll() {
    const count = teamIds.length === 0 ? 0 : calendar.upcoming(teamIds).length;
    calendarRow.hidden = count === 0;
    calendarAll.textContent = translator.plural('calendar.all', count);
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

  calendarAll.addEventListener('click', () => {
    const count = calendar.saveFollowed(teamIds);
    calendarStatus.textContent = translator.plural('calendar.savedAll', count);
  });

  for (const button of buttons) {
    button.addEventListener('click', () => {
      chosen = button.dataset.view;
      draw();
      onStateChange(state());
    });
  }

  function state() {
    return { view: chosen, filters: { ...filters } };
  }

  return {
    /** The list the visitor picked (null if they have not) and the filters now set. */
    state,
    /** Set the filters (competition, broadcaster, team search) and draw again. */
    setFilters(next) {
      filters = { ...EMPTY_FILTERS, ...next };
      draw();
      onStateChange(state());
    },
    /** Draw the list for the teams and services the visitor has chosen now. */
    render({ teams, services, onlyWatchable: only }) {
      teamIds = teams;
      accessible = accessibleBroadcasters(services, data);
      onlyWatchable = only;
      draw();
    },
  };
}
