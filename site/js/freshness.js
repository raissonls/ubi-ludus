// How old the data is (FR-30), from status.json. Pure: it takes the status and "now" and says
// what to tell the visitor, so the rules (today, yesterday, older than 36 hours, no record at all)
// can be tested without a browser.

import { dayKey, formatDate, formatTime } from './format.js';

/** Data older than this is called out as possibly out of date. */
export const STALE_AFTER_MS = 36 * 60 * 60 * 1000;

/** The calendar day before "2026-11-03", as "2026-11-02". */
function dayBefore(key) {
  const [year, month, day] = key.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day - 1)).toISOString().slice(0, 10);
}

/**
 * What to say about the data's age.
 *
 *   state  "fresh" (36 hours or less), "stale" (older) or "unknown" (the pipeline has never
 *          succeeded, or the file cannot be read)
 *   key    which string to use, with `values` filled in
 *   at     the UTC instant it is about, for a <time> element (null for "unknown")
 */
export function describeFreshness(status, now) {
  const at = Date.parse(status?.last_success_at ?? '');
  if (Number.isNaN(at)) {
    return { state: 'unknown', key: 'freshness.unknown', values: {}, at: null };
  }
  const when = new Date(at);
  const values = { time: formatTime(when), date: formatDate(when) };
  if (now.getTime() - at > STALE_AFTER_MS) {
    return { state: 'stale', key: 'freshness.stale', values, at: when.toISOString() };
  }
  const today = dayKey(now);
  const day = dayKey(when);
  let key = 'freshness.date';
  if (day === today) key = 'freshness.today';
  else if (day === dayBefore(today)) key = 'freshness.yesterday';
  return { state: 'fresh', key, values, at: when.toISOString() };
}
