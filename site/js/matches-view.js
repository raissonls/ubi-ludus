// The lists of matches on the home page (FR-23): the next matches of the followed teams, today and
// this week, drawn as match cards, followed teams first. The visitor picks the list with three
// buttons; until they do, the page picks it: their teams if they follow any, else today.

import { el } from './dom.js';
import { EMPTY_FILTERS, activeCount, createMatchFilter } from './filters.js';
import { daysFrom, defaultView, nextMatch, selectMatches } from './home-views.js';
import { describeHorizonNotice, uncoveredCompetitions } from './horizon.js';
import { createCalendar } from './calendar.js';
import { clockPhase, createLiveClock } from './live-clock.js';
import { formatDate } from './format.js';
import { renderHero } from './hero.js';
import { renderMatchCard } from './match-card.js';
import { accessibleBroadcasters, describeMatch } from './match-model.js';
import { renderPoster } from './poster.js';
import { planRails } from './rails-plan.js';
import { matchReportUrl } from './report.js';
import { createSheet } from './sheet.js';

const FREE_KINDS = new Set(['free_tv', 'youtube']);

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
  setOnlyWatchable = () => {},
  onCompetition = () => {},
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
  const nextSection = document.getElementById('next-match');
  const nextCard = document.getElementById('next-match-card');
  const status = document.getElementById('matches-status');
  const horizon = document.getElementById('horizon-notice');
  const uncovered = document.getElementById('uncovered');
  const uncoveredSummary = document.getElementById('uncovered-summary');
  const uncoveredList = document.getElementById('uncovered-list');
  const buttons = [...document.querySelectorAll('#view-switch [data-view]')];
  const quickButtons = [...document.querySelectorAll('#quick-filters [data-quick]')];
  const sheetList = document.getElementById('match-sheet-card');
  // The full card in the sheet is kept in step with the clock when it opens; no timer of its own.
  const sheetClock = createLiveClock({ root: sheetList, translator, clock });
  const sheet = createSheet({ onShown: () => sheetClock.update() });
  // Cards say where their match stands (a countdown, live, probably over) and keep saying it as
  // time passes.
  const liveClock = createLiveClock({ root: list, translator, clock });
  liveClock.start();
  let teamIds = [];
  let accessible = accessibleBroadcasters([], data);
  let onlyWatchable = false;
  let chosen = initial.view ?? null; // the list the visitor picked, if they have
  let filters = { ...EMPTY_FILTERS, ...initial.filters };
  const quick = { live: false, free: false }; // the chips above the lists; not kept in the address

  const current = () => chosen ?? defaultView(teamIds);

  // The full card of a match: what the sheet shows (every broadcaster, the calendar, the report link).
  function fullCard(match, followedTeam) {
    const model = describeMatch(match, data, { accessible });
    return renderMatchCard(model, {
      translator,
      accentTeam: followedTeam,
      reportHref: matchReportUrl(model, translator),
      onCalendar: () => {
        calendar.saveMatch(match);
        calendarStatus.textContent = translator.t('calendar.saved');
      },
    });
  }

  // A match as a poster in a row; pressing it opens the sheet with the full card.
  function poster(match, index, followedTeam) {
    const model = describeMatch(match, data, { accessible });
    const item = renderPoster(model, {
      translator,
      followed: followedTeam !== null,
      onOpen: () => sheet.open(fullCard(match, followedTeam)),
    });
    item.classList.add('match-card--enter');
    item.style.setProperty('--enter-step', String(Math.min(index, ENTER_STEPS)));
    return item;
  }

  function railTitle(row, now) {
    if (row.kind === 'live') return translator.t('rails.live');
    if (row.kind === 'mine') return translator.t('matches.groupMine');
    if (row.kind === 'next') return translator.t('rails.next');
    if (row.kind === 'competition') return data.competitionsById.get(row.id)?.name ?? row.id;
    const [today, tomorrow] = daysFrom(now, 2);
    if (row.id === today) return translator.t('rails.today');
    if (row.id === tomorrow) return translator.t('rails.tomorrow');
    const text = formatDate(`${row.id}T12:00:00Z`);
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  // One row: a title, "see all" (the row wraps into a grid), and the posters.
  function rail(row, now, followedIds) {
    const id = `rail-${row.kind}-${row.id}`;
    const title = railTitle(row, now);
    const cards = row.matches.map((match, index) => {
      const teamId = [match.home_team_id, match.away_team_id].find((found) => followedIds.has(found));
      return poster(match, index, teamId ? (data.teamsById.get(teamId) ?? null) : null);
    });
    const head = [el('h3', { class: 'rail__title matches-group__title', id: `${id}-title`, text: title })];
    const section = el('section', { class: `matches-group rail rail--${row.kind}`, 'aria-labelledby': `${id}-title` }, [
      el('div', { class: 'rail__head' }, head),
      el('ul', { class: 'matches rail__track', id: `${id}-track` }, cards),
    ]);
    if (cards.length > 2) {
      const more = el('button', { type: 'button', class: 'rail__more', 'aria-expanded': 'false', 'aria-controls': `${id}-track` });
      const label = (open) => {
        more.textContent = translator.t(open ? 'rails.less' : 'rails.more');
        more.setAttribute('aria-label', translator.t(open ? 'rails.lessFor' : 'rails.moreFor', { title }));
      };
      label(false);
      more.addEventListener('click', () => {
        const open = more.getAttribute('aria-expanded') !== 'true';
        more.setAttribute('aria-expanded', String(open));
        section.classList.toggle('is-expanded', open);
        label(open);
      });
      section.firstChild.append(more);
    }
    return section;
  }

  function draw() {
    const view = current();
    const now = clock();
    // Only a match we know the visitor cannot watch is hidden: with no broadcaster known, nothing
    // is known, and a match that is over has nothing to watch either way.
    const canBeWatched = (match) => describeMatch(match, data, { accessible }).access !== 'no';
    // On now: inside the window after kickoff. A match the data still calls live long after that
    // has run past any normal length ("probably over"), so it is not "live now".
    const isLive = (match) => {
      const phase = clockPhase({ status: match.status, kickoff: match.kickoff_utc }, now)?.phase;
      return phase === 'live' || (match.status === 'live' && phase !== 'over');
    };
    const isFree = (match) => {
      const model = describeMatch(match, data, { accessible });
      return model.showBroadcasts && model.badges.some((badge) => FREE_KINDS.has(badge.kind));
    };
    const passesFilters = createMatchFilter(data, filters);
    const keep = (match) =>
      passesFilters(match) &&
      (!onlyWatchable || canBeWatched(match)) &&
      (!quick.live || isLive(match)) &&
      (!quick.free || isFree(match));
    const { followed, others } = selectMatches(view, data.matches, teamIds, now, keep);
    const total = followed.length + others.length;
    const followedIds = new Set(teamIds);
    const rows = planRails({ view, followed, others, isLive });
    list.replaceChildren(...rows.map((row) => rail(row, now, followedIds)));
    showNext(now, view);
    showHorizonNotice([...followed, ...others]);
    liveClock.update();
    showCalendarAll();
    list.hidden = total === 0;
    empty.hidden = total > 0;
    const allHidden = total === 0 && hasMatches(view, now);
    let emptyText = emptyKey(view);
    if (allHidden) {
      const narrowed = activeCount(filters) > 0 || quick.live || quick.free;
      emptyText = narrowed ? 'matches.emptyFilters' : 'matches.emptyFiltered';
    }
    empty.textContent = translator.t(emptyText);
    for (const button of buttons) {
      button.setAttribute('aria-pressed', String(button.dataset.view === view));
    }
    paintQuick();
    const label = buttons.find((button) => button.dataset.view === view)?.textContent ?? '';
    status.textContent = translator.plural('matches.shown', total, { view: label });
  }

  // The chips above the lists: all, live now, what I can watch, free TV only, and the competition
  // (which opens the filters). They narrow the lists; "all" puts everything back.
  function paintQuick() {
    const none = !quick.live && !quick.free && !onlyWatchable;
    for (const button of quickButtons) {
      const name = button.dataset.quick;
      if (name === 'competition') continue;
      const on = name === 'all' ? none : name === 'watchable' ? onlyWatchable : quick[name];
      button.setAttribute('aria-pressed', String(on));
    }
  }

  for (const button of quickButtons) {
    button.addEventListener('click', () => {
      const name = button.dataset.quick;
      if (name === 'competition') {
        onCompetition();
        return;
      }
      if (name === 'all') {
        quick.live = false;
        quick.free = false;
        if (onlyWatchable) setOnlyWatchable(false); // the choices redraw the lists
        else draw();
        return;
      }
      if (name === 'watchable') {
        setOnlyWatchable(!onlyWatchable);
        return;
      }
      quick[name] = !quick[name];
      draw();
    });
  }

  // The next match of the followed teams in the list being shown (today's, the week's, or the
  // next of all), big, above the list: the one on now, else the soonest. The filters do not hide
  // it; a list with none of their matches has no big card.
  function showNext(now, view) {
    const next = teamIds.length > 0 ? nextMatch(view, data.matches, teamIds, now) : null;
    nextSection.hidden = next === null;
    nextCard.replaceChildren(
      ...(next ? [renderHero(describeMatch(next, data, { accessible }), { translator })] : []),
    );
  }

  // FR-34: say it when a competition we only know until tomorrow is in the list, or is the one
  // being looked at, or when the list is empty and some competitions are like that. The text is
  // only replaced when it changes, so a screen reader does not read it again at every redraw.
  function showHorizonNotice(shown) {
    const notice = describeHorizonNotice({ shown, data, selectedId: filters.competition });
    let text = '';
    if (notice !== null) {
      text = translator.has(notice.key)
        ? translator.t(notice.key, notice.values)
        : translator.plural(notice.key, notice.count, notice.values);
    }
    horizon.hidden = text === '';
    if (horizon.textContent !== text) horizon.textContent = text;
  }

  // The competitions we have no data for, listed once: the data does not change while the page
  // is open, and an empty list is not hidden because of a filter (PRD risk R1).
  function showUncovered() {
    const names = uncoveredCompetitions(data);
    uncovered.hidden = names.length === 0;
    if (names.length === 0) return;
    uncoveredSummary.textContent = translator.plural('uncovered.summary', names.length);
    uncoveredList.replaceChildren(...names.map((name) => el('li', { text: name })));
  }
  showUncovered();

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
