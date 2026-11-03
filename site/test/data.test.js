// Run with: node --test site/test/   (no dependencies)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { DataError, FILES, SUPPORTED_MAJOR, loadData } from '../js/data.js';

const BASE = 'https://example.org/data/';

function documents(overrides = {}) {
  const base = {
    matches: { schema_version: '1.0', generated_at: '2026-11-02T09:00:00Z', matches: [{ id: 'm-1' }, { id: 'm-2' }] },
    teams: { schema_version: '1.0', generated_at: '2026-11-02T09:00:00Z', teams: [{ id: 'flamengo', name: 'Flamengo' }] },
    competitions: { schema_version: '1.0', generated_at: '2026-11-02T09:00:00Z', competitions: [{ id: 'serie-a' }] },
    broadcasters: {
      schema_version: '1.0',
      generated_at: '2026-11-02T09:00:00Z',
      broadcasters: [{ id: 'globo' }],
      services: [{ id: 'globoplay' }],
    },
    status: { schema_version: '1.0', generated_at: '2026-11-02T09:00:00Z', last_success_at: '2026-11-02T09:00:00Z' },
  };
  return { ...base, ...overrides };
}

/** A fetch that serves these documents by file name and remembers what it was asked. */
function fakeFetch(served) {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url: String(url), options });
    const name = String(url).split('/').pop().replace('.json', '');
    const answer = served[name];
    if (answer instanceof Error) throw answer;
    if (typeof answer === 'number') return { ok: false, status: answer, json: async () => ({}) };
    if (answer === 'not json') {
      return { ok: true, status: 200, json: async () => { throw new SyntaxError('Unexpected token'); } };
    }
    return { ok: true, status: 200, json: async () => answer };
  };
  fetchImpl.calls = calls;
  return fetchImpl;
}

test('all five files are loaded, from the data folder, and each kind is indexed by id', async () => {
  const fetchImpl = fakeFetch(documents());
  const data = await loadData(BASE, fetchImpl);

  assert.deepEqual(fetchImpl.calls.map((c) => c.url).sort(), FILES.map((f) => `${BASE}${f}.json`).sort());
  assert.equal(data.matches.length, 2);
  assert.equal(data.teamsById.get('flamengo').name, 'Flamengo');
  assert.ok(data.competitionsById.has('serie-a'));
  assert.ok(data.broadcastersById.has('globo'));
  assert.ok(data.servicesById.has('globoplay'));
  assert.equal(data.status.last_success_at, '2026-11-02T09:00:00Z');
});

test('the files are asked for fresh, so a day\'s update shows', async () => {
  const fetchImpl = fakeFetch(documents());
  await loadData(BASE, fetchImpl);
  assert.ok(fetchImpl.calls.every((c) => c.options.cache === 'no-cache'));
});

test('the requests carry nothing but the file name', async () => {
  const fetchImpl = fakeFetch(documents());
  await loadData(BASE, fetchImpl);
  for (const call of fetchImpl.calls) {
    assert.equal(new URL(call.url).search, '');
    assert.deepEqual(Object.keys(call.options), ['cache']); // no body, no headers, no credentials
  }
});

test('a file the server does not have names itself in the error', async () => {
  await assert.rejects(loadData(BASE, fakeFetch(documents({ teams: 404 }))), (error) => {
    assert.ok(error instanceof DataError);
    assert.equal(error.file, 'teams');
    assert.match(error.message, /teams\.json: the server answered HTTP 404/);
    return true;
  });
});

test('a network failure is a DataError that keeps its cause', async () => {
  const cause = new TypeError('Failed to fetch');
  await assert.rejects(loadData(BASE, fakeFetch(documents({ status: cause }))), (error) => {
    assert.equal(error.file, 'status');
    assert.equal(error.cause, cause);
    return true;
  });
});

test('a file that is not JSON, or not an object, is refused', async () => {
  await assert.rejects(loadData(BASE, fakeFetch(documents({ matches: 'not json' }))), /matches\.json: is not valid JSON/);
  await assert.rejects(loadData(BASE, fakeFetch(documents({ matches: [] }))), /matches\.json: is not an object/);
  await assert.rejects(loadData(BASE, fakeFetch(documents({ matches: null }))), /matches\.json: is not an object/);
});

test('a newer format than the site knows is refused with a clear message', async () => {
  const future = { ...documents().matches, schema_version: `${SUPPORTED_MAJOR + 1}.0` };
  await assert.rejects(loadData(BASE, fakeFetch(documents({ matches: future }))), /matches\.json: is in format 2\.0; this site reads 1\.x/);
});

test('a minor change in the format is fine', async () => {
  const minor = { ...documents().matches, schema_version: '1.7' };
  const data = await loadData(BASE, fakeFetch(documents({ matches: minor })));
  assert.equal(data.matches.length, 2);
});

test('a file without a version is refused', async () => {
  const { schema_version: _gone, ...unversioned } = documents().teams;
  await assert.rejects(loadData(BASE, fakeFetch(documents({ teams: unversioned }))), /teams\.json: has no schema_version/);
});

test('a missing list is refused, naming the list', async () => {
  const noServices = { ...documents().broadcasters, services: undefined };
  await assert.rejects(loadData(BASE, fakeFetch(documents({ broadcasters: noServices }))), /broadcasters\.json: has no "services" list/);
  await assert.rejects(
    loadData(BASE, fakeFetch(documents({ competitions: { ...documents().competitions, competitions: 'many' } }))),
    /competitions\.json: has no "competitions" list/,
  );
});

test('an empty list is a valid, empty day', async () => {
  const empty = { ...documents().matches, matches: [] };
  const data = await loadData(BASE, fakeFetch(documents({ matches: empty })));
  assert.deepEqual(data.matches, []);
});
