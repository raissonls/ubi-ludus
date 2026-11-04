import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { createCalendar, describeEvent } from '../js/calendar.js';
import { createTranslator } from '../js/i18n.js';
import { describeMatch } from '../js/match-model.js';

const strings = JSON.parse(readFileSync(new URL('../i18n/pt-BR.json', import.meta.url), 'utf-8'));
const translator = createTranslator(strings);
const NOW = new Date('2026-11-02T12:00:00Z');
const unfold = (text) => text.replace(/\r\n /g, '');

const team = (id, name) => [id, { id, name, short_name: name }];
const data = {
  teamsById: new Map([team('palmeiras', 'Palmeiras'), team('flamengo', 'Flamengo'), team('brasil', 'Brasil')]),
  competitionsById: new Map([['serie-a', { id: 'serie-a', name: 'Campeonato Brasileiro Série A' }]]),
  broadcastersById: new Map([
    ['globo', { id: 'globo', name: 'TV Globo', kind: 'free_tv' }],
    ['sportv', { id: 'sportv', name: 'SporTV', kind: 'pay_tv' }],
  ]),
  servicesById: new Map(),
};
const broadcast = (id, confidence) => ({ broadcaster_id: id, confidence, source: 'x' });
const match = (id, changes = {}) => ({
  id,
  competition_id: 'serie-a',
  round: '34',
  kickoff_utc: '2026-11-03T22:00:00Z',
  home_team_id: 'palmeiras',
  away_team_id: 'flamengo',
  status: 'scheduled',
  broadcasts: [broadcast('globo', 'rule'), broadcast('sportv', 'rule')],
  ...changes,
});
data.matches = [
  match('a'),
  match('b', { kickoff_utc: '2026-11-05T22:00:00Z', home_team_id: 'brasil', away_team_id: null, broadcasts: [broadcast(null, 'unknown')] }),
  match('c', { status: 'finished', kickoff_utc: '2026-10-30T22:00:00Z' }),
  match('d', { home_team_id: 'flamengo', away_team_id: 'brasil', kickoff_utc: '2026-11-04T22:00:00Z' }),
  match('e', { status: 'cancelled' }),
];

function calendar() {
  const saved = [];
  const made = createCalendar({
    data,
    translator,
    clock: () => NOW,
    url: 'https://example.org/ubi-ludus/',
    save: (name, text) => saved.push({ name, text }),
  });
  return { made, saved };
}

test('an event is named for the teams and says where to watch, with how sure we are', () => {
  const found = describeEvent(describeMatch(data.matches[0], data), { translator, url: 'https://x.org/' });
  assert.equal(found.uid, 'a@ubi-ludus');
  assert.equal(found.start, '2026-11-03T22:00:00Z');
  assert.equal(found.summary, 'Palmeiras x Flamengo');
  assert.match(found.description, /^Campeonato Brasileiro Série A · Rodada 34\n/);
  assert.match(found.description, /Onde assistir: SporTV \(pela tabela de direitos\), TV Globo \(pela tabela de direitos\)\./);
  assert.match(found.description, /Confira a emissora perto do jogo\./);
  assert.match(found.description, /Horário de Brasília: .*19:00/); // 22:00 UTC
});

test('an unknown match names no broadcaster, here as on the card (FR-13)', () => {
  const found = describeEvent(describeMatch(data.matches[1], data), { translator, url: '' });
  assert.match(found.description, /Transmissão ainda não confirmada/);
  assert.equal(/Globo|SporTV|Onde assistir/.test(found.description), false);
  assert.equal(found.summary, 'Brasil x A definir');
});

test('a match every broadcaster of which is confirmed does not ask to be checked', () => {
  const sure = match('s', { broadcasts: [broadcast('globo', 'confirmed')] });
  const found = describeEvent(describeMatch(sure, data), { translator, url: '' });
  assert.match(found.description, /TV Globo \(confirmado\)/);
  assert.equal(found.description.includes('Confira a emissora'), false);
});

test('one match is saved under its own name, as a calendar with that one event', () => {
  const { made, saved } = calendar();
  made.saveMatch(data.matches[0]);
  assert.equal(saved.length, 1);
  assert.equal(saved[0].name, 'ubi-ludus-a.ics');
  const lines = saved[0].text.split('\r\n');
  assert.equal(lines.filter((line) => line === 'BEGIN:VEVENT').length, 1);
  assert.ok(lines.includes('SUMMARY:Palmeiras x Flamengo'));
  assert.ok(lines.includes('DTSTAMP:20261102T120000Z'));
  assert.ok(unfold(saved[0].text).includes('URL:https://example.org/ubi-ludus/'));
});

test('the file name is made safe whatever the match id', () => {
  const { made, saved } = calendar();
  made.saveMatch(match('../../Étrange id!'));
  assert.match(saved[0].name, /^ubi-ludus-[a-z0-9-]+\.ics$/);
  assert.equal(saved[0].name.includes('..'), false);
});

test('the followed teams give their matches that are still to come, soonest first', () => {
  const { made } = calendar();
  assert.deepEqual(made.upcoming(['flamengo']).map((m) => m.id), ['a', 'd']); // not the finished or cancelled
  assert.deepEqual(made.upcoming(['brasil']).map((m) => m.id), ['d', 'b']);
  assert.deepEqual(made.upcoming([]), []);
});

test('all of them are saved in one file, which says nothing about whose teams they are', () => {
  const { made, saved } = calendar();
  assert.equal(made.saveFollowed(['flamengo']), 2);
  assert.equal(saved[0].name, 'ubi-ludus-meus-times.ics');
  const lines = saved[0].text.split('\r\n');
  assert.equal(lines.filter((line) => line === 'BEGIN:VEVENT').length, 2);
  assert.ok(lines.includes('X-WR-CALNAME:Ubi Ludus: jogos dos meus times'));
  made.saveFollowed(['brasil']);
  const name = (text) => text.split('\r\n').find((line) => line.startsWith('X-WR-CALNAME'));
  assert.equal(name(saved[1].text), name(saved[0].text)); // the same name whatever the teams
});

test('with nothing to add no file is saved', () => {
  const { made, saved } = calendar();
  assert.equal(made.saveFollowed(['palmeiras-gone']), 0);
  assert.equal(made.saveFollowed([]), 0);
  assert.deepEqual(saved, []);
});

test('there is no limit of ten, unlike the list', () => {
  const many = Array.from({ length: 25 }, (_, i) =>
    match(`m${i}`, { kickoff_utc: `2026-11-${String(3 + (i % 20)).padStart(2, '0')}T22:00:00Z` }),
  );
  const wide = createCalendar({ data: { ...data, matches: many }, translator, clock: () => NOW, save: () => {} });
  assert.equal(wide.upcoming(['palmeiras']).length, 25);
});
