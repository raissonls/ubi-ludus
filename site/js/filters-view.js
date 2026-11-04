// The filter controls (FR-27): a list of competitions, a list of broadcasters and a search box for
// a team, in a "Filtros" box that stays closed until wanted. The summary says how many are set,
// so closed it still tells. Which matches pass is filters.js; this only draws and listens.

import { el } from './dom.js';
import { EMPTY_FILTERS, activeCount, filterOptions } from './filters.js';

function fill(select, allText, options) {
  select.replaceChildren(
    el('option', { value: '', text: allText }),
    ...options.map((option) => el('option', { value: option.id, text: option.name })),
  );
}

export function createFiltersView({ data, translator, initial = EMPTY_FILTERS, onChange }) {
  const box = document.getElementById('filters');
  const summary = document.getElementById('filters-summary');
  const competition = document.getElementById('filter-competition');
  const broadcaster = document.getElementById('filter-broadcaster');
  const team = document.getElementById('filter-team');
  const options = filterOptions(data);

  fill(competition, translator.t('filters.allCompetitions'), options.competitions);
  fill(broadcaster, translator.t('filters.allBroadcasters'), options.broadcasters);

  const read = () => ({ competition: competition.value, broadcaster: broadcaster.value, q: team.value });

  function show(filters) {
    competition.value = filters.competition;
    broadcaster.value = filters.broadcaster;
    team.value = filters.q;
    const count = activeCount(filters);
    summary.textContent = count > 0 ? translator.t('filters.titleActive', { count }) : translator.t('filters.title');
    if (count > 0) box.open = true; // a view that arrives filtered shows its filters
  }

  for (const control of [competition, broadcaster]) {
    control.addEventListener('change', () => onChange(read()));
  }
  team.addEventListener('input', () => onChange(read()));
  document.getElementById('filters-clear').addEventListener('click', () => onChange({ ...EMPTY_FILTERS }));

  show(initial);
  return { show };
}
