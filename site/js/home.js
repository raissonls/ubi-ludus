// The home page once its data is here: the pickers, the lists, the filters and the shared view.
// main.js calls this once, when the data has loaded (from the network or from the saved copy).

import { createFiltersView } from './filters-view.js';
import { filterOptions } from './filters.js';
import { VIEWS } from './home-views.js';
import { createMatchesView } from './matches-view.js';
import { createOnboarding } from './onboarding.js';
import { restrictTo } from './preferences.js';
import { createServicesPicker } from './services-picker.js';
import { createShare } from './share.js';
import { createTeamPicker } from './teams-picker.js';
import { buildSearch, parseUrlState } from './url-state.js';

export function mountHome({ data, translator, preferences }) {
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
    setOnlyWatchable: (value) => preferences.setOnlyWatchable(value),
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
  const onboarding = createOnboarding({ data, translator, preferences });
  document.getElementById('reopen-onboarding').addEventListener('click', () => onboarding.open({ from: 'continents' }));
  const onlyWatchable = document.getElementById('only-watchable');
  onlyWatchable.addEventListener('change', () => preferences.setOnlyWatchable(onlyWatchable.checked));

  function show() {
    const choices = chosen();
    picker.update(choices.teams);
    servicesPicker.update(choices.services);
    onlyWatchable.checked = choices.onlyWatchable;
    filtersView.setExtra(choices.onlyWatchable ? 1 : 0);
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

  // A new visitor, with nothing chosen and not arriving from a shared link, starts with the flow.
  // (With storage refused nothing can be remembered, so the flow would come back on every load.)
  if (!shared && preferences.isPersistent() && !preferences.isOnboarded() && chosen().teams.length === 0) {
    onboarding.open({ from: 'welcome' });
  }
}
