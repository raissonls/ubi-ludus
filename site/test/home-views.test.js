import assert from 'node:assert/strict';
import { test } from 'node:test';

import { daysFrom, defaultView, selectMatches, VIEWS } from '../js/home-views.js';

// Monday 2 November 2026, 09:00 in Brazil.
const NOW = new Date('2026-11-02T12:00:00Z');

function match(id, kickoff, home, away, status = 'scheduled') {
  return { id, kickoff_utc: kickoff, home_team_id: home, away_team_id: away, status };
}

const MATCHES = [
  match('late-today', '2026-11-03T01:30:00Z', 'a', 'b'), // 22:30 on 2 Nov in Brazil
  match('early-today', '2026-11-02T15:00:00Z', 'c', 'd'),
  match('followed-today', '2026-11-02T23:00:00Z', 'palmeiras', 'e'),
  match('tomorrow', '2026-11-03T20:00:00Z', 'f', 'palmeiras'),
  match('day-seven', '2026-11-08T22:00:00Z', 'g', 'h'),
  match('day-eight', '2026-11-09T22:00:00Z', 'i', 'j'),
  match('yesterday', '2026-11-01T22:00:00Z', 'k', 'l', 'finished'),
  match('stale', '2026-11-02T03:00:00Z', 'm', 'n'),
  match('done-today', '2026-11-02T10:00:00Z', 'o', 'p', 'finished'),
];
const ids = (list) => list.map((m) => m.id);

test('there are three views and the default follows the teams', () => {
  assert.deepEqual(VIEWS, ['mine', 'today', 'week']);
  assert.equal(defaultView(['palmeiras']), 'mine');
  assert.equal(defaultView([]), 'today');
});

test('the days are calendar days in Brazil, across month and year ends', () => {
  assert.deepEqual(daysFrom(NOW, 3), ['2026-11-02', '2026-11-03', '2026-11-04']);
  assert.deepEqual(daysFrom(new Date('2026-12-30T12:00:00Z'), 4), [
    '2026-12-30', '2026-12-31', '2027-01-01', '2027-01-02',
  ]);
  // 01:00 UTC on the 3rd is still the evening of the 2nd in Brazil.
  assert.equal(daysFrom(new Date('2026-11-03T01:00:00Z'), 1)[0], '2026-11-02');
});

test('today is the Brazilian day of now, finished matches included, stale ones left out', () => {
  const { followed, others } = selectMatches('today', MATCHES, [], NOW);
  assert.deepEqual(followed, []);
  assert.deepEqual(ids(others), ['done-today', 'early-today', 'followed-today', 'late-today']);
});

test('the week is today and six more days', () => {
  const { others } = selectMatches('week', MATCHES, [], NOW);
  assert.equal(ids(others).includes('day-seven'), true);
  assert.equal(ids(others).includes('day-eight'), false);
  assert.equal(ids(others).includes('yesterday'), false);
});

test('followed teams come before the rest, each group by kickoff', () => {
  const { followed, others } = selectMatches('week', MATCHES, ['palmeiras'], NOW);
  assert.deepEqual(ids(followed), ['followed-today', 'tomorrow']);
  assert.equal(ids(others)[0], 'done-today');
  assert.equal(ids(others).includes('followed-today'), false);
});

test('"mine" lists only the followed teams, still to come', () => {
  const found = selectMatches('mine', MATCHES, ['palmeiras'], NOW);
  assert.deepEqual(ids(found.followed), ['followed-today', 'tomorrow']);
  assert.deepEqual(found.others, []);
  assert.deepEqual(selectMatches('mine', MATCHES, [], NOW), { followed: [], others: [] });
});

test('the same instant keeps its order by id', () => {
  const twin = [match('b', '2026-11-03T20:00:00Z', 'x', 'y'), match('a', '2026-11-03T20:00:00Z', 'z', 'w')];
  assert.deepEqual(ids(selectMatches('week', twin, [], NOW).others), ['a', 'b']);
});
