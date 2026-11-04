// The screens the visitor can end up on besides the lists themselves (FR-32): loading, a problem
// (offline, the server failing, a site older than its data, something unexpected), no data yet, and
// a notice that what is shown is a saved copy. Each is words first and shows a way forward: a
// button to try again or to reload.

import { el } from './dom.js';
import { REPO_URL } from './report.js';

// For each kind of problem: where its words are in the strings file, and what it offers (try the
// load again, or reload the page).
const PROBLEMS = {
  offline: { words: 'states.offline', action: 'retry' },
  error: { words: 'states.error', action: 'retry' },
  empty: { words: 'states.empty', action: 'retry' },
  outdated: { words: 'states.outdated', action: 'reload' },
  unexpected: { words: 'states.unexpected', action: 'reload' },
};
const BUTTON = { retry: 'states.retry', reload: 'states.reload' };
const URGENT = new Set(['offline', 'error', 'outdated', 'unexpected']);

/** Which problem a failed load is. `online` is navigator.onLine. */
export function problemKind(error, online = true) {
  if (error?.kind === 'version') return 'outdated';
  if (error?.kind === 'network' || !online) return 'offline';
  return 'error';
}

export function createStates({ translator }) {
  const section = document.getElementById('matches-section');
  const heading = document.getElementById('matches-title');
  const loading = document.getElementById('matches-loading');
  const panel = document.getElementById('state-panel');
  const saved = document.getElementById('saved-notice');
  const content = document.getElementById('matches-content');
  const needsData = [...document.querySelectorAll('[data-needs-data]')];
  let current = null;

  function show({ busy, wait, problem, list }) {
    section.setAttribute('aria-busy', String(busy));
    loading.hidden = !wait;
    panel.hidden = !problem;
    content.hidden = !list;
    for (const part of needsData) part.hidden = !list;
  }

  return {
    /** The lists are on their way. */
    loading() {
      current = null;
      saved.hidden = true;
      show({ busy: true, wait: true, problem: false, list: false });
    },

    /** The data is here. `fromSavedCopy` says it is the copy kept from an earlier load. */
    ready({ fromSavedCopy = false } = {}) {
      current = null;
      saved.hidden = !fromSavedCopy;
      show({ busy: false, wait: false, problem: false, list: true });
    },

    /** A screen for a problem; `onRetry` is called by the button when the kind asks to try again. */
    problem(kind, { onRetry = () => {} } = {}) {
      current = kind;
      saved.hidden = true;
      const { words, action } = PROBLEMS[kind];
      const children = [
        el('h3', { text: translator.t(`${words}.title`) }),
        el('p', { text: translator.t(`${words}.body`) }),
      ];
      const button = el('button', { type: 'button', text: translator.t(BUTTON[action]) });
      button.addEventListener('click', () => {
        if (action === 'reload') {
          location.reload();
          return;
        }
        heading.focus(); // the button is about to go away; keep the visitor's place
        onRetry();
      });
      children.push(el('p', {}, [button]));
      if (URGENT.has(kind)) {
        children.push(
          el('p', {}, [
            el('a', {
              href: `${REPO_URL}/issues/new`,
              rel: 'noopener noreferrer',
              text: translator.t('states.report'),
            }),
          ]),
        );
      }
      panel.dataset.kind = kind;
      panel.setAttribute('role', URGENT.has(kind) ? 'alert' : 'status');
      panel.replaceChildren(...children);
      show({ busy: false, wait: false, problem: true, list: false });
    },

    /** True while a problem that trying again may fix is on screen. */
    canRetry() {
      return current !== null && PROBLEMS[current].action === 'retry';
    },
  };
}
