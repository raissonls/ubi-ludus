// Run with: node --test site/test/   (no dependencies)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { MAX_IDS, ONBOARDED_KEY, STORAGE_KEY, cleanIds, createPreferences, restrictTo } from '../js/preferences.js';

/** A storage that behaves like localStorage, and can be told to misbehave. */
function fakeStorage(initial = {}, { failGet = false, failSet = false, failRemove = false } = {}) {
  const items = { ...initial };
  return {
    items,
    getItem(key) {
      if (failGet) throw new Error('blocked');
      return key in items ? items[key] : null;
    },
    setItem(key, value) {
      if (failSet) throw new DOMException('full', 'QuotaExceededError');
      items[key] = String(value);
    },
    removeItem(key) {
      if (failRemove) throw new Error('blocked');
      delete items[key];
    },
  };
}

const saved = (storage) => JSON.parse(storage.items[STORAGE_KEY]);

test('a new visitor has no choices', () => {
  const preferences = createPreferences(() => fakeStorage());
  assert.deepEqual(preferences.get(), { teams: [], services: [], onlyWatchable: false });
  assert.ok(preferences.isPersistent());
});

test('choices are saved in storage, and found there the next visit', () => {
  const storage = fakeStorage();
  const first = createPreferences(() => storage);
  first.setTeams(['palmeiras', 'real-madrid']);
  first.setServices(['hbo-max']);

  assert.deepEqual(saved(storage), { version: 1, teams: ['palmeiras', 'real-madrid'], services: ['hbo-max'], onlyWatchable: false });
  const next = createPreferences(() => storage);
  assert.deepEqual(next.get(), { teams: ['palmeiras', 'real-madrid'], services: ['hbo-max'], onlyWatchable: false });
});

test('get returns a copy, so nobody changes the choices by accident', () => {
  const preferences = createPreferences(() => fakeStorage());
  preferences.setTeams(['palmeiras']);
  preferences.get().teams.push('hacked');
  assert.deepEqual(preferences.get().teams, ['palmeiras']);
});

test('reset forgets the saved copy and the one in memory', () => {
  const storage = fakeStorage();
  const preferences = createPreferences(() => storage);
  preferences.setTeams(['palmeiras']);
  preferences.reset();

  assert.deepEqual(preferences.get(), { teams: [], services: [], onlyWatchable: false });
  assert.ok(!(STORAGE_KEY in storage.items));
  assert.deepEqual(createPreferences(() => storage).get(), { teams: [], services: [], onlyWatchable: false });
});

test('listeners hear about every change and can stop listening', () => {
  const preferences = createPreferences(() => fakeStorage());
  const heard = [];
  const stop = preferences.subscribe((value) => heard.push(value));
  preferences.setTeams(['palmeiras']);
  preferences.setServices(['hbo-max']);
  preferences.reset();
  stop();
  preferences.setTeams(['santos']);

  assert.deepEqual(heard, [
    { teams: ['palmeiras'], services: [], onlyWatchable: false },
    { teams: ['palmeiras'], services: ['hbo-max'], onlyWatchable: false },
    { teams: [], services: [], onlyWatchable: false },
  ]);
});

test('ids are cleaned: only well-formed, once each, a bounded number', () => {
  assert.deepEqual(cleanIds(['a', 'a', 'b-c']), ['a', 'b-c']);
  assert.deepEqual(cleanIds(['UPPER', 'has space', '', '-x', 'x-', 'x--y', 7, null, {}, '<img>', 'ok']), ['ok']);
  assert.deepEqual(cleanIds('not a list'), []);
  assert.deepEqual(cleanIds(undefined), []);
  assert.deepEqual(cleanIds(['x'.repeat(81)]), []);
  assert.equal(cleanIds(Array.from({ length: 500 }, (_, i) => `team-${i}`)).length, MAX_IDS);
});

test('what is saved is cleaned too, so a hand-edited value cannot get in', () => {
  const storage = fakeStorage();
  const preferences = createPreferences(() => storage);
  preferences.setTeams(['palmeiras', '<script>alert(1)</script>', 'palmeiras']);
  assert.deepEqual(saved(storage).teams, ['palmeiras']);
});

test('a damaged saved value is ignored, not an error', () => {
  for (const damaged of ['{ not json', 'null', '[]', '"text"', JSON.stringify({ version: 2, teams: ['a'] }), JSON.stringify({ teams: ['a'] })]) {
    const preferences = createPreferences(() => fakeStorage({ [STORAGE_KEY]: damaged }));
    assert.deepEqual(preferences.get(), { teams: [], services: [], onlyWatchable: false }, damaged);
  }
});

test('a saved value with bad ids keeps only the good ones', () => {
  const stored = JSON.stringify({ version: 1, teams: ['palmeiras', 'BAD ID', 3], services: 'nope' });
  const preferences = createPreferences(() => fakeStorage({ [STORAGE_KEY]: stored }));
  assert.deepEqual(preferences.get(), { teams: ['palmeiras'], services: [], onlyWatchable: false });
});

test('restrictTo drops ids the data does not know', () => {
  const known = { teams: new Set(['palmeiras']), services: new Set(['hbo-max']) };
  assert.deepEqual(
    restrictTo({ teams: ['palmeiras', 'gone-fc'], services: ['hbo-max', 'old-service'], onlyWatchable: false }, known),
    { teams: ['palmeiras'], services: ['hbo-max'], onlyWatchable: false },
  );
});

// --- storage that is missing or refuses -----------------------------------------------------

