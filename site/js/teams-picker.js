// "Which teams do you follow?" (FR-20), in the settings panel: the teams chosen so far, one row each
// with its shirt, its name and a button to take it out. Adding teams is not done here: "Adicionar
// times" opens the same choice as at the start (continent, country, team), which works better on
// a phone than typing into a search box. (home.js wires that button.)
//
// What happened is said in a polite live region ("Palmeiras removido. 1 time escolhido.").

import { countryName } from './countries.js';
import { el } from './dom.js';
import { shirtOf } from './onboarding-model.js';
import { createShirt } from './shirt.js';

/**
 * @param teams    the published teams
 * @param translator  from i18n.js
 * @param onChange called with the ids left, in the order chosen, after the visitor removes a team.
 *   The caller saves them and calls update() with what it saved.
 */
export function createTeamPicker({ teams, translator, onChange }) {
  const chosenList = document.getElementById('chosen-teams');
  const chosenEmpty = document.getElementById('chosen-empty');
  const announcer = document.getElementById('picker-announcer');

  const byId = new Map(teams.map((team) => [team.id, team]));
  let selected = [];
  let announcedOnce = false;

  function say(text) {
    // The same sentence twice in a row is not read again, so the second one differs invisibly.
    announcedOnce = !announcedOnce;
    announcer.textContent = announcedOnce ? text : `${text} `;
  }

  function draw() {
    chosenList.replaceChildren(
      ...selected.map((id) => {
        const team = byId.get(id);
        const shirt = createShirt(shirtOf(team), 32);
        shirt.classList.add('team-row__shirt');
        const remove = el(
          'button',
          {
            type: 'button',
            class: 'team-row__remove',
            'aria-label': translator.t('picker.remove', { team: team.name }),
          },
          [el('span', { 'aria-hidden': 'true', text: '×' })],
        );
        remove.addEventListener('click', () => take(team));
        return el('li', { class: 'team-row' }, [
          shirt,
          el('span', { class: 'team-row__text' }, [
            el('span', { class: 'team-row__name', text: team.name }),
            el('span', { class: 'team-row__country', text: countryName(team.country, translator) }),
          ]),
          remove,
        ]);
      }),
    );
    chosenEmpty.hidden = selected.length > 0;
  }

  function take(team) {
    const position = selected.indexOf(team.id);
    selected = selected.filter((id) => id !== team.id);
    onChange(selected);
    draw();
    // Portuguese counts 0 as singular, so nothing left needs its own sentence.
    say(
      selected.length === 0
        ? translator.t('picker.removedAll', { team: team.name })
        : translator.plural('picker.removed', selected.length, { team: team.name }),
    );
    // The row is gone, so the focus goes to the one that took its place, or to "Adicionar times".
    const next = chosenList.querySelectorAll('.team-row__remove')[Math.min(position, selected.length - 1)];
    (next ?? document.getElementById('reopen-onboarding')).focus();
  }

  draw();

  return {
    /** Show these ids as the chosen teams (what was saved, or nothing after a reset). */
    update(ids) {
      selected = ids.filter((id) => byId.has(id));
      draw();
    },
  };
}
