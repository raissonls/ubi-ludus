// "Which teams do you follow?" (FR-20): a search box that suggests teams as you type, and the
// teams chosen so far as buttons you can press to take one out.
//
// It follows the ARIA "editable combobox with list autocomplete" pattern, so it works with the
// keyboard and with a screen reader:
//   * the input is the combobox; the options are in a listbox it controls
//   * Down and Up move through the options (aria-activedescendant), Enter chooses, Escape closes
//   * what happened is said in a polite live region ("Palmeiras adicionado. 2 times escolhidos.")
//
// The markup is in index.html; this module adds the behaviour and draws the options and the chips.

import { el, setAccent } from './dom.js';
import { LOCALE } from './i18n.js';
import { buildIndex, searchTeams, suggestTeams } from './search.js';

const ANNOUNCE_AFTER_TYPING_MS = 350;
const regionNames = new Intl.DisplayNames([LOCALE], { type: 'region' });

function countryName(code, translator) {
  if (code.includes('-')) {
    // A part of a country (England): the strings file names it. The group is read by key.
    return translator.t(['countries', code].join('.'));
  }
  try {
    return regionNames.of(code) ?? code;
  } catch {
    return code;
  }
}

/**
 * @param teams    the published teams
 * @param translator  from i18n.js
 * @param onChange called with the ids chosen, in the order chosen, after the visitor adds or
 *   removes a team. The caller saves them and calls update() with what it saved.
 */
export function createTeamPicker({ teams, translator, onChange }) {
  const input = document.getElementById('team-search');
  const listbox = document.getElementById('team-options');
  const noResults = document.getElementById('team-no-results');
  const chosenList = document.getElementById('chosen-teams');
  const chosenEmpty = document.getElementById('chosen-empty');
  const announcer = document.getElementById('picker-announcer');

  const index = buildIndex(teams);
  const byId = new Map(teams.map((team) => [team.id, team]));
  let selected = [];
  let results = [];
  let active = -1;
  let typingTimer = null;
  let announcedOnce = false;
  let focusedByCode = false;

  function say(text) {
    // The same sentence twice in a row is not read again, so the second one differs invisibly.
    announcedOnce = !announcedOnce;
    announcer.textContent = announcedOnce ? text : `${text} `;
  }

  function optionId(team) {
    return `team-option-${team.id}`;
  }

  function swatch(team) {
    const element = el('span', { class: 'swatch', 'aria-hidden': 'true' });
    setAccent(element, team);
    return element;
  }

  function drawOptions() {
    listbox.replaceChildren(
      ...results.map((team, position) => {
        const option = el(
          'li',
          { role: 'option', id: optionId(team), 'aria-selected': String(position === active) },
          [
            swatch(team),
            el('span', { class: 'option__name', text: team.name }),
            el('span', { class: 'option__country', text: countryName(team.country, translator) }),
          ],
        );
        if (position === active) option.classList.add('is-active');
        option.addEventListener('pointerdown', (event) => event.preventDefault()); // keep the focus
        option.addEventListener('click', () => choose(team));
        return option;
      }),
    );
    const open = results.length > 0;
    listbox.hidden = !open;
    input.setAttribute('aria-expanded', String(open));
    if (active >= 0 && results[active]) {
      input.setAttribute('aria-activedescendant', optionId(results[active]));
    } else {
      input.removeAttribute('aria-activedescendant');
    }
    const query = input.value.trim();
    noResults.hidden = open || query === '';
    noResults.textContent = noResults.hidden ? '' : translator.t('picker.noResults', { query });
  }

  function compute() {
    const exclude = new Set(selected);
    const query = input.value.trim();
    results = query ? searchTeams(index, query, { exclude }) : suggestTeams(index, { exclude });
    active = -1;
    drawOptions();
  }

  function close() {
    results = [];
    active = -1;
    drawOptions();
  }

  function drawChosen() {
    chosenList.replaceChildren(
      ...selected.map((id) => {
        const team = byId.get(id);
        const chip = el(
          'button',
          { type: 'button', class: 'chip', 'aria-label': translator.t('picker.remove', { team: team.name }) },
          [swatch(team), el('span', { text: team.short_name || team.name }), el('span', { 'aria-hidden': 'true', text: '×' })],
        );
        chip.addEventListener('click', () => remove(team));
        return el('li', {}, [chip]);
      }),
    );
    chosenEmpty.hidden = selected.length > 0;
  }

  // Put the focus back in the box after choosing or removing, without opening the suggestions:
  // they would cover the chosen teams the visitor may want to reach next.
  function returnFocusToBox() {
    focusedByCode = true;
    input.focus();
    focusedByCode = false;
  }

  function choose(team) {
    if (selected.includes(team.id)) return;
    selected = [...selected, team.id];
    onChange(selected);
    drawChosen();
    say(translator.plural('picker.added', selected.length, { team: team.name }));
    input.value = '';
    returnFocusToBox();
    close(); // typing or Down opens the suggestions again
  }

  function remove(team) {
    selected = selected.filter((id) => id !== team.id);
    onChange(selected);
    drawChosen();
    // Portuguese counts 0 as singular, so nothing left needs its own sentence.
    say(
      selected.length === 0
        ? translator.t('picker.removedAll', { team: team.name })
        : translator.plural('picker.removed', selected.length, { team: team.name }),
    );
    returnFocusToBox();
    close();
  }

  function move(step) {
    if (results.length === 0) {
      compute();
      return;
    }
    active = (active + step + results.length) % results.length;
    drawOptions();
  }

  function announceResults() {
    const query = input.value.trim();
    if (!query) return;
    say(
      results.length > 0
        ? translator.plural('picker.found', results.length)
        : translator.t('picker.noResults', { query }),
    );
  }

  input.addEventListener('input', () => {
    compute();
    clearTimeout(typingTimer);
    typingTimer = setTimeout(announceResults, ANNOUNCE_AFTER_TYPING_MS);
  });
  input.addEventListener('focus', () => {
    if (!focusedByCode) compute();
  });
  input.addEventListener('click', () => {
    if (results.length === 0) compute();
  });
  input.addEventListener('blur', close);
  input.addEventListener('keydown', (event) => {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        move(1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        move(-1);
        break;
      case 'Enter':
        if (results.length > 0) {
          event.preventDefault();
          choose(results[active >= 0 ? active : 0]);
        }
        break;
      case 'Escape':
        if (results.length > 0) {
          event.preventDefault();
          close();
        } else if (input.value !== '') {
          event.preventDefault();
          input.value = '';
        }
        break;
      default:
    }
  });

  drawChosen();

  return {
    /** Show these ids as the chosen teams (what was saved, or nothing after a reset). */
    update(ids) {
      selected = ids.filter((id) => byId.has(id));
      drawChosen();
      if (results.length > 0) compute(); // an open list stops offering what is now chosen
    },
  };
}
