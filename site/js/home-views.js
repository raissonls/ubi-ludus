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

/**
 * The matches of one view: `followed` are the ones with a team the visitor follows, `others` the
 * rest (empty for "mine"); each group soonest first, so followed teams always come before the rest.
 */
export function selectMatches(view, matches, teamIds, now) {
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
