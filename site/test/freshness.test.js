import assert from 'node:assert/strict';
import { test } from 'node:test';

import { STALE_AFTER_MS, describeFreshness } from '../js/freshness.js';

// Tuesday 3 November 2026, 09:00 in Brazil.
const NOW = new Date('2026-11-03T12:00:00Z');
const status = (lastSuccess) => ({ last_success_at: lastSuccess });

test('an update from earlier today says "today" and the time in Brazil', () => {
  const found = describeFreshness(status('2026-11-03T09:12:00Z'), NOW);
  assert.equal(found.state, 'fresh');
  assert.equal(found.key, 'freshness.today');
  assert.equal(found.values.time, '06:12'); // 09:12 UTC
  assert.equal(found.at, '2026-11-03T09:12:00.000Z');
});

test('the day is the day in Brazil, not in UTC', () => {
  // 01:00 UTC on the 3rd is 22:00 on the 2nd in Brazil: yesterday.
  assert.equal(describeFreshness(status('2026-11-03T01:00:00Z'), NOW).key, 'freshness.yesterday');
  // 23:00 UTC on the 2nd is 20:00 on the 2nd in Brazil: yesterday as well.
  assert.equal(describeFreshness(status('2026-11-02T23:00:00Z'), NOW).key, 'freshness.yesterday');
});

test('yesterday works across a month end', () => {
  const now = new Date('2026-12-01T12:00:00Z');
  assert.equal(describeFreshness(status('2026-11-30T20:00:00Z'), now).key, 'freshness.yesterday');
});

test('36 hours is still fresh, one minute more is stale', () => {
  const edge = new Date(NOW.getTime() - STALE_AFTER_MS);
  assert.equal(describeFreshness(status(edge.toISOString()), NOW).state, 'fresh');
  const past = new Date(NOW.getTime() - STALE_AFTER_MS - 60_000);
  const found = describeFreshness(status(past.toISOString()), NOW);
  assert.equal(found.state, 'stale');
  assert.equal(found.key, 'freshness.stale');
});

test('a fresh update from two days ago cannot happen, an old one gives the date', () => {
  const found = describeFreshness(status('2026-10-30T09:00:00Z'), NOW);
  assert.equal(found.state, 'stale');
  assert.match(found.values.date, /30/);
  assert.equal(found.values.time, '06:00');
});

test('no record of a success, or an unreadable status, is "unknown"', () => {
  for (const broken of [status(null), status('not a date'), {}, null, undefined]) {
    const found = describeFreshness(broken, NOW);
    assert.equal(found.state, 'unknown');
    assert.equal(found.key, 'freshness.unknown');
    assert.equal(found.at, null);
  }
});

test('a time slightly in the future (a clock a bit off) still counts as today', () => {
  const found = describeFreshness(status('2026-11-03T12:05:00Z'), NOW);
  assert.equal(found.state, 'fresh');
  assert.equal(found.key, 'freshness.today');
});
