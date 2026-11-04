import assert from 'node:assert/strict';
import { test } from 'node:test';

import { DataError, FILES } from '../js/data.js';
import { CACHE_NAME, createDataCache } from '../js/data-cache.js';
import { loadBest } from '../js/data-source.js';
import { problemKind } from '../js/states.js';

const BASE = 'https://example.org/data/';
const STAMP = '2026-11-02T09:00:00Z';

function documents(changes = {}) {
  const head = { schema_version: '1.0', generated_at: STAMP };
  return {
    matches: { ...head, matches: [{ id: 'm-1' }] },
    teams: { ...head, teams: [{ id: 'flamengo' }] },
    competitions: { ...head, competitions: [{ id: 'serie-a' }] },
    broadcasters: { ...head, broadcasters: [{ id: 'globo' }], services: [{ id: 'globoplay' }] },
    status: { ...head, last_success_at: STAMP },
    ...changes,
  };
}

/** A fetch serving these documents, or failing the way `failure` says. */
function fetchOf(served, failure = null) {
  return async (url) => {
    if (failure === 'network') throw new TypeError('Failed to fetch');
    if (typeof failure === 'number') return { ok: false, status: failure, json: async () => ({}) };
    const name = String(url).split('/').pop().replace('.json', '');
    return { ok: true, status: 200, json: async () => served[name] };
  };
}

/** A stand-in for `caches`: one named cache that keeps Responses by address. */
function fakeCaches({ broken = false } = {}) {
  const stores = new Map();
  return {
    stores,
    async open(name) {
      if (broken) throw new TypeError('caches is not available');
      if (!stores.has(name)) stores.set(name, new Map());
      const store = stores.get(name);
      return {
        put: async (key, response) => store.set(key, response),
        match: async (key) => store.get(key)?.clone(),
      };
    },
  };
}

test('a load that works is returned from the network and kept for later', async () => {
  const caches = fakeCaches();
  const cache = createDataCache(BASE, caches);
  const result = await loadBest({ baseUrl: BASE, fetchImpl: fetchOf(documents()), cache });
  assert.equal(result.source, 'network');
  assert.equal(result.data.matches.length, 1);
  assert.equal(caches.stores.get(CACHE_NAME).size, FILES.length);
  assert.deepEqual(await cache.load(), documents());
});

test('when the load fails the copy kept from the last time is used, and says why', async () => {
  const cache = createDataCache(BASE, fakeCaches());
  await loadBest({ baseUrl: BASE, fetchImpl: fetchOf(documents()), cache });
  for (const failure of ['network', 500]) {
    const result = await loadBest({ baseUrl: BASE, fetchImpl: fetchOf({}, failure), cache });
    assert.equal(result.source, 'saved', String(failure));
    assert.equal(result.data.matches.length, 1);
    assert.ok(result.reason instanceof DataError);
    assert.equal(result.data.status.last_success_at, STAMP); // the freshness shown is the copy's
  }
});

test('with no copy the failure is raised as it was', async () => {
  const cache = createDataCache(BASE, fakeCaches());
  await assert.rejects(loadBest({ baseUrl: BASE, fetchImpl: fetchOf({}, 'network'), cache }), (error) => {
    assert.ok(error instanceof DataError);
    assert.equal(error.kind, 'network');
    return true;
  });
});

test('a copy that is incomplete is no copy', async () => {
  const caches = fakeCaches();
  const cache = createDataCache(BASE, caches);
  await loadBest({ baseUrl: BASE, fetchImpl: fetchOf(documents()), cache });
  caches.stores.get(CACHE_NAME).delete(`${BASE}status.json`);
  await assert.rejects(loadBest({ baseUrl: BASE, fetchImpl: fetchOf({}, 500), cache }), /HTTP 500/);
});

test('a damaged or outdated copy is not used either', async () => {
  const caches = fakeCaches();
  const cache = createDataCache(BASE, caches);
  await cache.save(documents({ teams: { schema_version: '1.0' } })); // no "teams" list
  await assert.rejects(loadBest({ baseUrl: BASE, fetchImpl: fetchOf({}, 'network'), cache }), /could not be reached/);
  await cache.save(documents({ matches: { ...documents().matches, schema_version: '0.9' } }));
  await assert.rejects(loadBest({ baseUrl: BASE, fetchImpl: fetchOf({}, 'network'), cache }), /could not be reached/);
});

test('data newer than the site is never hidden behind an old copy', async () => {
  const cache = createDataCache(BASE, fakeCaches());
  await loadBest({ baseUrl: BASE, fetchImpl: fetchOf(documents()), cache });
  const future = documents({ matches: { ...documents().matches, schema_version: '2.0' } });
  await assert.rejects(loadBest({ baseUrl: BASE, fetchImpl: fetchOf(future), cache }), (error) => {
    assert.equal(error.kind, 'version');
    return true;
  });
});

test('without Cache Storage the site works and simply has no copy', async () => {
  const cache = createDataCache(BASE, fakeCaches({ broken: true }));
  const result = await loadBest({ baseUrl: BASE, fetchImpl: fetchOf(documents()), cache });
  assert.equal(result.source, 'network');
  assert.equal(await cache.load(), null);
  await assert.rejects(loadBest({ baseUrl: BASE, fetchImpl: fetchOf({}, 500), cache }), /HTTP 500/);
  const absent = createDataCache(BASE, undefined);
  await absent.save(documents()); // must not throw
  assert.equal(await absent.load(), null);
});

test('the failures are told apart by kind', async () => {
  const kinds = {};
  for (const [label, failure, served] of [
    ['network', 'network', {}],
    ['http', 503, {}],
    ['invalid', null, documents({ teams: { schema_version: '1.0' } })],
    ['version', null, documents({ status: { schema_version: '3.0' } })],
  ]) {
    const cache = createDataCache(BASE, fakeCaches());
    await loadBest({ baseUrl: BASE, fetchImpl: fetchOf(served, failure), cache }).catch((error) => {
      kinds[label] = error.kind;
    });
  }
  assert.deepEqual(kinds, { network: 'network', http: 'http', invalid: 'invalid', version: 'version' });
});

test('each failure gets its own screen, and being offline wins over a vague one', () => {
  assert.equal(problemKind(new DataError('matches', 'x', 'network'), true), 'offline');
  assert.equal(problemKind(new DataError('matches', 'x', 'http'), true), 'error');
  assert.equal(problemKind(new DataError('matches', 'x', 'invalid'), true), 'error');
  assert.equal(problemKind(new DataError('matches', 'x', 'http'), false), 'offline'); // navigator.onLine
  assert.equal(problemKind(new DataError('matches', 'x', 'version'), false), 'outdated');
  assert.equal(problemKind(new Error('who knows'), true), 'error');
});
