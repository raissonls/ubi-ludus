// Entry point: the strings, the visitor's choices and the published data. The views that use
// them come in the next tasks (M3-03 onwards).

import { loadData } from './data.js';
import { applyStrings, createTranslator, loadStrings } from './i18n.js';
import { createPreferences } from './preferences.js';

const strings = await loadStrings(new URL('../i18n/pt-BR.json', import.meta.url));
const translator = createTranslator(strings);
applyStrings(document, translator);

// "Reset my data" (FR-22): forget the saved choices, in storage and in memory.
const preferences = createPreferences();
document.getElementById('reset-data').addEventListener('click', () => {
  preferences.reset();
  document.getElementById('reset-result').textContent = translator.t('footer.resetDone');
});

const status = document.getElementById('data-status');
try {
  const data = await loadData(new URL('../data/', import.meta.url));
  status.textContent = translator.plural('home.matchesLoaded', data.matches.length);
} catch (error) {
  status.textContent = translator.t('home.loadFailed');
  console.error(error);
}

// Tests and styles can tell the page is ready, loaded or not.
document.documentElement.dataset.ready = 'true';
