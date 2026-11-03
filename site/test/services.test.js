// Run with: node --test site/test/   (no dependencies)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { includedNames } from '../js/services-picker.js';

const broadcasters = new Map([
  ['sportv', { id: 'sportv', name: 'SporTV' }],
  ['espn', { id: 'espn', name: 'ESPN' }],
]);

test('a service names the broadcasters it includes, in catalogue order', () => {
  const service = { id: 'tv-por-assinatura', includes_broadcasters: ['sportv', 'espn'] };
  assert.deepEqual(includedNames(service, broadcasters), ['SporTV', 'ESPN']);
});

test('a broadcaster the data does not describe shows its id rather than disappearing', () => {
  const service = { id: 'x', includes_broadcasters: ['sportv', 'ghost'] };
  assert.deepEqual(includedNames(service, broadcasters), ['SporTV', 'ghost']);
});

test('the names read as Portuguese prose', () => {
  const format = new Intl.ListFormat('pt-BR', { style: 'long', type: 'conjunction' });
  assert.equal(format.format(['SporTV', 'ESPN']), 'SporTV e ESPN');
  assert.equal(format.format(['SporTV', 'ESPN', 'TNT Sports']), 'SporTV, ESPN e TNT Sports');
});
