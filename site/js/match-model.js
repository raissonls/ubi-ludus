// What a match card says, as plain data. No DOM here, so every rule about states and about how
// sure we are of a broadcaster (FR-12, FR-13) can be tested without a browser.

/** The states of a match, as the pipeline publishes them. */
export const STATES = ['scheduled', 'live', 'finished', 'postponed', 'cancelled', 'rescheduled'];

// There is something to watch only for a match that is on, or still to come. A finished, postponed
// or cancelled match shows no broadcasters: they would be a promise nobody can keep.
const WATCHABLE = new Set(['scheduled', 'rescheduled', 'live']);

const CONFIDENCE_ORDER = { confirmed: 0, rule: 1 };

/**
 * How sure we are, for the card as a whole:
 *   unknown    nothing is known (no broadcast, or only "unknown" ones): no broadcaster is named
 *   confirmed  every broadcaster listed was checked by a person
 *   rule       at least one comes only from the rights table
 */
export function summariseConfidence(broadcasts) {
  const named = broadcasts.filter((b) => b.confidence !== 'unknown' && b.broadcaster_id);
  if (named.length === 0) return 'unknown';
  return named.every((b) => b.confidence === 'confirmed') ? 'confirmed' : 'rule';
}

/**
 * The broadcaster badges of a match: confirmed ones first, then by name. A broadcast with no
 * broadcaster, or that says "unknown", gives no badge, whatever else it carries (FR-13).
 */
export function describeBadges(broadcasts, broadcastersById) {
  return broadcasts
    .filter((b) => b.confidence !== 'unknown' && b.broadcaster_id)
    .map((b) => {
      const broadcaster = broadcastersById.get(b.broadcaster_id);
      return {
        id: b.broadcaster_id,
        name: broadcaster ? broadcaster.name : b.broadcaster_id,
        kind: broadcaster ? broadcaster.kind : null,
        confidence: b.confidence,
      };
    })
    .sort(
      (a, b) =>
        (CONFIDENCE_ORDER[a.confidence] ?? 2) - (CONFIDENCE_ORDER[b.confidence] ?? 2) ||
        a.name.localeCompare(b.name, 'pt-BR'),
    );
}

/** A round as the pipeline publishes it: a matchday ("34"), or a knockout stage ("final"). */
export function describeRound(round) {
  if (round === null || round === undefined || round === '') return null;
  return /^\d+$/.test(round) ? { kind: 'matchday', number: Number(round) } : { kind: 'stage', slug: round };
}

function side(id, data) {
  const team = id ? data.teamsById.get(id) : undefined;
  return { id: id ?? null, name: team ? team.short_name || team.name : null, team: team ?? null };
}

/** Everything the card shows for one match. */
export function describeMatch(match, data) {
  const state = STATES.includes(match.status) ? match.status : 'scheduled';
  const competition = data.competitionsById.get(match.competition_id);
  const broadcasts = match.broadcasts ?? [];
  return {
    id: match.id,
    state,
    kickoff: match.kickoff_utc,
    rescheduledAt: match.rescheduled_at ?? null,
    home: side(match.home_team_id, data),
    away: side(match.away_team_id, data),
    competition: competition ? competition.name : match.competition_id,
    round: describeRound(match.round),
    confidence: summariseConfidence(broadcasts),
    showBroadcasts: WATCHABLE.has(state),
    badges: describeBadges(broadcasts, data.broadcastersById),
  };
}
