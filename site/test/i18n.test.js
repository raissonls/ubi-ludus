// Run with: node --test site/test/   (no dependencies)
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

import { applyStrings, createTranslator, loadStrings } from '../js/i18n.js';

const strings = {
  greeting: { hello: 'Olá, {name}!' },
  matches: {
    count: { one: '{count} jogo', other: '{count} jogos' },
  },
};

test('a string is found by its dotted key and its values are filled in', () => {
  const { t } = createTranslator(strings);
  assert.equal(t('greeting.hello', { name: 'Ana' }), 'Olá, Ana!');
});

test('a value is inserted as text, never as markup', () => {
  const { t } = createTranslator(strings);
  assert.equal(t('greeting.hello', { name: '<img src=x onerror=alert(1)>' }), 'Olá, <img src=x onerror=alert(1)>!');
});

test('a placeholder without a value stays visible', () => {
  const { t } = createTranslator(strings);
  assert.equal(t('greeting.hello'), 'Olá, {name}!');
});

test('a missing string shows its key instead of a blank', () => {
  const { t, plural } = createTranslator(strings);
  assert.equal(t('nothing.here'), '[nothing.here]');
  assert.equal(t('greeting'), '[greeting]'); // a group is not a string
  assert.equal(plural('nothing.here', 2), '[nothing.here]');
  assert.equal(plural('greeting.hello', 2), '[greeting.hello]'); // a string is not a set of forms
});

test('plural forms follow Portuguese: 0 and 1 are singular, 2 or more plural', () => {
  const { plural } = createTranslator(strings);
  assert.equal(plural('matches.count', 0), '0 jogo');
  assert.equal(plural('matches.count', 1), '1 jogo');
  assert.equal(plural('matches.count', 2), '2 jogos');
  assert.equal(plural('matches.count', 12), '12 jogos');
});

test('a missing plural form falls back to "other"', () => {
  const { plural } = createTranslator({ x: { other: '{count} itens' } });
  assert.equal(plural('x', 1), '1 itens');
});

function fakeElement(attributes) {
  const element = {
    textContent: '',
    attributes: { ...attributes },
    getAttribute(name) {
      return this.attributes[name];
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  };
  return element;
}

test('applyStrings sets text and attributes from the page markup', () => {
  const heading = fakeElement({ 'data-i18n': 'greeting.hello' });
  const link = fakeElement({ 'data-i18n-attr': 'aria-label:greeting.hello; title : greeting.hello' });
  const root = {
    querySelectorAll(selector) {
      return selector === '[data-i18n]' ? [heading] : [link];
    },
  };

  applyStrings(root, createTranslator(strings));

  assert.equal(heading.textContent, 'Olá, {name}!');
  assert.equal(link.attributes['aria-label'], 'Olá, {name}!');
  assert.equal(link.attributes.title, 'Olá, {name}!');
});

test('loadStrings returns the parsed file, and fails loudly when it cannot', async () => {
  const ok = async () => ({ ok: true, status: 200, json: async () => strings });
  assert.deepEqual(await loadStrings('x.json', ok), strings);

  const missing = async () => ({ ok: false, status: 404, json: async () => ({}) });
  await assert.rejects(loadStrings('x.json', missing), /HTTP 404/);
});

test('the real strings file is valid and has no empty string', async () => {
  const text = await readFile(new URL('../i18n/pt-BR.json', import.meta.url), 'utf8');
  const real = JSON.parse(text);
  const empty = [];
  (function walk(node, path) {
    for (const [key, value] of Object.entries(node)) {
      if (typeof value === 'object') walk(value, `${path}${key}.`);
      else if (typeof value !== 'string' || value.trim() === '') empty.push(`${path}${key}`);
    }
  })(real, '');
  assert.deepEqual(empty, []);
});