test('with no storage at all, the choices live in memory and the site still works', () => {
  const preferences = createPreferences(() => undefined);
  preferences.setTeams(['palmeiras']);
  assert.deepEqual(preferences.get().teams, ['palmeiras']);
  assert.equal(preferences.isPersistent(), false);
  preferences.reset();
  assert.deepEqual(preferences.get().teams, []);
});

test('when merely touching storage throws (blocked site data), nothing breaks', () => {
  const preferences = createPreferences(() => {
    throw new DOMException('denied', 'SecurityError');
  });
  assert.deepEqual(preferences.get(), { teams: [], services: [], onlyWatchable: false });
  preferences.setTeams(['palmeiras']);
  preferences.setServices(['hbo-max']);
  assert.deepEqual(preferences.get(), { teams: ['palmeiras'], services: ['hbo-max'], onlyWatchable: false });
  preferences.reset();
  assert.equal(preferences.isPersistent(), false);
});

test('when reading fails the visit starts empty and is not persistent', () => {
  const preferences = createPreferences(() => fakeStorage({ [STORAGE_KEY]: '{}' }, { failGet: true }));
  assert.deepEqual(preferences.get(), { teams: [], services: [], onlyWatchable: false });
  assert.equal(preferences.isPersistent(), false);
});

test('when storage is full the choice holds for this visit and is flagged as not saved', () => {
  const storage = fakeStorage({}, { failSet: true });
  const preferences = createPreferences(() => storage);
  preferences.setTeams(['palmeiras']);
  assert.deepEqual(preferences.get().teams, ['palmeiras']);
  assert.equal(preferences.isPersistent(), false);
});

test('when removing fails, reset still clears what the visitor sees', () => {
  const storage = fakeStorage({ [STORAGE_KEY]: JSON.stringify({ version: 1, teams: ['palmeiras'], services: [] }) }, { failRemove: true });
  const preferences = createPreferences(() => storage);
  preferences.reset();
  assert.deepEqual(preferences.get(), { teams: [], services: [], onlyWatchable: false });
  assert.equal(preferences.isPersistent(), false);
});

test('"only what I can watch" is saved, found again, and anything but true means off', () => {
  const storage = fakeStorage();
  const preferences = createPreferences(() => storage);
  preferences.setOnlyWatchable(true);
  assert.equal(saved(storage).onlyWatchable, true);
  assert.equal(createPreferences(() => storage).get().onlyWatchable, true);
  preferences.setOnlyWatchable('yes');
  assert.equal(preferences.get().onlyWatchable, false);
  const older = fakeStorage({ [STORAGE_KEY]: JSON.stringify({ version: 1, teams: ['palmeiras'], services: [] }) });
  assert.equal(createPreferences(() => older).get().onlyWatchable, false); // saved before it existed
  preferences.setOnlyWatchable(true);
  preferences.reset();
  assert.equal(preferences.get().onlyWatchable, false);
});

test('adopting choices from a shared link shows them without saving anything', () => {
  const storage = fakeStorage();
  const preferences = createPreferences(() => storage);
  preferences.setTeams(['palmeiras']);
  const heard = [];
  preferences.subscribe((choices) => heard.push(choices));
  preferences.adopt({ teams: ['brasil'], services: ['globoplay'], onlyWatchable: true });
  assert.deepEqual(preferences.get(), { teams: ['brasil'], services: ['globoplay'], onlyWatchable: true });
  assert.deepEqual(saved(storage).teams, ['palmeiras']); // what was saved is untouched
  assert.deepEqual(heard, []);
  preferences.setServices(['premiere']); // the first real change saves what is shown
  assert.deepEqual(saved(storage), { version: 1, teams: ['brasil'], services: ['premiere'], onlyWatchable: true });
});

test('adopting leaves out what the link does not mention and cleans what it does', () => {
  const preferences = createPreferences(() => fakeStorage());
  preferences.setTeams(['palmeiras']);
  preferences.adopt({ teams: null, services: ['BAD ID', 'premiere'], onlyWatchable: null });
  assert.deepEqual(preferences.get(), { teams: ['palmeiras'], services: ['premiere'], onlyWatchable: false });
});

// --- the first-run flow: has the visitor seen it? --------------------------------------------

test('a new visitor has not seen the first-run flow, and once they have it is remembered', () => {
  const storage = fakeStorage();
  const first = createPreferences(() => storage);
  assert.equal(first.isOnboarded(), false);
  first.markOnboarded();
  assert.equal(first.isOnboarded(), true);
  assert.equal(storage.items[ONBOARDED_KEY], '1');
  assert.equal(createPreferences(() => storage).isOnboarded(), true);
});

test('seeing the first-run flow is not a choice: nothing is saved in the choices for it', () => {
  const storage = fakeStorage();
  const preferences = createPreferences(() => storage);
  preferences.markOnboarded();
  assert.ok(!(STORAGE_KEY in storage.items));
  assert.deepEqual(preferences.get(), { teams: [], services: [], onlyWatchable: false });
});

test('reset forgets that the flow was seen, so it is offered again', () => {
  const storage = fakeStorage();
  const preferences = createPreferences(() => storage);
  preferences.markOnboarded();
  preferences.reset();
  assert.equal(preferences.isOnboarded(), false);
  assert.ok(!(ONBOARDED_KEY in storage.items));
});

test('when storage refuses the flag it still holds for this visit', () => {
  const preferences = createPreferences(() => fakeStorage({}, { failSet: true }));
  preferences.markOnboarded();
  assert.equal(preferences.isOnboarded(), true);
  assert.equal(preferences.isPersistent(), false);
});

test('only the exact flag value counts as seen', () => {
  const storage = fakeStorage({ [ONBOARDED_KEY]: 'yes' });
  assert.equal(createPreferences(() => storage).isOnboarded(), false);
});
