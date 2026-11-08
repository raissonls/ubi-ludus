// How the matches of a list are split into rows ("rails"), like the rows of a streaming app. Pure:
// it takes the matches already chosen and ordered (soonest first) and says which row each goes in.
//
//   live     the matches on now, first of all
//   mine     the followed teams' matches ("today" list), or "next" for the "my teams" list
//   day      one row for each day, for the week
//   competition  one row for each competition, for the rest of today's matches
//
// A match is in one row only: the one on now is in "live", not again in its competition's.

import { dayKey } from './format.js';

/**
 * @param view      "mine", "today" or "week"
 * @param followed  the matches with a team the visitor follows
 * @param others    the rest
 * @param isLive    (match) => whether it is on now
 * @returns rows: { kind, id, matches[] }, none of them empty
 */
export function planRails({ view, followed, others, isLive }) {
  const rows = [];
  const live = [...followed, ...others].filter(isLive);
  if (live.length > 0) rows.push({ kind: 'live', id: 'live', matches: live });
  const restFollowed = followed.filter((match) => !isLive(match));
  const restOthers = others.filter((match) => !isLive(match));

  if (view === 'mine') {
    if (restFollowed.length > 0) rows.push({ kind: 'next', id: 'next', matches: restFollowed });
    return rows;
  }
  if (view === 'week') {
    const days = new Map();
    for (const match of [...restFollowed, ...restOthers].sort(byKickoff)) {
      const key = dayKey(match.kickoff_utc);
      if (!days.has(key)) days.set(key, []);
      days.get(key).push(match);
    }
    for (const [key, matches] of days) rows.push({ kind: 'day', id: key, matches });
    return rows;
  }
  // today: the followed teams first, then one row for each competition, the earliest first
  if (restFollowed.length > 0) rows.push({ kind: 'mine', id: 'mine', matches: restFollowed });
  const competitions = new Map();
  for (const match of restOthers) {
    if (!competitions.has(match.competition_id)) competitions.set(match.competition_id, []);
    competitions.get(match.competition_id).push(match);
  }
  for (const [id, matches] of competitions) rows.push({ kind: 'competition', id, matches });
  return rows;
}

function byKickoff(a, b) {
  return Date.parse(a.kickoff_utc) - Date.parse(b.kickoff_utc) || a.id.localeCompare(b.id);
}
