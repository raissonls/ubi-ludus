// The strip at the top of the lists: the shirts of the teams the visitor follows, their names and the
// services they have, and "Editar". It is one button, so what they chose is always in sight and
// one press from changing. With no team chosen it asks them to choose.

import { shirtOf } from './onboarding-model.js';
import { createShirt } from './shirt.js';

const MAX_SHIRTS = 3;
const MAX_NAMES = 2;
const listFormat = new Intl.ListFormat('pt-BR', { style: 'long', type: 'conjunction' });

/** "Palmeiras e Flamengo", or "Palmeiras, Flamengo e mais 1": the first names, then how many more. */
export function summarise(names, translator, maxNames = MAX_NAMES) {
  if (names.length <= maxNames) return listFormat.format(names);
  const more = translator.plural('strip.andMore', names.length - maxNames);
  return `${names.slice(0, maxNames).join(', ')} ${more}`;
}

/**
 * @param data        the published data (teams, services)
 * @param onOpen      called with the choices when the strip is pressed
 */
export function createTeamStrip({ data, translator, onOpen }) {
  const button = document.getElementById('team-strip');
  const shirts = document.getElementById('team-strip-shirts');
  const teams = document.getElementById('team-strip-teams');
  const services = document.getElementById('team-strip-services');
  let current = { teams: [], services: [] };

  button.addEventListener('click', () => onOpen(current));

  return {
    /** Show these choices (ids), as the preferences hold them. */
    update(choices) {
      current = choices;
      const chosen = choices.teams.map((id) => data.teamsById.get(id)).filter(Boolean);
      shirts.replaceChildren(
        ...chosen.slice(0, MAX_SHIRTS).map((team) => {
          const shirt = createShirt(shirtOf(team), 38);
          shirt.classList.add('strip__shirt');
          return shirt;
        }),
      );
      if (chosen.length === 0) {
        teams.textContent = translator.t('strip.none');
        services.textContent = translator.t('strip.noneHint');
        button.removeAttribute('data-has-teams');
        return;
      }
      button.dataset.hasTeams = 'true';
      teams.textContent = summarise(
        chosen.map((team) => team.short_name),
        translator,
      );
      const names = choices.services.map((id) => data.servicesById.get(id)?.name).filter(Boolean);
      services.textContent =
        names.length === 0 ? translator.t('strip.freeOnly') : summarise(names, translator);
    },
  };
}
