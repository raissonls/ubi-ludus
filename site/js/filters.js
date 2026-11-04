// The filters on the list of matches (FR-27): by competition, by broadcaster and by a few letters
// of a team's name. They combine (AND): a match must pass every one that is set. Pure: no DOM.

import { normalise } from './search.js';

export const EMPTY_FILTERS = { competition: '', broadcaster: '', q: '' };

/** How many filters are set. */
export function activeCount(filters) {
  return [filters.competition, filters.broadcaster, normalise(filters.q)].filter(Boolean).length;
}

function names(team) {
  return [team?.name, team?.short_name, ...(team?.aliases ?? [])].filter(Boolean).map(normalise);
}

/**
 * The competitions and the broadcasters that some match has, by name: the choices the filters
 * offer. A broadcaster is only offered if a match names it (an "unknown" broadcast names nobody).
 */
export function filterOptions(data) {
  const competitions = new Set();
  const broadcasters = new Set();
  for (const match of data.matches) {
    competitions.add(match.competition_id);
    for (const broadcast of match.broadcasts ?? []) {
      if (broadcast.confidence !== 'unknown' && broadcast.broadcaster_id) {
        broadcasters.add(broadcast.broadcaster_id);
      }
    }
  }
  const byName = (a, b) => a.name.localeCompare(b.name, 'pt-BR');
  return {
    competitions: [...competitions]
      .map((id) => ({ id, name: data.competitionsById.get(id)?.name ?? id }))
      .sort(byName),
    broadcasters: [...broadcasters]
      .map((id) => ({ id, name: data.broadcastersById.get(id)?.name ?? id }))
      .sort(byName),
  };
}

/** A function telling whether a match passes the filters; the team names are prepared once. */
export function createMatchFilter(data, filters) {
  const words = normalise(filters.q).split(' ').filter(Boolean);
  const keysOf = new Map();
  function keys(teamId) {
    if (!keysOf.has(teamId)) keysOf.set(teamId, names(data.teamsById.get(teamId)));
    return keysOf.get(teamId);
  }
  return (match) => {
    if (filters.competition && match.competition_id !== filters.competition) return false;
    if (
      filters.broadcaster &&
      !(match.broadcasts ?? []).some(
        (b) => b.confidence !== 'unknown' && b.broadcaster_id === filters.broadcaster,
      )
    ) {
      return false;
    }
    if (words.length > 0) {
      const teams = [...keys(match.home_team_id), ...keys(match.away_team_id)];
      return words.every((word) => teams.some((key) => key.includes(word)));
    }
    return true;
  };
}
