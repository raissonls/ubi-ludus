// The three lists of the home page (FR-23): the next matches of the teams the visitor follows,
// today, and the week. Pure: it takes the matches, the followed teams and "now", and returns
// which matches to show, followed teams first.

import { dayKey } from './format.js';
import { isStale, upcomingMatches } from './matches-preview.js';

export const VIEWS = ['mine', 'today', 'week'];
/** "This week" is today and the six days after it. */
export const WEEK_DAYS = 7;
/** The next matches of the followed teams: enough for a glance, not a calendar. */
export const MINE_LIMIT = 10;

/** The list a visitor sees before choosing one: their teams if they follow any, else today. */
export function defaultView(teamIds) {
  return teamIds.length > 0 ? 'mine' : 'today';
}

/** The calendar days (as "2026-11-14") from the day of `now`, `count` of them, in Brazil. */
export function daysFrom(now, count) {
  const [year, month, day] = dayKey(now).split('-').map(Number);
  return Array.from({ length: count }, (_, offset) =>
    new Date(Date.UTC(year, month - 1, day + offset)).toISOString().slice(0, 10),
  );
}

function byKickoff(a, b) {
  return Date.parse(a.kickoff_utc) - Date.parse(b.kickoff_utc) || a.id.localeCompare(b.id);
}

// A match worth putting first: one that is on now, or still to come.
const OPEN = new Set(['scheduled', 'rescheduled', 'live']);

/**
 * The match to show big at the top for a view: among the matches of the followed teams in that
 * view's days, the one on now, else the soonest still to come. Null when their teams have none
 * in the view (the big card is then left out, rather than showing a match from another day).
 * Filters do not apply: it is the visitor's own next match.
 */
export function nextMatch(view, allMatches, teamIds, now) {
  const { followed } = selectMatches(view, allMatches, teamIds, now);
  const open = followed.filter((match) => OPEN.has(match.status));
  return open.find((match) => match.status === 'live') ?? open[0] ?? null;
}

/**
 * The matches of one view: `followed` are the ones with a team the visitor follows, `others` the
 * rest (empty for "mine"); each group soonest first, so followed teams always come before the rest.
 * `keep` says which matches may be listed at all (the "only what I can watch" filter).
 */
export function selectMatches(view, allMatches, teamIds, now, keep = () => true) {
  // The filter comes first, so "my teams" still gives ten matches when some were filtered out.
  const matches = allMatches.filter(keep);
  if (view === 'mine') {
    return { followed: upcomingMatches(matches, teamIds, now, MINE_LIMIT), others: [] };
  }
  const days = new Set(daysFrom(now, view === 'today' ? 1 : WEEK_DAYS));
  const followedTeams = new Set(teamIds);
  const inRange = matches
    .filter((match) => days.has(dayKey(match.kickoff_utc)) && !isStale(match, now))
    .sort(byKickoff);
  const isFollowed = (match) =>
    followedTeams.has(match.home_team_id) || followedTeams.has(match.away_team_id);
  return { followed: inRange.filter(isFollowed), others: inRange.filter((m) => !isFollowed(m)) };
}
