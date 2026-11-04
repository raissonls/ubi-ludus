// Entry point: the strings, the visitor's choices and the published data, and the views that use
// them.

import { loadData } from './data.js';
import { filterOptions } from './filters.js';
import { createFiltersView } from './filters-view.js';
import { describeFreshness } from './freshness.js';
import { VIEWS } from './home-views.js';
import { applyStrings, createTranslator, loadStrings } from './i18n.js';
import { createMatchesView } from './matches-view.js';
import { createPreferences, restrictTo } from './preferences.js';
import { createServicesPicker } from './services-picker.js';
import { createShare } from './share.js';
import { createTeamPicker } from './teams-picker.js';
import { buildSearch, parseUrlState } from './url-state.js';

const strings = await loadStrings(new URL('../i18n/pt-BR.json', import.meta.url));
const translator = createTranslator(strings);
applyStrings(document, translator);

const preferences = createPreferences();
const status = document.getElementById('data-status');

try {
  const data = await loadData(new URL('../data/', import.meta.url));
  status.textContent = translator.plural('home.matchesLoaded', data.matches.length);
  showFreshness(data.status);

  // The choices that are saved may name a team that has since gone: keep only the ones we know.
  const known = { teams: new Set(data.teamsById.keys()), services: new Set(data.servicesById.keys()) };
  const chosen = () => restrictTo(preferences.get(), known);

  const picker = createTeamPicker({
    teams: data.teams,
    translator,
    onChange: (ids) => preferences.setTeams(ids),
  });
  const servicesPicker = createServicesPicker({
    services: data.services,
    broadcastersById: data.broadcastersById,
    translator,
    onChange: (ids) => preferences.setServices(ids),
  });
  // The address may ask for a view: filters, a list, and (from a shared link) teams and services.
  // Every value is checked against what the data has; what does not fit is ignored.
  const options = filterOptions(data);
  const fromAddress = parseUrlState(location.search, {
    views: new Set(VIEWS),
    competitions: new Set(options.competitions.map((option) => option.id)),
    broadcasters: new Set(options.broadcasters.map((option) => option.id)),
    teams: known.teams,
    services: known.services,
  });
  // A shared link shows its teams and services for this visit and saves nothing, until the visitor
  // changes their own choices.
  let shared = fromAddress.teams !== null || fromAddress.services !== null || fromAddress.onlyWatchable !== null;
  if (shared) {
    preferences.adopt(fromAddress);
  }
  const notice = document.getElementById('shared-notice');
  notice.hidden = !shared;

  function syncAddress() {
    const { view, filters } = matches.state();
    const search = buildSearch({ view, filters, choices: shared ? chosen() : null });
    try {
      history.replaceState(null, '', `${location.pathname}${search}${location.hash}`);
    } catch {
      // Some embedding contexts refuse; the view still works, it just is not in the address.
    }
  }

  const matches = createMatchesView({
    data,
    translator,
    initial: { view: fromAddress.view, filters: fromAddress.filters },
    onStateChange: (state) => {
      filtersView.show(state.filters);
      syncAddress();
    },
  });
  const filtersView = createFiltersView({
    data,
    translator,
    initial: fromAddress.filters,
    onChange: (filters) => matches.setFilters(filters),
  });
  createShare({
    translator,
    link: () => {
      const { view, filters } = matches.state();
      return `${location.origin}${location.pathname}${buildSearch({ view, filters, choices: chosen() })}`;
    },
  });
  const onlyWatchable = document.getElementById('only-watchable');
  onlyWatchable.addEventListener('change', () => preferences.setOnlyWatchable(onlyWatchable.checked));

  function show() {
    const choices = chosen();
    picker.update(choices.teams);
    servicesPicker.update(choices.services);
    onlyWatchable.checked = choices.onlyWatchable;
    matches.render(choices);
  }
  preferences.subscribe(() => {
    if (shared) {
      shared = false; // the visitor made the choices their own
      notice.hidden = true;
    }
    show();
    syncAddress();
  });
  show();
} catch (error) {
  status.textContent = translator.t('home.loadFailed');
  console.error(error);
}

// How old the data is (FR-30). A warning when it is old or was never recorded.
function showFreshness(statusDocument) {
  const element = document.getElementById('freshness');
  const found = describeFreshness(statusDocument, new Date());
  const text = translator.t(found.key, found.values);
  element.dataset.state = found.state;
  element.replaceChildren(
    ...(found.state === 'fresh' ? [] : [warningMark()]),
    document.createTextNode(text),
  );
  element.hidden = false;
}

function warningMark() {
  const mark = document.createElement('span');
  mark.setAttribute('aria-hidden', 'true');
  mark.textContent = '⚠ ';
  return mark;
}

// "Reset my data" (FR-22): forget the saved choices, in storage and in memory. The views follow.
document.getElementById('reset-data').addEventListener('click', () => {
  preferences.reset();
  document.getElementById('reset-result').textContent = translator.t('footer.resetDone');
});

// Tests and styles can tell the page is ready, loaded or not.
document.documentElement.dataset.ready = 'true';
