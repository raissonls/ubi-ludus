// Run with: node --test site/test/   (no dependencies)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { upcomingMatches } from '../js/matches-preview.js';
import { buildIndex, normalise, searchTeams, suggestTeams } from '../js/search.js';

const team = (id, name, short, country, aliases = []) => ({ id, name, short_name: short, country, aliases });
const TEAMS = [
  team('palmeiras', 'Palmeiras', 'Palmeiras', 'BR'),
  team('sao-paulo', 'São Paulo', 'São Paulo', 'BR', ['Sao Paulo', 'São Paulo FC']),
  team('santos', 'Santos', 'Santos', 'BR'),
  team('atletico-mineiro', 'Atlético Mineiro', 'Atlético-MG', 'BR', ['CA Mineiro', 'Atletico-MG']),
  team('atletico-madrid', 'Atlético de Madrid', 'Atleti', 'ES', ['Club Atlético de Madrid']),
  team('real-madrid', 'Real Madrid', 'Real Madrid', 'ES', ['Real Madrid CF']),
  team('real-betis', 'Real Betis', 'Real Betis', 'ES'),
  team('barcelona', 'Barcelona', 'Barça', 'ES', ['FC Barcelona']),
  team('bodo-glimt', 'Bodø/Glimt', 'Bodø/Glimt', 'NO'),
  team('brasil', 'Brasil', 'Brasil', 'BR', ['Brazil', 'Seleção Brasileira']),
];
const index = buildIndex(TEAMS);
const ids = (teams) => teams.map((t) => t.id);

test('case, accents and punctuation do not matter', () => {
  assert.equal(normalise('  São Paulo F.C.  '), 'sao paulo f c');
  assert.equal(normalise('Atlético-MG'), 'atletico mg');
  assert.equal(normalise('Bodø/Glimt'), 'bodo glimt');
  assert.equal(normalise(''), '');
});

test('typing without accents finds the accented name', () => {
  assert.deepEqual(ids(searchTeams(index, 'sao pa')), ['sao-paulo']);
  assert.deepEqual(ids(searchTeams(index, 'SÃO')), ['sao-paulo']);
});

test('an alias finds its team, as does the short name', () => {
  assert.deepEqual(ids(searchTeams(index, 'barca')), ['barcelona']);
  assert.deepEqual(ids(searchTeams(index, 'brazil')), ['brasil']);
  // Madrid's short name is exactly "atleti", so it comes first; Mineiro merely starts with it.
  assert.deepEqual(ids(searchTeams(index, 'atleti')), ['atletico-madrid', 'atletico-mineiro']);
  assert.deepEqual(ids(searchTeams(index, 'ca mineiro')), ['atletico-mineiro']);
});

test('a team that starts with what was typed comes before one that only contains it', () => {
  const found = searchTeams(index, 'real');
  assert.deepEqual(ids(found), ['real-betis', 'real-madrid']); // both start with it: by name
  assert.deepEqual(ids(searchTeams(index, 'madrid')), ['atletico-madrid', 'real-madrid']); // word start
});

test('the start of the name beats a later word of another', () => {
  // "santos" starts with "san"; "São Paulo" does not contain it.
  assert.deepEqual(ids(searchTeams(index, 'san')), ['santos']);
  // "mad": the word "madrid" in two names, by name order.
  assert.deepEqual(ids(searchTeams(index, 'mad')), ['atletico-madrid', 'real-madrid']);
});

test('several words match across a name in any order of words', () => {
  assert.deepEqual(ids(searchTeams(index, 'madrid atl')), ['atletico-madrid']);
});

test('the middle of a word counts, but last', () => {
  assert.deepEqual(ids(searchTeams(index, 'tico')), ['atletico-madrid', 'atletico-mineiro']);
});

test('teams already chosen are left out', () => {
  assert.deepEqual(ids(searchTeams(index, 'real', { exclude: new Set(['real-madrid']) })), ['real-betis']);
});

test('the number of results is capped', () => {
  assert.equal(searchTeams(index, 'a', { limit: 3 }).length, 3);
  assert.equal(searchTeams(index, 'a').length <= 8, true);
});

