// Entry point: the strings, the visitor's choices and the published data, and the views that use
// them. More views come in the next tasks (M3-04 onwards).

import { loadData } from './data.js';
import { applyStrings, createTranslator, loadStrings } from './i18n.js';
import { createMatchesView } from './matches-view.js';
import { createPreferences, restrictTo } from './preferences.js';
import { createTeamPicker } from './teams-picker.js';

const strings = await loadStrings(new URL('../i18n/pt-BR.json', import.meta.url));
const translator = createTranslator(strings);
applyStrings(document, translator);

const preferences = createPreferences();
const status = document.getElementById('data-status');

try {
  const data = await loadData(new URL('../data/', import.meta.url));
  status.textContent = translator.plural('home.matchesLoaded', data.matches.length);

  // The choices that are saved may name a team that has since gone: keep only the ones we know.
  const known = { teams: new Set(data.teamsById.keys()), services: new Set(data.servicesById.keys()) };
  const chosenTeams = () => restrictTo(preferences.get(), known).teams;

  const picker = createTeamPicker({
    teams: data.teams,
    translator,
    onChange: (ids) => preferences.setTeams(ids),
  });
  const matches = createMatchesView({ data, translator });

  function show() {
    picker.update(chosenTeams());
    matches.render(chosenTeams());
  }
  preferences.subscribe(show);
  show();
} catch (error) {
  status.textContent = translator.t('home.loadFailed');
  console.error(error);
}

// "Reset my data" (FR-22): forget the saved choices, in storage and in memory. The views follow.
document.getElementById('reset-data').addEventListener('click', () => {
  preferences.reset();
  document.getElementById('reset-result').textContent = translator.t('footer.resetDone');
});

// Tests and styles can tell the page is ready, loaded or not.
document.documentElement.dataset.ready = 'true';
