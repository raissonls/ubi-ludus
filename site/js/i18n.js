// Every string the visitor reads lives in i18n/<locale>.json (PRD: localisation). This module
// loads it and puts it on the page. Text goes in with textContent, never as HTML, so a string (or
// a value inserted into one) can never become markup.

export const LOCALE = 'pt-BR';

/** Fetch and parse a strings file. */
export async function loadStrings(url, fetchImpl = fetch) {
  const response = await fetchImpl(url);
  if (!response.ok) {
    throw new Error(`Could not load ${url}: HTTP ${response.status}`);
  }
  return response.json();
}

function find(strings, key) {
  let node = strings;
  for (const part of key.split('.')) {
    if (node === null || typeof node !== 'object' || !(part in node)) {
      return undefined;
    }
    node = node[part];
  }
  return node;
}

/**
 * Build the functions the rest of the site uses to read strings.
 *
 * t(key, values)        a string, with {name} replaced from values
 * has(key)              whether the strings file has a string at that key
 * plural(key, n, values) the form for n ("one", "other", ...) of an object of forms, with
 *                       {count} set to n; the form is chosen by Intl.PluralRules
 */
export function createTranslator(strings, locale = LOCALE) {
  const rules = new Intl.PluralRules(locale);

  function fill(text, values) {
    return text.replace(/\{(\w+)\}/g, (placeholder, name) =>
      Object.hasOwn(values, name) ? String(values[name]) : placeholder,
    );
  }

  function t(key, values = {}) {
    const text = find(strings, key);
    if (typeof text !== 'string') {
      // A missing string is a bug to see, not a blank to hide.
      return `[${key}]`;
    }
    return fill(text, values);
  }

  function plural(key, count, values = {}) {
    const forms = find(strings, key);
    if (forms === null || typeof forms !== 'object') {
      return `[${key}]`;
    }
    const form = forms[rules.select(count)] ?? forms.other;
    return typeof form === 'string' ? fill(form, { ...values, count }) : `[${key}]`;
  }

  function has(key) {
    return typeof find(strings, key) === 'string';
  }

  return { t, plural, has };
}

/**
 * Fill the page from the strings:
 *   data-i18n="key"                       sets the element's text
 *   data-i18n-attr="aria-label:key;..."  sets attributes
 */
export function applyStrings(root, translator) {
  for (const element of root.querySelectorAll('[data-i18n]')) {
    element.textContent = translator.t(element.getAttribute('data-i18n'));
  }
  for (const element of root.querySelectorAll('[data-i18n-attr]')) {
    for (const pair of element.getAttribute('data-i18n-attr').split(';')) {
      const [attribute, key] = pair.split(':').map((part) => part.trim());
      if (attribute && key) {
        element.setAttribute(attribute, translator.t(key));
      }
    }
  }
}
