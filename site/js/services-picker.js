// "Which services do you have?" (FR-21): one checkbox for each subscription in the catalogue
// (pay TV, Premiere, Globoplay, Disney+, ...), saved with the other choices.
//
// Free TV and YouTube need no subscription, so nothing is ticked by default: no choice at all
// means "free TV and YouTube only", and the page says so. Native checkboxes with real labels are
// the most accessible control there is, so that is what this uses.

import { el } from './dom.js';
import { LOCALE } from './i18n.js';

const listFormat = new Intl.ListFormat(LOCALE, { style: 'long', type: 'conjunction' });

/** The names of the broadcasters a service includes ("SporTV", "ESPN"), in catalogue order. */
export function includedNames(service, broadcastersById) {
  return service.includes_broadcasters.map((id) => broadcastersById.get(id)?.name ?? id);
}

/**
 * @param services          the published services
 * @param broadcastersById  to name what each service includes
 * @param translator        from i18n.js
 * @param onChange          called with the ids ticked, in catalogue order, after each change
 */
export function createServicesPicker({ services, broadcastersById, translator, onChange }) {
  const list = document.getElementById('service-options');
  const summary = document.getElementById('services-summary');
  const known = new Set(services.map((service) => service.id));
  const boxes = new Map();

  function ticked() {
    return services.filter((service) => boxes.get(service.id).checked).map((service) => service.id);
  }

  function describe() {
    const count = ticked().length;
    summary.textContent =
      count === 0 ? translator.t('services.noneChosen') : translator.plural('services.chosen', count);
  }

  list.replaceChildren(
    ...services.map((service) => {
      const id = `service-${service.id}`;
      const box = el('input', { type: 'checkbox', id, value: service.id, 'aria-describedby': `${id}-includes` });
      box.addEventListener('change', () => {
        describe();
        onChange(ticked());
      });
      boxes.set(service.id, box);
      return el('li', { class: 'service' }, [
        box,
        el('label', { for: id, text: service.name }),
        el('span', {
          id: `${id}-includes`,
          class: 'service__includes',
          text: translator.t('services.includes', {
            names: listFormat.format(includedNames(service, broadcastersById)),
          }),
        }),
      ]);
    }),
  );
  describe();

  return {
    /** Tick exactly these ids (what was saved, or nothing after a reset). Unknown ids are ignored. */
    update(ids) {
      const wanted = new Set(ids.filter((id) => known.has(id)));
      for (const [id, box] of boxes) {
        box.checked = wanted.has(id);
      }
      describe();
    },
  };
}
