// What a match card says, as plain data. No DOM here, so every rule about states and about how
// sure we are of a broadcaster (FR-12, FR-13) can be tested without a browser.

import { isShortHorizon } from './horizon.js';

/** The states of a match, as the pipeline publishes them. */
export const STATES = ['scheduled', 'live', 'finished', 'postponed', 'cancelled', 'rescheduled'];

// There is something to watch only for a match that is on, or still to come. A finished, postponed
// or cancelled match shows no broadcasters: they would be a promise nobody can keep.
const WATCHABLE = new Set(['scheduled', 'rescheduled', 'live']);

const CONFIDENCE_ORDER = { confirmed: 0, rule: 1 };

// Free TV and YouTube need no subscription: everybody can watch them (FR-21).
const FREE_KINDS = new Set(['free_tv', 'youtube']);

/**
 * The ids of the broadcasters this visitor can watch (FR-25): the free ones, those of a service
 * they ticked, and any broadcaster a ticked service includes (Disney+ includes ESPN, for one).
 */
export function accessibleBroadcasters(serviceIds, data) {
  const ticked = new Set(serviceIds);
  const found = new Set();
  for (const broadcaster of data.broadcastersById.values()) {
    if (FREE_KINDS.has(broadcaster.kind) || ticked.has(broadcaster.service_id)) {
      found.add(broadcaster.id);
    }
  }
  for (const id of ticked) {
    for (const broadcasterId of data.servicesById.get(id)?.includes_broadcasters ?? []) {
      found.add(broadcasterId);
    }
  }
  return found;
}

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
export function describeBadges(broadcasts, broadcastersById, accessible = null) {
  return broadcasts
    .filter((b) => b.confidence !== 'unknown' && b.broadcaster_id)
    .map((b) => {
      const broadcaster = broadcastersById.get(b.broadcaster_id);
      return {
        id: b.broadcaster_id,
        name: broadcaster ? broadcaster.name : b.broadcaster_id,
        kind: broadcaster ? broadcaster.kind : null,
        confidence: b.confidence,
        ...(accessible ? { accessible: accessible.has(b.broadcaster_id) } : {}),
      };
    })
    .sort(
      (a, b) =>
        (CONFIDENCE_ORDER[a.confidence] ?? 2) - (CONFIDENCE_ORDER[b.confidence] ?? 2) ||
        a.name.localeCompare(b.name, 'pt-BR'),
    );
}

/**
 * Can the visitor watch this match? Only said when we know their services (`accessible` given)
 * and the match is one to watch:
 *   yes      a listed broadcaster is one they have
 *   no       broadcasters are listed and none is theirs
 *   unknown  no broadcaster is known, so nothing can be said (FR-13)
 *   null     nothing to say (a finished match, or the services are not known)
 */
export function summariseAccess(badges, { showBroadcasts, confidence, known }) {
  if (!known || !showBroadcasts) return null;
  if (confidence === 'unknown') return 'unknown';
  return badges.some((badge) => badge.accessible) ? 'yes' : 'no';
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

/**
 * Everything the card shows for one match. `accessible` is the set from accessibleBroadcasters();
 * leave it out and the card says nothing about the visitor's services.
 */
export function describeMatch(match, data, { accessible = null } = {}) {
  const state = STATES.includes(match.status) ? match.status : 'scheduled';
  const competition = data.competitionsById.get(match.competition_id);
  const broadcasts = match.broadcasts ?? [];
  const confidence = summariseConfidence(broadcasts);
  const showBroadcasts = WATCHABLE.has(state);
  const badges = describeBadges(broadcasts, data.broadcastersById, accessible);
  return {
    id: match.id,
    state,
    kickoff: match.kickoff_utc,
    rescheduledAt: match.rescheduled_at ?? null,
    home: side(match.home_team_id, data),
    away: side(match.away_team_id, data),
    competition: competition ? competition.name : match.competition_id,
    // The card of a match still to come in a competition we only know until tomorrow says so (FR-34).
    shortHorizon: showBroadcasts && isShortHorizon(competition),
    round: describeRound(match.round),
    confidence,
    showBroadcasts,
    badges,
    access: summariseAccess(badges, { showBroadcasts, confidence, known: accessible !== null }),
  };
}
