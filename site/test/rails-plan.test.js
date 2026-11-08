import assert from 'node:assert/strict';
import { test } from 'node:test';

import { planRails } from '../js/rails-plan.js';

const match = (id, kickoff, competition = 'serie-a', status = 'scheduled') => ({
  id,
  kickoff_utc: kickoff,
  competition_id: competition,
  status,
});
const summary = (rows) => rows.map((row) => `${row.kind}:${row.id}=${row.matches.map((m) => m.id).join(',')}`);
const never = () => false;

test('the matches on now come first, in a row of their own, and are not repeated below', () => {
  const live = match('on-now', '2026-11-02T14:00:00Z', 'la-liga', 'live');
  const rows = planRails({
    view: 'today',
    followed: [match('mine', '2026-11-02T22:00:00Z')],
    others: [live, match('later', '2026-11-02T20:00:00Z', 'la-liga')],
    isLive: (m) => m.id === 'on-now',
  });
  assert.deepEqual(summary(rows), ['live:live=on-now', 'mine:mine=mine', 'competition:la-liga=later']);
});

test('the followed teams of the live row come before the others', () => {
  const a = match('other-live', '2026-11-02T14:00:00Z');
  const b = match('mine-live', '2026-11-02T15:00:00Z');
  const rows = planRails({ view: 'today', followed: [b], others: [a], isLive: () => true });
  assert.deepEqual(summary(rows), ['live:live=mine-live,other-live']);
});

test('today: my teams first, then one row for each competition in order of the first match', () => {
  const rows = planRails({
    view: 'today',
    followed: [match('f1', '2026-11-02T22:00:00Z', 'serie-a')],
    others: [
      match('l1', '2026-11-02T15:00:00Z', 'la-liga'),
      match('s1', '2026-11-02T16:00:00Z', 'serie-a'),
      match('l2', '2026-11-02T17:00:00Z', 'la-liga'),
    ],
    isLive: never,
  });
  assert.deepEqual(summary(rows), [
    'mine:mine=f1',
    'competition:la-liga=l1,l2',
    'competition:serie-a=s1',
  ]);
});

test('today with nobody followed: only the competitions', () => {
  const rows = planRails({ view: 'today', followed: [], others: [match('a', '2026-11-02T15:00:00Z')], isLive: never });
  assert.deepEqual(summary(rows), ['competition:serie-a=a']);
});

test('my teams: one row of their next matches', () => {
  const rows = planRails({
    view: 'mine',
    followed: [match('a', '2026-11-03T22:00:00Z'), match('b', '2026-11-05T22:00:00Z')],
    others: [],
    isLive: never,
  });
  assert.deepEqual(summary(rows), ['next:next=a,b']);
});

test('the week: one row for each day, soonest first, followed and others together', () => {
  const rows = planRails({
    view: 'week',
    followed: [match('f', '2026-11-04T22:00:00Z')],
    others: [
      match('o2', '2026-11-04T15:00:00Z'),
      match('o1', '2026-11-03T15:00:00Z'),
      match('o3', '2026-11-06T15:00:00Z'),
    ],
    isLive: never,
  });
  assert.deepEqual(summary(rows), [
    'day:2026-11-03=o1',
    'day:2026-11-04=o2,f',
    'day:2026-11-06=o3',
  ]);
});

test('a late match belongs to the day it is in Brazil, not in UTC', () => {
  const rows = planRails({
    view: 'week',
    followed: [],
    others: [match('late', '2026-11-03T01:30:00Z')], // 22:30 on the 2nd in Brazil
    isLive: never,
  });
  assert.deepEqual(summary(rows), ['day:2026-11-02=late']);
});

test('no matches, no rows', () => {
  assert.deepEqual(planRails({ view: 'today', followed: [], others: [], isLive: never }), []);
});
