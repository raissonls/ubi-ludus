// Entry point. For now it puts the strings on the page; the data and the views come in the
// next tasks (M3-02 onwards).

import { applyStrings, createTranslator, loadStrings } from './i18n.js';

const strings = await loadStrings(new URL('../i18n/pt-BR.json', import.meta.url));
applyStrings(document, createTranslator(strings));

// Tests and styles can tell the page is ready.
document.documentElement.dataset.ready = 'true';
