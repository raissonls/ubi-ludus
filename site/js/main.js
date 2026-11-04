// Entry point: the strings, the visitor's choices and the published data. It shows the loading
// screen, loads the data (from the network, else from the copy kept from the last time), and then
// mounts the home page; if that cannot be done it shows the screen for what went wrong (states.js).

import { createDataCache } from './data-cache.js';
import { loadBest } from './data-source.js';
import { describeFreshness } from './freshness.js';
import { mountHome } from './home.js';
import { applyStrings, createTranslator, loadStrings } from './i18n.js';
import { createPreferences } from './preferences.js';
import { createStates, problemKind } from './states.js';

const strings = await loadStrings(new URL('../i18n/pt-BR.json', import.meta.url));
const translator = createTranslator(strings);
applyStrings(document, translator);

const preferences = createPreferences();
const states = createStates({ translator });
const dataUrl = new URL('../data/', import.meta.url);
const cache = createDataCache(dataUrl);
let mounted = false;

async function start() {
  states.loading();
  let loaded;
  try {
    loaded = await loadBest({ baseUrl: dataUrl, cache });
  } catch (error) {
    console.error(error);
    states.problem(problemKind(error, navigator.onLine), { onRetry: start });
    return;
  }
  try {
    showFreshness(loaded.data.status);
    if (loaded.data.matches.length === 0) {
      states.problem('empty', { onRetry: start });
      return;
    }
    if (!mounted) {
      mounted = true;
      mountHome({ data: loaded.data, translator, preferences });
    }
    states.ready({ fromSavedCopy: loaded.source === 'saved' });
  } catch (error) {
    console.error(error);
    states.problem('unexpected');
  }
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

// When the connection comes back, a screen that was waiting for it tries again by itself.
window.addEventListener('online', () => {
  if (states.canRetry()) start();
});

await start();

// Tests and styles can tell the page is ready, loaded or not.
document.documentElement.dataset.ready = 'true';
