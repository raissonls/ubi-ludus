// The view in the address bar (FR-27, FR-29). The filters are always reflected there, so a view
// can be copied, bookmarked or reloaded; the visitor's own teams and services only when they
// choose to share the view. Reading it is the careful part: an address is text anyone can write,
// so every value is checked against what the site actually has (an allow-list of ids) and what
// does not fit is ignored, never used.

import { cleanIds } from './preferences.js';

/** The longest search text kept from an address. */
export const MAX_QUERY = 60;
/** The most teams or services read from an address (far more than anyone follows). */
export const MAX_LIST = 50;

const CONTROL = /[\u0000-\u001f\u007f]/g;

function cleanText(value) {
  return (value ?? '').replace(CONTROL, ' ').replace(/\s+/g, ' ').trim().slice(0, MAX_QUERY);
}

function list(value, allowed) {
  if (value === null) return null;
  return cleanIds(value.split(',')).filter((id) => allowed.has(id)).slice(0, MAX_LIST);
}

/**
 * What an address asks for. `allow` has a Set for each of views, competitions, broadcasters,
 * teams and services. A value that is not on its list comes back empty, and `teams`, `services`
 * and `onlyWatchable` are null when the address does not mention them (a plain link).
 */
export function parseUrlState(search, allow) {
  const params = new URLSearchParams(search);
  const one = (name) => params.get(name);
  const pick = (name, allowed) => (allowed.has(one(name) ?? '') ? one(name) : '');
  const watchable = one('watchable');
  return {
    view: pick('view', allow.views) || null,
    filters: {
      competition: pick('competition', allow.competitions),
      broadcaster: pick('broadcaster', allow.broadcasters),
      q: cleanText(one('q')),
    },
    teams: list(one('teams'), allow.teams),
    services: list(one('services'), allow.services),
    onlyWatchable: watchable === null ? null : watchable === '1',
  };
}

/**
 * The query string for a view: only what is set. `choices` ({teams, services, onlyWatchable}) is
 * added for a link to share and left out of the address bar the rest of the time.
 */
export function buildSearch({ view = null, filters, choices = null }) {
  const params = new URLSearchParams();
  if (view) params.set('view', view);
  if (filters.competition) params.set('competition', filters.competition);
  if (filters.broadcaster) params.set('broadcaster', filters.broadcaster);
  if (cleanText(filters.q)) params.set('q', cleanText(filters.q));
  if (choices) {
    if (choices.teams.length > 0) params.set('teams', choices.teams.join(','));
    if (choices.services.length > 0) params.set('services', choices.services.join(','));
    if (choices.onlyWatchable) params.set('watchable', '1');
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}
