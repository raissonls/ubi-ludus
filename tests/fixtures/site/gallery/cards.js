// A page for the tests: it draws one match card for each case in cases.json, with the site's own
// modules and the site's own data fixtures, so every state can be looked at and checked at once.
// It is never part of the site.

import { loadData } from '/js/data.js';
import { createTranslator, loadStrings } from '/js/i18n.js';
import { renderMatchCard } from '/js/match-card.js';
import { describeMatch } from '/js/match-model.js';

const translator = createTranslator(await loadStrings('/i18n/pt-BR.json'));
const data = await loadData(new URL('/data/', location.href));
const gallery = await (await fetch('/gallery/cases.json')).json();
for (const team of gallery.extra_teams) {
  data.teamsById.set(team.id, team);
}

const list = document.getElementById('cards');
for (const { case: name, match } of gallery.cases) {
  const followed = data.teamsById.get(match.home_team_id) ?? null;
  const card = renderMatchCard(describeMatch(match, data), { translator, accentTeam: followed });
  card.dataset.case = name;
  list.append(card);
}
document.documentElement.dataset.ready = 'true';
