import assert from 'node:assert/strict';
import { test } from 'node:test';

import { buildCatalog, NEUTRAL_SHIRT, searchCountries, shirtOf } from '../js/onboarding-model.js';
import { safeColours } from '../js/shirt.js';

const team = (id, country, extra = {}) => ({
  id,
  name: id.toUpperCase(),
  short_name: id.toUpperCase(),
  aliases: [],
  country,
  colors: { primary: '#111111', secondary: '#eeeeee' },
  ...extra,
});

const TEAMS = [
  team('flamengo', 'BR'),
  team('palmeiras', 'BR'),
  team('brasil', 'BR', { kind: 'national', shirt: { primary: '#ffdf00', secondary: '#009c3b' } }),
  team('estudiantes', 'AR'),
  team('argentina', 'AR', { kind: 'national' }),
  team('uruguai', 'UY', { kind: 'national' }),
  team('real-madrid', 'ES'),
  team('espanha', 'ES', { kind: 'national' }),
  team('marrocos', 'MA', { kind: 'national' }),
];

test('a country is drawn as the shirt of its national team', () => {
  const brazil = buildCatalog(TEAMS).continents[0].countries[0];
  assert.equal(brazil.code, 'BR');
  assert.equal(brazil.nation.id, 'brasil');
  assert.deepEqual(brazil.shirt, { primary: '#ffdf00', secondary: '#009c3b' });
});

test('the clubs of a country are the teams that are not national teams, by name', () => {
  const brazil = buildCatalog(TEAMS).continents[0].countries[0];
  assert.deepEqual(brazil.clubs.map((club) => club.id), ['flamengo', 'palmeiras']);
});

test('only the continents that have a team are listed, in the order of the list', () => {
  const ids = buildCatalog(TEAMS).continents.map((continent) => continent.id);
  assert.deepEqual(ids, ['south-america', 'europe', 'africa']);
});

test('countries come with the most clubs first, then by code', () => {
  const south = buildCatalog(TEAMS).continents[0];
  assert.deepEqual(south.countries.map((country) => country.code), ['BR', 'AR', 'UY']);
});

test('a country with only its national team has no clubs', () => {
  const uruguay = buildCatalog(TEAMS).continents[0].countries.find((c) => c.code === 'UY');
  assert.deepEqual(uruguay.clubs, []);
  assert.equal(uruguay.nation.id, 'uruguai');
});

test('a country the list of continents does not know is still reachable, in a last group', () => {
  const catalog = buildCatalog([...TEAMS, team('club-x', 'ZZ')]);
  const last = catalog.continents.at(-1);
  assert.equal(last.id, 'other');
  assert.deepEqual(last.countries.map((country) => country.code), ['ZZ']);
});

test('a continent shows up to three shirts, the featured teams first', () => {
  const europe = buildCatalog(TEAMS).continents[1];
  assert.deepEqual(europe.featured.map((t) => t.id), ['real-madrid', 'espanha']);
  const south = buildCatalog(TEAMS).continents[0];
  assert.equal(south.featured.length, 3);
  assert.equal(south.featured[0].id, 'flamengo');
});

test('the shirt is the shirt, else the colours, else a neutral grey', () => {
  assert.deepEqual(shirtOf(team('a', 'BR', { shirt: { primary: '#ffffff', secondary: '#000000' } })), {
    primary: '#ffffff',
    secondary: '#000000',
  });
  assert.deepEqual(shirtOf(team('a', 'BR')), { primary: '#111111', secondary: '#eeeeee' });
  assert.deepEqual(shirtOf(undefined), NEUTRAL_SHIRT);
});

test('countries are found by the start of their name, without caring about accents or case', () => {
  const catalog = buildCatalog(TEAMS);
  const names = { BR: 'Brasil', AR: 'Argentina', UY: 'Uruguai', ES: 'Espanha', MA: 'Marrocos' };
  const found = (text) => searchCountries(catalog, text, (code) => names[code]).map((x) => x.country.code);
  assert.deepEqual(found('bra'), ['BR']);
  assert.deepEqual(found('ESPA'), ['ES']);
  assert.deepEqual(found('ar'), ['AR']);
  assert.deepEqual(found('asil'), []);
  assert.deepEqual(found(''), []);
});

test('only #rrggbb is drawn: anything else becomes a neutral grey', () => {
  assert.deepEqual(safeColours({ primary: '#ABCDEF', secondary: '#012345' }), {
    primary: '#ABCDEF',
    secondary: '#012345',
  });
  const grey = '#9aa0ad';
  assert.deepEqual(safeColours({ primary: 'red', secondary: 'url(javascript:alert(1))' }), {
    primary: grey,
    secondary: grey,
  });
  assert.deepEqual(safeColours(undefined), { primary: grey, secondary: grey });
  assert.deepEqual(safeColours({ primary: 5, secondary: null }), { primary: grey, secondary: grey });
});
