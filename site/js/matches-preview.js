// The next matches of the teams the visitor follows. This is the plain list of M3-03; the match
// card (M3-05) and the day views (M3-06) replace how it looks, not what it picks.

/** A match that has started is still worth showing for this long (a long one, with extra time). */
export const STILL_RELEVANT_MS = 3 * 60 * 60 * 1000;

const OPEN = new Set(['scheduled', 'rescheduled', 'live']);

/** A match still marked as to come whose kickoff was long ago: old data, not a match to show. */
export function isStale(match, now) {
  return (
    (match.status === 'scheduled' || match.status === 'rescheduled') &&
    Date.parse(match.kickoff_utc) < now.getTime() - STILL_RELEVANT_MS
  );
}

/**
 * The matches of `teamIds` that are live or still to come, soonest first, at most `limit`.
 * A match that is "scheduled" but started long ago is stale data, not an upcoming match.
 */
export function upcomingMatches(matches, teamIds, now, limit = 10) {
  const followed = new Set(teamIds);
  const since = now.getTime() - STILL_RELEVANT_MS;
  return matches
    .filter((match) => followed.has(match.home_team_id) || followed.has(match.away_team_id))
    .filter((match) => OPEN.has(match.status))
    .filter((match) => match.status === 'live' || Date.parse(match.kickoff_utc) >= since)
    .sort((a, b) => Date.parse(a.kickoff_utc) - Date.parse(b.kickoff_utc) || a.id.localeCompare(b.id))
    .slice(0, limit);
}
