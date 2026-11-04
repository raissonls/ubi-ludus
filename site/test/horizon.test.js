import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  describeHorizonNotice,
  hasShortCompetitions,
  isShortHorizon,
  joinNames,
  shortCompetitionsIn,
} from '../js/horizon.js';
import { createTranslator } from '../js/i18n.js';
import { describeMatch } from '../js/match-model.js';

const strings = JSON.parse(readFileSync(new URL('../i18n/pt-BR.json', import.meta.url), 'utf-8'));
const translator = createTranslator(strings);

const competition = (id, name, coverage) => [id, { id, name, coverage }];
const data = {
  competitionsById: new Map([
    competition('serie-a', 'Campeonato Brasileiro Série A', 'full'),
    competition('copa-do-brasil', 'Copa do Brasil', 'short'),
    competition('paulista', 'Campeonato Paulista', 'short'),
    competition('nowhere', 'Sem dados', 'none'),
  ]),
  teamsById: new Map(),
  broadcastersById: new Map(),
};
const match = (id, competition_id, status = 'scheduled') => ({
  id,
  competition_id,
  kickoff_utc: '2026-11-03T22:00:00Z',
  home_team_id: null,
  away_team_id: null,
  status,
  broadcasts: [],
});

test('only a competition published as short is short, whatever its name', () => {
  assert.equal(isShortHorizon({ coverage: 'short' }), true);
  assert.equal(isShortHorizon({ coverage: 'full' }), false);
  assert.equal(isShortHorizon({ coverage: 'none' }), false);
  assert.equal(isShortHorizon({}), false);
  assert.equal(isShortHorizon(undefined), false);
});

test('the short competitions of a list are named once each, in alphabetical order', () => {
  const shown = [match('1', 'paulista'), match('2', 'serie-a'), match('3', 'copa-do-brasil'), match('4', 'paulista')];
  assert.deepEqual(shortCompetitionsIn(shown, data), ['Campeonato Paulista', 'Copa do Brasil']);
  assert.deepEqual(shortCompetitionsIn([match('5', 'serie-a')], data), []);
  assert.deepEqual(shortCompetitionsIn([match('6', 'unknown-id')], data), []);
});

test('a competition being looked at counts although no match of it is in the list', () => {
  assert.deepEqual(shortCompetitionsIn([], data, ['copa-do-brasil']), ['Copa do Brasil']);
});

test('names are joined the Portuguese way', () => {
  assert.equal(joinNames(['A']), 'A');
  assert.equal(joinNames(['A', 'B']), 'A e B');
  assert.equal(joinNames(['A', 'B', 'C']), 'A, B e C');
});

test('the notice names the short competitions in the list', () => {
  const notice = describeHorizonNotice({ shown: [match('1', 'copa-do-brasil'), match('2', 'paulista')], data });
  assert.equal(notice.key, 'horizon.some');
  assert.equal(notice.count, 2);
  const text = translator.plural(notice.key, notice.count, notice.values);
  assert.match(text, /^Para Campeonato Paulista e Copa do Brasil, só temos dados até amanhã\./);
});

test('no notice when every competition in the list has its full window', () => {
  assert.equal(describeHorizonNotice({ shown: [match('1', 'serie-a')], data }), null);
});

test('an empty list says that some competitions are only known until tomorrow', () => {
  const notice = describeHorizonNotice({ shown: [], data });
  assert.equal(notice.key, 'horizon.empty');
  assert.match(translator.t(notice.key), /só temos dados até amanhã/);
});

test('an empty list says nothing when no competition is short', () => {
  const full = { ...data, competitionsById: new Map([competition('serie-a', 'Série A', 'full')]) };
  assert.equal(hasShortCompetitions(full), false);
  assert.equal(describeHorizonNotice({ shown: [], data: full }), null);
});

test('an empty list of a full competition says nothing about the short ones', () => {
  assert.equal(describeHorizonNotice({ shown: [], data, selectedId: 'serie-a' }), null);
});

test('an empty list of a short competition names it', () => {
  const notice = describeHorizonNotice({ shown: [], data, selectedId: 'copa-do-brasil' });
  assert.equal(notice.key, 'horizon.some');
  assert.equal(notice.values.competitions, 'Copa do Brasil');
});

test('a card for a match still to come carries the notice, one that is over does not', () => {
  assert.equal(describeMatch(match('1', 'copa-do-brasil'), data).shortHorizon, true);
  assert.equal(describeMatch(match('2', 'copa-do-brasil', 'live'), data).shortHorizon, true);
  assert.equal(describeMatch(match('3', 'copa-do-brasil', 'finished'), data).shortHorizon, false);
  assert.equal(describeMatch(match('4', 'copa-do-brasil', 'cancelled'), data).shortHorizon, false);
  assert.equal(describeMatch(match('5', 'serie-a'), data).shortHorizon, false);
});
