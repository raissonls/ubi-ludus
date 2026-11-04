import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  COUNTDOWN_FROM_MS,
  LIVE_WINDOW_MS,
  SOON_MS,
  clockPhase,
  describePhase,
} from '../js/live-clock.js';

const KICKOFF = '2026-11-03T22:00:00Z';
const AT = Date.parse(KICKOFF);
const at = (offsetMs) => new Date(AT + offsetMs);
const MIN = 60 * 1000;
const phaseAt = (offsetMs, status = 'scheduled') => clockPhase({ status, kickoff: KICKOFF }, at(offsetMs));
const words = (offsetMs, status) => describePhase(phaseAt(offsetMs, status));

test('far from kickoff there is nothing to add', () => {
  assert.equal(phaseAt(-COUNTDOWN_FROM_MS - 1), null);
  assert.equal(phaseAt(-3 * 24 * 60 * MIN), null);
});

test('a day before kickoff the countdown begins', () => {
  assert.deepEqual(phaseAt(-COUNTDOWN_FROM_MS), { phase: 'countdown', msLeft: COUNTDOWN_FROM_MS });
  assert.deepEqual(phaseAt(-1), { phase: 'countdown', msLeft: 1 });
});

test('at kickoff it is on, and stays on through the live window', () => {
  assert.deepEqual(phaseAt(0), { phase: 'live' });
  assert.deepEqual(phaseAt(LIVE_WINDOW_MS - 1), { phase: 'live' });
});

test('past the window the match is probably over, whatever the data still says', () => {
  assert.deepEqual(phaseAt(LIVE_WINDOW_MS), { phase: 'over' });
  assert.deepEqual(phaseAt(LIVE_WINDOW_MS, 'live'), { phase: 'over' });
  assert.deepEqual(phaseAt(48 * 60 * MIN), { phase: 'over' });
});

test('a match the data calls live is live from the clock too, inside the window', () => {
  assert.deepEqual(phaseAt(30 * MIN, 'live'), { phase: 'live' });
});

test('matches that are over or off get nothing, at any time', () => {
  for (const status of ['finished', 'postponed', 'cancelled', 'surprise']) {
    for (const offset of [-60 * MIN, 0, 60 * MIN, 5 * 60 * MIN]) {
      assert.equal(phaseAt(offset, status), null, `${status} ${offset}`);
    }
  }
  assert.equal(phaseAt(0, 'rescheduled').phase, 'live');
});

test('a kickoff that is not a date gets nothing', () => {
  assert.equal(clockPhase({ status: 'scheduled', kickoff: 'later' }, at(0)), null);
  assert.equal(clockPhase({ status: 'scheduled', kickoff: undefined }, at(0)), null);
});

test('the countdown reads in hours and minutes, then minutes, then "in a moment"', () => {
  assert.deepEqual(words(-(2 * 60 + 15) * MIN), { key: 'clock.hoursMinutes', values: { hours: 2, minutes: 15 } });
  assert.deepEqual(words(-2 * 60 * MIN), { key: 'clock.hours', values: { hours: 2 } });
  assert.deepEqual(words(-42 * MIN), { key: 'clock.minutes', values: { minutes: 42 } });
  assert.deepEqual(words(-1 * MIN), { key: 'clock.minutes', values: { minutes: 1 } });
  assert.deepEqual(words(-SOON_MS), { key: 'clock.minutes', values: { minutes: 1 } });
  assert.deepEqual(words(-SOON_MS + 1), { key: 'clock.soon', values: {} });
  assert.deepEqual(words(-1), { key: 'clock.soon', values: {} });
});

test('minutes round up, so the countdown never says 0 and never skips to the hour early', () => {
  assert.deepEqual(words(-(59 * MIN + 30_000)), { key: 'clock.hours', values: { hours: 1 } }); // 59.5 min
  assert.deepEqual(words(-(60 * MIN + 1)), { key: 'clock.hoursMinutes', values: { hours: 1, minutes: 1 } });
  assert.deepEqual(words(-(23 * 60 + 59) * MIN - 1), { key: 'clock.hours', values: { hours: 24 } });
});

test('live and over have their own words, and nothing has none', () => {
  assert.deepEqual(words(10 * MIN), { key: 'clock.live', values: {} });
  assert.deepEqual(words(4 * 60 * MIN), { key: 'clock.over', values: {} });
  assert.equal(describePhase(null), null);
});
