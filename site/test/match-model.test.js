// Run with: node --test site/test/   (no dependencies)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  STATES,
  describeBadges,
  describeMatch,
  describeRound,
  summariseConfidence,
} from '../js/match-model.js';

const broadcastersById = new Map([
  ['globo', { id: 'globo', name: 'TV Globo', kind: 'free_tv' }],
  ['sportv', { id: 'sportv', name: 'SporTV', kind: 'pay_tv' }],
  ['premiere', { id: 'premiere', name: 'Premiere', kind: 'ppv' }],
]);
const data = {
  teamsById: new Map([
    ['palmeiras', { id: 'palmeiras', name: 'Palmeiras', short_name: 'Palmeiras' }],
    ['barcelona', { id: 'barcelona', name: 'Barcelona', short_name: 'Barça' }],
  ]),
  competitionsById: new Map([['serie-a', { id: 'serie-a', name: 'Campeonato Brasileiro Série A' }]]),
  broadcastersById,
};
const rule = (id) => ({ broadcaster_id: id, confidence: 'rule', source: 'rights_rule' });
const confirmed = (id) => ({ broadcaster_id: id, confidence: 'confirmed', source: 'override' });
const unknown = { broadcaster_id: null, confidence: 'unknown', source: 'none' };

const match = (changes = {}) => ({
  id: 'm-1',
  competition_id: 'serie-a',
  round: '34',
  kickoff_utc: '2026-11-03T22:00:00Z',
  home_team_id: 'palmeiras',
  away_team_id: 'barcelona',
  status: 'scheduled',
  broadcasts: [rule('globo')],
  ...changes,
});

// --- how sure we are -----------------------------------------------------------------------

test('nothing known is "unknown", and so is no broadcast at all', () => {
  assert.equal(summariseConfidence([unknown]), 'unknown');
  assert.equal(summariseConfidence([]), 'unknown');
});

test('only broadcasters a person checked make the card "confirmed"', () => {
  assert.equal(summariseConfidence([confirmed('globo')]), 'confirmed');
  assert.equal(summariseConfidence([confirmed('globo'), confirmed('sportv')]), 'confirmed');
});

test('one broadcaster that comes only from the rights table makes the card "rule"', () => {
  assert.equal(summariseConfidence([rule('globo')]), 'rule');
  assert.equal(summariseConfidence([confirmed('globo'), rule('sportv')]), 'rule');
});

test('an "unknown" broadcast that wrongly carries a broadcaster is still unknown', () => {
  assert.equal(summariseConfidence([{ broadcaster_id: 'globo', confidence: 'unknown', source: 'none' }]), 'unknown');
  assert.deepEqual(describeBadges([{ broadcaster_id: 'globo', confidence: 'unknown', source: 'none' }], broadcastersById), []);
});

// --- badges --------------------------------------------------------------------------------

test('badges name the broadcasters, confirmed ones first, then by name', () => {
  const badges = describeBadges([rule('sportv'), rule('premiere'), confirmed('globo')], broadcastersById);
  assert.deepEqual(
    badges.map((b) => [b.name, b.confidence]),
    [['TV Globo', 'confirmed'], ['Premiere', 'rule'], ['SporTV', 'rule']],
  );
  assert.deepEqual(badges.map((b) => b.kind), ['free_tv', 'ppv', 'pay_tv']);
});

test('a broadcaster the data does not describe still shows by its id', () => {
  assert.deepEqual(describeBadges([rule('ghost')], broadcastersById), [
    { id: 'ghost', name: 'ghost', kind: null, confidence: 'rule' },
  ]);
});

test('no unknown broadcast ever makes a badge', () => {
  assert.deepEqual(describeBadges([unknown], broadcastersById), []);
});

// --- rounds --------------------------------------------------------------------------------

test('a round is a matchday or a stage, or nothing', () => {
  assert.deepEqual(describeRound('34'), { kind: 'matchday', number: 34 });
  assert.deepEqual(describeRound('final'), { kind: 'stage', slug: 'final' });
  assert.deepEqual(describeRound('last-16'), { kind: 'stage', slug: 'last-16' });
  assert.equal(describeRound(null), null);
  assert.equal(describeRound(undefined), null);
  assert.equal(describeRound(''), null);
});

// --- the card ------------------------------------------------------------------------------

test('a match is described with its teams, competition, round and kickoff', () => {
  const card = describeMatch(match(), data);
  assert.equal(card.home.name, 'Palmeiras');
  assert.equal(card.away.name, 'Barça');
  assert.equal(card.competition, 'Campeonato Brasileiro Série A');
  assert.deepEqual(card.round, { kind: 'matchday', number: 34 });
  assert.equal(card.kickoff, '2026-11-03T22:00:00Z');
  assert.equal(card.state, 'scheduled');
  assert.equal(card.confidence, 'rule');
  assert.equal(card.showBroadcasts, true);
  assert.deepEqual(card.badges.map((b) => b.name), ['TV Globo']);
});

test('an undecided team has no name, and an unknown one is not invented', () => {
  const card = describeMatch(match({ home_team_id: null, away_team_id: 'gone-fc' }), data);
  assert.deepEqual([card.home.name, card.away.name], [null, null]);
  assert.equal(card.home.team, null);
});

test('a competition the data lacks shows its id rather than nothing', () => {
  assert.equal(describeMatch(match({ competition_id: 'mystery-cup' }), data).competition, 'mystery-cup');
});

test('every state is known, and a state we do not know falls back to scheduled', () => {
  for (const state of STATES) {
    assert.equal(describeMatch(match({ status: state }), data).state, state);
  }
  assert.equal(describeMatch(match({ status: 'delayed' }), data).state, 'scheduled');
});

test('only a match on, or still to come, shows broadcasters', () => {
  const shows = Object.fromEntries(STATES.map((s) => [s, describeMatch(match({ status: s }), data).showBroadcasts]));
  assert.deepEqual(shows, {
    scheduled: true,
    live: true,
    rescheduled: true,
    finished: false,
    postponed: false,
    cancelled: false,
  });
});

test('an unknown match has no badge and says it is unknown', () => {
  const card = describeMatch(match({ broadcasts: [unknown] }), data);
  assert.equal(card.confidence, 'unknown');
  assert.deepEqual(card.badges, []);
});

test('a rescheduled match carries the time it was noticed', () => {
  const card = describeMatch(match({ status: 'rescheduled', rescheduled_at: '2026-11-02T09:00:00Z' }), data);
  assert.equal(card.rescheduledAt, '2026-11-02T09:00:00Z');
  assert.equal(describeMatch(match(), data).rescheduledAt, null);
});

test('a match with no broadcasts list at all is unknown, not an error', () => {
  const { broadcasts: _gone, ...bare } = match();
  assert.equal(describeMatch(bare, data).confidence, 'unknown');
});
