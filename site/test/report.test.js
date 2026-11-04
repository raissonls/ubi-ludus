import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createTranslator } from '../js/i18n.js';
import { REPO_URL, generalReportUrl, matchReportUrl } from '../js/report.js';

const translator = createTranslator({
  matches: { tbd: 'A definir' },
  card: { versus: 'x', badge: { confirmed: 'confirmado', rule: 'pela tabela de direitos' } },
  report: { title: 'Transmissão errada', nothingShown: 'nenhuma emissora' },
});

const model = {
  id: 'fx-1',
  kickoff: '2026-11-03T22:00:00Z',
  home: { name: 'Palmeiras' },
  away: { name: 'Flamengo' },
  competition: 'Campeonato Brasileiro Série A',
  badges: [
    { name: 'TV Globo', confidence: 'confirmed' },
    { name: 'SporTV', confidence: 'rule' },
  ],
};

test('the general link opens the form for a wrong broadcast and fills nothing in', () => {
  const url = new URL(generalReportUrl());
  assert.equal(url.origin + url.pathname, `${REPO_URL}/issues/new`);
  assert.equal(url.searchParams.get('template'), 'wrong-broadcast.yml');
  assert.deepEqual([...url.searchParams.keys()], ['template']);
});

test('the link for a match fills in the match and what the site shows', () => {
  const url = new URL(matchReportUrl(model, translator));
  assert.equal(url.origin, 'https://github.com');
  assert.equal(url.searchParams.get('template'), 'wrong-broadcast.yml');
  assert.equal(url.searchParams.get('title'), 'Transmissão errada: Palmeiras x Flamengo');
  const match = url.searchParams.get('match');
  assert.match(match, /^Palmeiras x Flamengo · Campeonato Brasileiro Série A · .*19:00 · fx-1$/);
  assert.equal(url.searchParams.get('shown'), 'TV Globo (confirmado), SporTV (pela tabela de direitos)');
});

test('a match with no broadcaster says nothing was shown, and an undecided team says so', () => {
  const bare = { ...model, away: { name: null }, badges: [] };
  const url = new URL(matchReportUrl(bare, translator));
  assert.equal(url.searchParams.get('shown'), 'nenhuma emissora');
  assert.match(url.searchParams.get('title'), /Palmeiras x A definir$/);
});

test('names that look like markup or a URL stay inside their parameter', () => {
  const hostile = { ...model, home: { name: '"><script>x</script>&template=evil' } };
  const url = new URL(matchReportUrl(hostile, translator));
  assert.equal(url.searchParams.get('template'), 'wrong-broadcast.yml');
  assert.equal(url.searchParams.getAll('template').length, 1);
  assert.match(url.searchParams.get('match'), /^"><script>x<\/script>&template=evil x Flamengo/);
});

test('the link carries nothing about the visitor', () => {
  const url = matchReportUrl(model, translator);
  for (const word of ['teams', 'services', 'follow', 'onlyWatchable']) {
    assert.equal(url.includes(word), false, word);
  }
});
