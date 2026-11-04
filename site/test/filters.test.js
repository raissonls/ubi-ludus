import assert from 'node:assert/strict';
import { test } from 'node:test';

import { EMPTY_FILTERS, activeCount, createMatchFilter, filterOptions } from '../js/filters.js';

const team = (id, name, short, aliases = []) => [id, { id, name, short_name: short, aliases }];
const broadcast = (id, confidence = 'rule') => ({ broadcaster_id: id, confidence });
const data = {
  teamsById: new Map([
    team('palmeiras', 'Palmeiras', 'Palmeiras', ['Verdão']),
    team('sao-paulo', 'São Paulo', 'São Paulo'),
    team('barcelona', 'Barcelona', 'Barça', ['FC Barcelona']),
    team('real-madrid', 'Real Madrid', 'Real Madrid'),
  ]),
  competitionsById: new Map([
    ['serie-a', { id: 'serie-a', name: 'Campeonato Brasileiro Série A' }],
    ['champions', { id: 'champions', name: 'UEFA Champions League' }],
  ]),
  broadcastersById: new Map([
    ['globo', { id: 'globo', name: 'TV Globo' }],
    ['sportv', { id: 'sportv', name: 'SporTV' }],
    ['max', { id: 'max', name: 'HBO Max' }],
  ]),
  matches: [
    {
      id: 'a',
      competition_id: 'serie-a',
      home_team_id: 'palmeiras',
      away_team_id: 'sao-paulo',
      broadcasts: [broadcast('globo'), broadcast('sportv')],
    },
    {
      id: 'b',
      competition_id: 'champions',
      home_team_id: 'real-madrid',
      away_team_id: 'barcelona',
      broadcasts: [broadcast('max', 'confirmed')],
    },
    {
      id: 'c',
      competition_id: 'champions',
      home_team_id: 'barcelona',
      away_team_id: null,
      broadcasts: [broadcast(null, 'unknown')],
    },
  ],
};
const passing = (filters) =>
  data.matches.filter(createMatchFilter(data, { ...EMPTY_FILTERS, ...filters })).map((m) => m.id);

test('no filter lets everything through', () => {
  assert.deepEqual(passing({}), ['a', 'b', 'c']);
  assert.equal(activeCount(EMPTY_FILTERS), 0);
});

test('competition and broadcaster each narrow the list', () => {
  assert.deepEqual(passing({ competition: 'champions' }), ['b', 'c']);
  assert.deepEqual(passing({ broadcaster: 'sportv' }), ['a']);
  assert.deepEqual(passing({ broadcaster: 'max' }), ['b']);
});

test('an "unknown" broadcast names nobody, so no broadcaster filter finds it', () => {
  assert.deepEqual(passing({ broadcaster: 'globo' }), ['a']);
  assert.equal(passing({ broadcaster: 'unknown' }).length, 0);
});

test('the team search ignores case and accents and finds names, short names and aliases', () => {
  assert.deepEqual(passing({ q: 'SAO paulo' }), ['a']);
  assert.deepEqual(passing({ q: 'barca' }), ['b', 'c']);
  assert.deepEqual(passing({ q: 'verdao' }), ['a']);
  assert.deepEqual(passing({ q: 'fc barcelona' }), ['b', 'c']);
});

test('every word of the search must match a team of the match', () => {
  assert.deepEqual(passing({ q: 'real barca' }), ['b']);
  assert.deepEqual(passing({ q: 'real palmeiras' }), []);
  assert.deepEqual(passing({ q: '   ' }), ['a', 'b', 'c']);
});

test('filters combine: a match must pass all of them', () => {
  assert.deepEqual(passing({ competition: 'champions', q: 'barca' }), ['b', 'c']);
  assert.deepEqual(passing({ competition: 'champions', broadcaster: 'max', q: 'barca' }), ['b']);
  assert.deepEqual(passing({ competition: 'serie-a', broadcaster: 'max' }), []);
  assert.deepEqual(passing({ competition: 'serie-a', q: 'barca' }), []);
});

test('a match with a team still to be decided is searched by the other team', () => {
  assert.deepEqual(passing({ q: 'barcelona' }), ['b', 'c']);
});

test('the options are the competitions and named broadcasters that matches have, by name', () => {
  const { competitions, broadcasters } = filterOptions(data);
  assert.deepEqual(
    competitions.map((c) => c.id),
    ['serie-a', 'champions'],
  );
  assert.deepEqual(
    broadcasters.map((b) => b.name),
    ['HBO Max', 'SporTV', 'TV Globo'],
  );
});

test('how many filters are set counts words, not blanks', () => {
  assert.equal(activeCount({ competition: 'x', broadcaster: '', q: ' ' }), 1);
  assert.equal(activeCount({ competition: 'x', broadcaster: 'y', q: 'barca' }), 3);
});
