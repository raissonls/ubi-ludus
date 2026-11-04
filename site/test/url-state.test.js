import assert from 'node:assert/strict';
import { test } from 'node:test';

import { MAX_LIST, MAX_QUERY, buildSearch, parseUrlState } from '../js/url-state.js';

const allow = {
  views: new Set(['mine', 'today', 'week']),
  competitions: new Set(['serie-a', 'champions']),
  broadcasters: new Set(['globo', 'sportv']),
  teams: new Set(['palmeiras', 'brasil', 'real-madrid']),
  services: new Set(['globoplay', 'premiere']),
};
const filters = (changes = {}) => ({ competition: '', broadcaster: '', q: '', ...changes });

test('a plain address asks for nothing', () => {
  assert.deepEqual(parseUrlState('', allow), {
    view: null,
    filters: filters(),
    teams: null,
    services: null,
    onlyWatchable: null,
  });
});

test('a valid address is read in full', () => {
  const search =
    '?view=week&competition=serie-a&broadcaster=globo&q=palmeiras' +
    '&teams=palmeiras,brasil&services=globoplay&watchable=1';
  assert.deepEqual(parseUrlState(search, allow), {
    view: 'week',
    filters: filters({ competition: 'serie-a', broadcaster: 'globo', q: 'palmeiras' }),
    teams: ['palmeiras', 'brasil'],
    services: ['globoplay'],
    onlyWatchable: true,
  });
});

test('anything not on the allow-list is ignored, never used', () => {
  const search =
    '?view=evil&competition=nope&broadcaster=<script>' +
    '&teams=palmeiras,gone-fc,../x,PALMEIRAS,real-madrid&services=hbo';
  const found = parseUrlState(search, allow);
  assert.equal(found.view, null);
  assert.deepEqual(found.filters, filters());
  assert.deepEqual(found.teams, ['palmeiras', 'real-madrid']);
  assert.deepEqual(found.services, []); // mentioned, but nothing valid
});

test('a list that is mentioned but empty is empty, not missing', () => {
  const found = parseUrlState('?teams=&services=', allow);
  assert.deepEqual([found.teams, found.services], [[], []]);
});

test('"watchable" is only on for exactly 1', () => {
  assert.equal(parseUrlState('?watchable=1', allow).onlyWatchable, true);
  assert.equal(parseUrlState('?watchable=0', allow).onlyWatchable, false);
  assert.equal(parseUrlState('?watchable=yes', allow).onlyWatchable, false);
});

test('the search text loses control characters, extra spaces and anything past the limit', () => {
  assert.equal(parseUrlState('?q=%20%20sao%00%0A%20%20paulo%20', allow).filters.q, 'sao paulo');
  assert.equal(parseUrlState(`?q=${'a'.repeat(500)}`, allow).filters.q.length, MAX_QUERY);
});

test('markup in the search text stays text', () => {
  const found = parseUrlState('?q=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E', allow);
  assert.equal(found.filters.q, '<img src=x onerror=alert(1)>');
});

test('only the first value of a repeated parameter counts, and lists are capped', () => {
  assert.equal(parseUrlState('?view=today&view=week', allow).view, 'today');
  const many = Array.from({ length: 80 }, (_, i) => `t${i}`);
  const wide = { ...allow, teams: new Set(many) };
  assert.equal(parseUrlState(`?teams=${many.join(',')}`, wide).teams.length, MAX_LIST);
});

test('the address bar gets only what is set, and no choices', () => {
  assert.equal(buildSearch({ filters: filters() }), '');
  assert.equal(
    buildSearch({ view: 'today', filters: filters({ competition: 'serie-a', q: 'sao paulo' }) }),
    '?view=today&competition=serie-a&q=sao+paulo',
  );
});

test('a link to share adds the teams, the services and the filter of the visitor', () => {
  const choices = { teams: ['palmeiras', 'brasil'], services: ['globoplay'], onlyWatchable: true };
  assert.equal(
    buildSearch({ view: 'week', filters: filters({ broadcaster: 'globo' }), choices }),
    '?view=week&broadcaster=globo&teams=palmeiras%2Cbrasil&services=globoplay&watchable=1',
  );
  const none = { teams: [], services: [], onlyWatchable: false };
  assert.equal(buildSearch({ filters: filters(), choices: none }), '');
});

test('what is built is read back as the same view', () => {
  const choices = { teams: ['palmeiras', 'real-madrid'], services: ['premiere'], onlyWatchable: true };
  const view = {
    view: 'mine',
    filters: filters({ competition: 'champions', broadcaster: 'sportv', q: 'real' }),
    choices,
  };
  assert.deepEqual(parseUrlState(buildSearch(view), allow), {
    view: 'mine',
    filters: view.filters,
    teams: choices.teams,
    services: choices.services,
    onlyWatchable: true,
  });
});
