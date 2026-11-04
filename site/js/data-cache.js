// A copy of the last data that loaded, kept in this browser (Cache Storage) so the site can still
// show matches when the next load fails: no connection, a server that is down. The copy is the
// published data and nothing about the visitor. It can be missing or refuse to work (private
// modes, an insecure page, a full disk), and then the site simply has no copy to fall back on.

import { FILES } from './data.js';

export const CACHE_NAME = 'ubi-ludus-data-v1';

/**
 * @param baseUrl       where the data files live; each copy is kept under its own address
 * @param cacheStorage  the browser's `caches`; tests pass a fake
 */
export function createDataCache(baseUrl, cacheStorage = globalThis.caches) {
  const keyOf = (name) => new URL(`${name}.json`, baseUrl).href;

  return {
    /** Keep these five documents (by file name), replacing the previous copy. Never throws. */
    async save(documents) {
      try {
        const cache = await cacheStorage.open(CACHE_NAME);
        await Promise.all(
          FILES.map((name) =>
            cache.put(keyOf(name), new Response(JSON.stringify(documents[name]))),
          ),
        );
      } catch {
        // No copy this time; the next successful load tries again.
      }
    },

    /** The kept documents by file name, or null if there is no complete copy. Never throws. */
    async load() {
      try {
        const cache = await cacheStorage.open(CACHE_NAME);
        const found = {};
        for (const name of FILES) {
          const response = await cache.match(keyOf(name));
          if (!response) return null;
          found[name] = await response.json();
        }
        return found;
      } catch {
        return null;
      }
    },
  };
}
