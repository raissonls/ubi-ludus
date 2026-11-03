// A plain list of the next matches of the followed teams. The proper match card (M3-05) and the
// day views (M3-06) replace this; it exists so a new visitor sees their matches right after
// choosing a team.

import { el, setAccent } from './dom.js';
import { formatDateTime } from './format.js';
import { upcomingMatches } from './matches-preview.js';

export function createMatchesView({ data, translator }) {
  const list = document.getElementById('matches-list');
  const empty = document.getElementById('matches-empty');

  function teamName(id) {
    const team = data.teamsById.get(id);
    return team ? team.short_name || team.name : translator.t('matches.tbd');
  }

  function row(match, followed) {
    const competition = data.competitionsById.get(match.competition_id);
    const accentTeam = data.teamsById.get(followed.find((id) => id === match.home_team_id || id === match.away_team_id));
    const item = el('li', { class: 'match' }, [
      el('time', { datetime: match.kickoff_utc, text: formatDateTime(match.kickoff_utc) }),
      el('span', {
        class: 'match__teams',
        text: translator.t('matches.versus', { home: teamName(match.home_team_id), away: teamName(match.away_team_id) }),
      }),
      el('span', { class: 'match__competition', text: competition ? competition.name : match.competition_id }),
    ]);
    if (accentTeam) setAccent(item, accentTeam);
    return item;
  }

  return {
    /** Draw the matches of these teams as of `now`. */
    render(teamIds, now = new Date()) {
      const matches = upcomingMatches(data.matches, teamIds, now);
      list.replaceChildren(...matches.map((match) => row(match, teamIds)));
      list.hidden = matches.length === 0;
      empty.hidden = matches.length > 0;
      empty.textContent = translator.t(teamIds.length === 0 ? 'matches.pickPrompt' : 'matches.empty');
    },
  };
}
