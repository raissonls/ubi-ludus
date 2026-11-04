// Where the page's data comes from: the published files if they load, else the copy kept from the
// last time they did. A copy is checked like any file (it may be old or damaged), and it is never
// used when the failure is that the data is newer than this site: that is for the visitor to fix by
// reloading, not for an old copy to hide.

import { buildData, fetchDocuments, validate, FILES } from './data.js';

/**
 * @param cache  from data-cache.js (save, load)
 * @returns {data, source}  source is "network" or "saved"; when "saved", `reason` is the DataError
 *   that sent us to the copy. Throws the DataError if there is no usable copy either.
 */
export async function loadBest({ baseUrl, fetchImpl, cache }) {
  let failure;
  try {
    const documents = await fetchDocuments(baseUrl, fetchImpl);
    await cache.save(documents);
    return { data: buildData(documents), source: 'network' };
  } catch (error) {
    failure = error;
  }
  if (failure.kind === 'version') {
    throw failure;
  }
  const kept = await cache.load();
  if (kept) {
    try {
      for (const name of FILES) validate(name, kept[name]);
      return { data: buildData(kept), source: 'saved', reason: failure };
    } catch {
      // A damaged or outdated copy is no help.
    }
  }
  throw failure;
}