test('nothing typed finds nothing, and nonsense finds nothing', () => {
  assert.deepEqual(searchTeams(index, ''), []);
  assert.deepEqual(searchTeams(index, '   '), []);
  assert.deepEqual(searchTeams(index, 'zzzz'), []);
  assert.deepEqual(searchTeams(index, '!!!'), []);
});

test('special letters are typed the easy way', () => {
  assert.deepEqual(ids(searchTeams(index, 'bodo')), ['bodo-glimt']);
});

test('suggestions put Brazilian teams first, then the others, by name', () => {
  const first = ids(suggestTeams(index, { limit: 10 }));
  assert.deepEqual(first.slice(0, 5), ['atletico-mineiro', 'brasil', 'palmeiras', 'santos', 'sao-paulo']);
  assert.deepEqual(first.slice(5), ['atletico-madrid', 'barcelona', 'bodo-glimt', 'real-betis', 'real-madrid']);
});

test('suggestions leave out chosen teams and respect the limit', () => {
  assert.deepEqual(ids(suggestTeams(index, { exclude: new Set(['atletico-mineiro']), limit: 2 })), ['brasil', 'palmeiras']);
});

// --- upcoming matches ---------------------------------------------------------------------

const NOW = new Date('2026-11-02T12:00:00Z');
const match = (id, kickoff, home, away, status = 'scheduled') => ({
  id,
  kickoff_utc: kickoff,
  home_team_id: home,
  away_team_id: away,
  status,
});
const MATCHES = [
  match('later', '2026-11-05T22:00:00Z', 'palmeiras', 'santos'),
  match('soon', '2026-11-03T22:00:00Z', 'barcelona', 'palmeiras'),
  match('other-teams', '2026-11-03T20:00:00Z', 'real-betis', 'santos'),
  match('finished', '2026-11-01T22:00:00Z', 'palmeiras', 'santos', 'finished'),
  match('postponed', '2026-11-04T22:00:00Z', 'palmeiras', 'santos', 'postponed'),
  match('cancelled', '2026-11-04T22:00:00Z', 'palmeiras', 'santos', 'cancelled'),
  match('rescheduled', '2026-11-04T18:00:00Z', 'palmeiras', 'sao-paulo', 'rescheduled'),
  match('started-an-hour-ago', '2026-11-02T11:00:00Z', 'palmeiras', 'sao-paulo', 'scheduled'),
  match('live', '2026-11-02T10:30:00Z', 'palmeiras', 'sao-paulo', 'live'),
  match('stale', '2026-11-02T01:00:00Z', 'palmeiras', 'sao-paulo', 'scheduled'),
  match('undecided', '2026-11-06T22:00:00Z', 'palmeiras', null),
];

test('only the followed teams matches, on either side, soonest first', () => {
  const found = upcomingMatches(MATCHES, ['palmeiras'], NOW, 20).map((m) => m.id);
  assert.deepEqual(found, ['live', 'started-an-hour-ago', 'soon', 'rescheduled', 'later', 'undecided']);
});

test('finished, postponed, cancelled and stale matches are not "upcoming"', () => {
  const found = upcomingMatches(MATCHES, ['palmeiras'], NOW, 20).map((m) => m.id);
  for (const gone of ['finished', 'postponed', 'cancelled', 'stale', 'other-teams']) {
    assert.ok(!found.includes(gone), gone);
  }
});

test('several teams combine, and a match of two followed teams appears once', () => {
  const found = upcomingMatches(MATCHES, ['palmeiras', 'santos'], NOW, 20).map((m) => m.id);
  assert.deepEqual(found.filter((id) => id === 'later').length, 1);
  assert.ok(found.includes('other-teams'));
});

test('the list is capped, and no team means no matches', () => {
  assert.equal(upcomingMatches(MATCHES, ['palmeiras'], NOW, 2).length, 2);
  assert.deepEqual(upcomingMatches(MATCHES, [], NOW), []);
});

test('a team that is not decided yet (null) never matches a followed id', () => {
  assert.deepEqual(upcomingMatches([match('x', '2026-11-06T22:00:00Z', null, null)], ['palmeiras'], NOW), []);
});
