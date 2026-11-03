// The next matches of the followed teams, as match cards. The day views (M3-06) will group and
// filter cards like these; this is the first place they appear, right after a visitor chooses a
// team.

import { renderMatchCard } from './match-card.js';
import { describeMatch } from './match-model.js';
import { upcomingMatches } from './matches-preview.js';

export function createMatchesView({ data, translator }) {
  const list = document.getElementById('matches-list');
  const empty = document.getElementById('matches-empty');

  function card(match, followed) {
    const id = followed.find((teamId) => teamId === match.home_team_id || teamId === match.away_team_id);
    return renderMatchCard(describeMatch(match, data), { translator, accentTeam: data.teamsById.get(id) ?? null });
  }

  return {
    /** Draw the matches of these teams as of `now`. */
    render(teamIds, now = new Date()) {
      const matches = upcomingMatches(data.matches, teamIds, now);
      list.replaceChildren(...matches.map((match) => card(match, teamIds)));
      list.hidden = matches.length === 0;
      empty.hidden = matches.length > 0;
      empty.textContent = translator.t(teamIds.length === 0 ? 'matches.pickPrompt' : 'matches.empty');
    },
  };
}
