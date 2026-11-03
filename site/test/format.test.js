// Run with: node --test site/test/   (no dependencies)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { dayKey, formatDate, formatDateTime, formatTime } from '../js/format.js';

test('a UTC instant is shown in Brazil\'s time', () => {
  // 02:30 UTC is 23:30 the evening before in Sao Paulo (UTC-3 in 2026).
  assert.equal(formatTime('2026-11-03T02:30:00Z'), '23:30');
  assert.equal(dayKey('2026-11-03T02:30:00Z'), '2026-11-02');
});

test('midnight in Brazil belongs to the new day', () => {
  assert.equal(formatTime('2026-11-03T03:00:00Z'), '00:00');
  assert.equal(dayKey('2026-11-03T03:00:00Z'), '2026-11-03');
});

test('the last minute of a day in Brazil still belongs to it', () => {
  assert.equal(dayKey('2026-11-04T02:59:00Z'), '2026-11-03');
});

test('the IANA zone is used, so past daylight saving time is right', () => {
  // Brazil used UTC-2 in December 2018. A fixed -03:00 would say 23:30 on 30 November.
  assert.equal(formatTime('2018-12-01T02:30:00Z'), '00:30');
  assert.equal(dayKey('2018-12-01T02:30:00Z'), '2018-12-01');
});

test('dates read in Portuguese', () => {
  const text = formatDate('2026-11-14T19:00:00Z');
  assert.match(text, /sáb/i);
  assert.match(text, /14/);
  assert.match(text, /nov/i);
});

test('date and time together', () => {
  const text = formatDateTime('2026-11-14T19:00:00Z');
  assert.match(text, /14/);
  assert.match(text, /16:00/);
});

test('a Date works as well as a string', () => {
  assert.equal(formatTime(new Date('2026-11-03T02:30:00Z')), '23:30');
});

test('something that is not a date is an error, not "Invalid Date"', () => {
  assert.throws(() => formatTime('soon'), RangeError);
  assert.throws(() => dayKey(undefined), RangeError);
});
