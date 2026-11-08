// The first-run flow: a welcome screen, then continent, country and team (each a grid of cards,
// the teams drawn as shirts in their colours), then the services the visitor has. Nothing is
// asked that the site does not need, and nothing leaves the browser (the choices are saved by
// preferences.js, like every other choice).
//
// It is a modal dialog (role="dialog", aria-modal): while it is open the rest of the page is inert,
// the focus moves to each screen's title, Escape or "Pular" leaves it, and what the visitor picks
// is said in a polite live region. The markup it fills is in index.html.

import { countryName } from './countries.js';
import { el } from './dom.js';
import { buildCatalog, searchCountries, shirtOf } from './onboarding-model.js';
import { buildIndex, searchTeams } from './search.js';
import { createShirt } from './shirt.js';

const SEARCH_LIMIT = 6;
const ANNOUNCE_AFTER_TYPING_MS = 350;
const FIRST_STEP_OF = { continents: 1, countries: 1, teams: 1, services: 2 };

/**
 * @param data         the published data (teams, services, broadcasters)
 * @param translator   from i18n.js
 * @param preferences  from preferences.js: the choices are saved through it
 */
export function createOnboarding({ data, translator, preferences }) {
  const root = document.getElementById('onboarding');
  const stage = document.getElementById('ob-stage');
  const live = document.getElementById('ob-live');
  const outside = [...document.querySelectorAll('.skip-link, .site-header, main, .site-footer')];

  const t = (key, values) => translator.t(key, values);
  const catalog = buildCatalog(data.teams);
  const index = buildIndex(data.teams);
  const listFormat = new Intl.ListFormat('pt-BR', { style: 'long', type: 'conjunction' });
  const nameOf = (code) => countryName(code, translator);
  const continentName = (id) => t(['onboarding.continent', id].join('.'));

  let step = 'welcome';
  let direction = 'forward';
  let continent = null;
  let country = null;
  let picks = [];
  let services = new Set();
  let query = '';
  let viaSearch = false;
  let opener = null;
  let announcedOnce = false;
  let typingTimer = null;
  const tiles = new Map(); // team id -> its button, to update without redrawing the screen
  let bar = null;

  function say(text) {
    announcedOnce = !announcedOnce; // the same sentence twice in a row is not read again
    live.textContent = announcedOnce ? text : `${text} `;
  }

  // ---- small pieces ----------------------------------------------------------------------

  const stagger = (element, position) => {
    element.style.setProperty('--i', String(Math.min(position, 14)));
    return element;
  };

  function words(text, highlightLast) {
    const parts = text.split(' ');
    return parts.flatMap((word, position) => {
      const span = el('span', { class: 'ob-word', text: word });
      if (position >= parts.length - highlightLast) span.classList.add('is-accent');
      span.style.setProperty('--i', String(position));
      return position === 0 ? [span] : [document.createTextNode(' '), span];
    });
  }

  function title(content) {
    return el('h2', { class: 'ob__title', tabindex: '-1' }, Array.isArray(content) ? content : [content]);
  }

  function lead(text) {
    return el('p', { class: 'ob__lead', text });
  }

  function primary(label, onClick, extraClass = '') {
    const button = el('button', { type: 'button', class: `ob-button ${extraClass}`.trim(), text: label });
    button.addEventListener('click', onClick);
    return button;
  }

  function link(label, onClick) {
    const button = el('button', { type: 'button', class: 'ob-link', text: label });
    button.addEventListener('click', onClick);
    return button;
  }

  // ---- the picks -------------------------------------------------------------------------

  const picked = (id) => picks.includes(id);

  function toggle(team) {
    if (picked(team.id)) {
      picks = picks.filter((id) => id !== team.id);
      say(
        picks.length === 0
          ? t('onboarding.removedAll', { team: team.name })
          : translator.plural('onboarding.removed', picks.length, { team: team.name }),
      );
    } else {
      picks = [...picks, team.id];
      say(translator.plural('onboarding.added', picks.length, { team: team.name }));
    }
    paintTiles(team.id);
    drawBar();
  }

  function paintTiles(id) {
    const button = tiles.get(id);
    if (!button) return;
    const on = picked(id);
    button.setAttribute('aria-pressed', String(on));
    button.classList.toggle('is-picked', on);
    if (on) {
      const shirt = button.querySelector('.shirt');
      shirt.classList.remove('is-bounce');
      void shirt.getBoundingClientRect(); // restart the animation if it is tapped again
      shirt.classList.add('is-bounce');
    }
  }

  function teamTile(team, position, { large = false } = {}) {
    const button = el('button', { type: 'button', class: `ob-tile${large ? ' ob-tile--wide' : ''}`, 'aria-pressed': 'false' }, [
      createShirt(shirtOf(team), large ? 52 : 64),
      el('span', { class: 'ob-tile__text' }, [
        ...(large ? [el('span', { class: 'ob-tile__eyebrow', text: t('onboarding.nation') })] : []),
        el('span', { class: 'ob-tile__name', text: team.short_name }),
      ]),
      el('span', { class: 'ob-tile__check', 'aria-hidden': 'true', text: '✓' }),
    ]);
    button.setAttribute('aria-label', team.name);
    button.addEventListener('click', () => toggle(team));
    tiles.set(team.id, button);
    paintTiles(team.id);
    // Not bounced on arrival: only a tap makes a shirt bounce.
    button.querySelector('.shirt')?.classList.remove('is-bounce');
    return stagger(button, position);
  }

  // ---- the bar: what is picked so far, and the way on --------------------------------------

  function drawBar() {
    if (!bar) return;
    const show = picks.length > 0 && (step === 'continents' || step === 'countries' || step === 'teams');
    bar.hidden = !show;
    if (!show) {
      bar.replaceChildren();
      return;
    }
    const chips = picks.map((id) => {
      const team = data.teamsById.get(id);
      const chip = el('button', { type: 'button', class: 'ob-chip', 'aria-label': t('onboarding.remove', { team: team.name }) }, [
        createShirt(shirtOf(team), 24),
        el('span', { text: team.short_name }),
        el('span', { 'aria-hidden': 'true', text: '×' }),
      ]);
      chip.addEventListener('click', () => toggle(team));
      return el('li', {}, [chip]);
    });
    bar.replaceChildren(
      el('ul', { class: 'ob-bar__chips', 'aria-label': t('onboarding.chosen') }, chips),
      primary(translator.plural('onboarding.next', picks.length), () => go('services')),
    );
  }

  // ---- screens ---------------------------------------------------------------------------

  function welcomeScreen() {
    const sample = el('div', { class: 'ob-sample', 'aria-hidden': 'true' }, [
      el('div', { class: 'ob-sample__card' }, [
        el('p', { class: 'ob-sample__label', text: t('onboarding.sample.label') }),
        el('div', { class: 'ob-sample__teams' }, [
          createShirt({ primary: '#006437', secondary: '#FFFFFF' }, 48),
          el('p', { class: 'ob-sample__match' }, [
            el('span', { text: t('onboarding.sample.home') }),
            el('span', { class: 'ob-sample__time', text: t('onboarding.sample.time') }),
            el('span', { text: t('onboarding.sample.away') }),
          ]),
          createShirt({ primary: '#C52613', secondary: '#000000' }, 48),
        ]),
        el('p', { class: 'ob-sample__where' }, [
          el('span', { class: 'ob-sample__chip is-free', text: t('onboarding.sample.free') }),
          el('span', { class: 'ob-sample__chip', text: t('onboarding.sample.paid') }),
        ]),
      ]),
    ]);
    const heading = title(words(t('onboarding.welcome.title'), 2));
    return el('div', { class: 'ob__welcome' }, [
      el('div', { class: 'ob-brand' }, [
        el('span', { class: 'ob-brand__mark', 'aria-hidden': 'true', text: 'U' }),
        el('span', { class: 'ob-brand__name', text: t('app.name') }),
      ]),
      sample,
      el('div', { class: 'ob__welcome-text' }, [
        heading,
        lead(t('onboarding.welcome.lead')),
        primary(t('onboarding.welcome.start'), () => go('continents'), 'ob-button--cta'),
        link(t('onboarding.welcome.skip'), () => finish(false)),
        el('p', { class: 'ob__fine', text: t('onboarding.welcome.privacy') }),
      ]),
    ]);
  }

  function continentCard(group, position) {
    const count = group.countries.length;
    const button = el('button', { type: 'button', class: 'ob-tile ob-tile--continent' }, [
      el('span', { class: 'ob-shirts', 'aria-hidden': 'true' }, group.featured.map((team) => createShirt(shirtOf(team), 44))),
      el('span', { class: 'ob-tile__text' }, [
        el('span', { class: 'ob-tile__name', text: continentName(group.id) }),
        el('span', { class: 'ob-tile__sub', text: translator.plural(group.clubCount > 0 ? 'onboarding.countries' : 'onboarding.countriesNations', count) }),
      ]),
    ]);
    const chosenHere = picks.filter((id) => group.countries.some((c) => c.code === data.teamsById.get(id)?.country)).length;
    if (chosenHere > 0) {
      button.classList.add('is-picked');
      button.append(el('span', { class: 'ob-badge', text: String(chosenHere), 'aria-hidden': 'true' }));
    }
    button.setAttribute(
      'aria-label',
      [continentName(group.id), translator.plural('onboarding.countries', count)].join(', ') +
        (chosenHere > 0 ? `, ${translator.plural('onboarding.chosenCount', chosenHere)}` : ''),
    );
    button.addEventListener('click', () => {
      continent = group;
      viaSearch = false;
      go('countries');
    });
    return stagger(button, position);
  }

  function searchResults(text) {
    const results = [];
    for (const { continent: group, country: found } of searchCountries(catalog, text, nameOf)) {
      const row = el('button', { type: 'button', class: 'ob-row ob-row--result' }, [
        createShirt(found.shirt, 40),
        el('span', { class: 'ob-row__text' }, [
          el('span', { class: 'ob-row__name', text: nameOf(found.code) }),
          el('span', { class: 'ob-row__sub', text: t('onboarding.seeCountry') }),
        ]),
        el('span', { class: 'ob-row__go', 'aria-hidden': 'true', text: '›' }),
      ]);
      row.addEventListener('click', () => {
        continent = group;
        country = found;
        query = '';
        viaSearch = true;
        go('teams');
      });
      results.push(row);
    }
    for (const team of searchTeams(index, text, { limit: SEARCH_LIMIT })) {
      const row = el('button', { type: 'button', class: 'ob-row ob-row--result', 'aria-pressed': 'false' }, [
        createShirt(shirtOf(team), 40),
        el('span', { class: 'ob-row__text' }, [
          el('span', { class: 'ob-row__name', text: team.name }),
          el('span', { class: 'ob-row__sub', text: team.kind === 'national' ? t('onboarding.nation') : nameOf(team.country) }),
        ]),
        el('span', { class: 'ob-row__mark', 'aria-hidden': 'true' }),
      ]);
      row.classList.toggle('is-picked', picked(team.id));
      row.setAttribute('aria-pressed', String(picked(team.id)));
      row.addEventListener('click', () => {
        toggle(team);
        row.classList.toggle('is-picked', picked(team.id));
        row.setAttribute('aria-pressed', String(picked(team.id)));
      });
      results.push(row);
    }
    return results.slice(0, SEARCH_LIMIT + 3).map((row, position) => stagger(row, position));
  }

  function continentsScreen() {
    const results = el('div', { class: 'ob-results' });
    const grid = el('div', { class: 'ob-grid ob-grid--continents' }, catalog.continents.map(continentCard));
    const noResults = el('p', { class: 'ob-empty', hidden: '' });
    const input = el('input', {
      id: 'ob-search',
      type: 'search',
      autocomplete: 'off',
      maxlength: '60',
      placeholder: t('onboarding.search.placeholder'),
    });
    input.value = query;

    function refresh() {
      query = input.value;
      const text = query.trim();
      const found = text.length >= 2 ? searchResults(text) : [];
      results.replaceChildren(...found);
      grid.hidden = text.length >= 2;
      noResults.hidden = text.length < 2 || found.length > 0;
      noResults.textContent = noResults.hidden ? '' : t('onboarding.search.none', { query: text });
      clearTimeout(typingTimer);
      if (text.length >= 2) {
        typingTimer = setTimeout(() => {
          say(found.length > 0 ? translator.plural('onboarding.search.found', found.length) : t('onboarding.search.none', { query: text }));
        }, ANNOUNCE_AFTER_TYPING_MS);
      }
    }
    input.addEventListener('input', refresh);
    const field = el('div', { class: 'ob-search' }, [
      el('label', { for: 'ob-search', class: 'visually-hidden', text: t('onboarding.search.label') }),
      el('span', { class: 'ob-search__icon', 'aria-hidden': 'true' }),
      input,
    ]);
    const screen = [title(t('onboarding.continents.title')), lead(t('onboarding.continents.lead')), field, results, noResults, grid];
    queueMicrotask(refresh);
    return el('div', { class: 'ob__body' }, screen);
  }

  function countriesScreen() {
    const cards = continent.countries.map((entry, position) => {
      const clubs = entry.clubs.length;
      const chosenHere = picks.filter((id) => data.teamsById.get(id)?.country === entry.code).length;
      const sub = clubs > 0 ? translator.plural('onboarding.clubsAndNation', clubs) : t('onboarding.onlyNation');
      const button = el('button', { type: 'button', class: 'ob-tile' }, [
        createShirt(entry.shirt, 64),
        el('span', { class: 'ob-tile__text' }, [
          el('span', { class: 'ob-tile__name', text: nameOf(entry.code) }),
          el('span', { class: 'ob-tile__sub', text: sub }),
        ]),
      ]);
      button.setAttribute('aria-label', `${nameOf(entry.code)}, ${sub}${chosenHere > 0 ? `, ${translator.plural('onboarding.chosenCount', chosenHere)}` : ''}`);
      if (chosenHere > 0) {
        button.classList.add('is-picked');
        button.append(el('span', { class: 'ob-badge', text: String(chosenHere), 'aria-hidden': 'true' }));
      }
      button.addEventListener('click', () => {
        country = entry;
        go('teams');
      });
      return stagger(button, position);
    });
    return el('div', { class: 'ob__body' }, [
      el('p', { class: 'ob__eyebrow', text: t('onboarding.continentLabel') }),
      title(continentName(continent.id)),
      lead(t('onboarding.countriesLead')),
      el('div', { class: 'ob-grid ob-grid--three' }, cards),
    ]);
  }

  function teamsScreen() {
    const total = country.clubs.length;
    const parts = [
      el('p', { class: 'ob__eyebrow', text: continentName(continent.id) }),
      title(nameOf(country.code)),
      lead(total > 0 ? translator.plural('onboarding.teams.lead', total) : t('onboarding.teams.leadNation')),
    ];
    if (country.nation) parts.push(teamTile(country.nation, 0, { large: true }));
    if (total > 0) {
      parts.push(
        el('h3', { class: 'ob__section', text: t('onboarding.clubs') }),
        el('div', { class: 'ob-grid ob-grid--three' }, country.clubs.map((team, position) => teamTile(team, position + 1))),
      );
    }
    return el('div', { class: 'ob__body' }, parts);
  }

  function servicesScreen() {
    const rows = data.services.map((service, position) => {
      const id = `ob-service-${service.id}`;
      const names = service.includes_broadcasters.map((b) => data.broadcastersById.get(b)?.name ?? b);
      const box = el('input', { type: 'checkbox', id, value: service.id, class: 'ob-row__box' });
      box.checked = services.has(service.id);
      box.addEventListener('change', () => {
        if (box.checked) services.add(service.id);
        else services.delete(service.id);
        drawFinish();
      });
      const label = el('label', { for: id, class: 'ob-row' }, [
        el('span', { class: 'ob-row__text' }, [
          el('span', { class: 'ob-row__name', text: service.name }),
          el('span', { class: 'ob-row__sub', text: t('services.includes', { names: listFormat.format(names) }) }),
        ]),
        el('span', { class: 'ob-row__mark', 'aria-hidden': 'true' }),
      ]);
      return stagger(el('li', { class: 'ob-service' }, [box, label]), position);
    });
    return el('div', { class: 'ob__body' }, [
      title(t('onboarding.services.title')),
      lead(t('onboarding.services.lead')),
      el('ul', { class: 'ob-list' }, rows),
    ]);
  }

  let finishButton = null;
  function drawFinish() {
    if (!finishButton) return;
    finishButton.textContent =
      services.size === 0 ? t('onboarding.services.finish') : translator.plural('onboarding.services.finishWith', services.size);
  }

  function servicesBar() {
    finishButton = primary('', () => finish(true));
    const wrapper = el('div', { class: 'ob-bar__services' }, [finishButton, link(t('onboarding.services.skip'), () => finish(true))]);
    drawFinish();
    return wrapper;
  }

  // ---- the frame: back, progress, skip ---------------------------------------------------

  function header() {
    const number = FIRST_STEP_OF[step];
    const back = el('button', { type: 'button', class: 'ob-icon-button', 'aria-label': t('onboarding.back') }, [
      el('span', { class: 'ob-icon-button__arrow', 'aria-hidden': 'true' }),
    ]);
    back.addEventListener('click', () => go(previous(), 'back'));
    const progress = el('div', { class: 'ob-progress', role: 'img', 'aria-label': t('onboarding.progress', { step: number, total: 2 }) }, [
      el('span', { class: number >= 1 ? 'is-on' : '' }),
      el('span', { class: number >= 2 ? 'is-on' : '' }),
    ]);
    return el('div', { class: 'ob__top' }, [
      back,
      progress,
      link(t('onboarding.skip'), () => finish(false)),
    ]);
  }

  function previous() {
    if (step === 'teams') return viaSearch ? 'continents' : 'countries';
    if (step === 'countries') return 'continents';
    if (step === 'services') return 'teams';
    return 'welcome';
  }

  // ---- the flow ---------------------------------------------------------------------------

  function draw() {
    tiles.clear();
    finishButton = null;
    const builders = { welcome: welcomeScreen, continents: continentsScreen, countries: countriesScreen, teams: teamsScreen, services: servicesScreen };
    const screen = el('div', { class: `ob__screen ob__screen--${step} is-${direction}` }, [builders[step]()]);
    bar = el('div', { class: 'ob-bar', hidden: '' });
    const frame = [];
    if (step !== 'welcome') frame.push(header());
    frame.push(screen);
    frame.push(bar);
    if (step === 'services') {
      bar.hidden = false;
      bar.append(servicesBar());
    }
    stage.replaceChildren(...frame);
    if (step !== 'services') drawBar();
    const heading = stage.querySelector('.ob__title');
    heading?.focus({ preventScroll: true });
    stage.querySelector('.ob__screen')?.scrollTo?.(0, 0);
  }

  function go(next, how = 'forward') {
    step = next;
    direction = how === 'back' ? 'back' : 'forward';
    draw();
  }

  function leave() {
    clearTimeout(typingTimer);
    root.hidden = true;
    stage.replaceChildren();
    for (const element of outside) element.inert = false;
    document.documentElement.classList.remove('ob-open');
    opener?.focus?.({ preventScroll: true });
    opener = null;
  }

  function finish(apply) {
    preferences.markOnboarded();
    if (apply) {
      preferences.setServices([...services]);
      preferences.setTeams(picks);
    }
    leave();
    document.getElementById('main')?.focus({ preventScroll: true });
  }

  root.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      finish(false);
    }
  });

  return {
    /**
     * Show the flow. `from` is "welcome" for a new visitor, or "continents" to change the choices:
     * the teams and services already chosen are then ticked.
     */
    open({ from = 'welcome' } = {}) {
      const chosen = preferences.get();
      picks = from === 'welcome' ? [] : chosen.teams.filter((id) => data.teamsById.has(id));
      services = new Set(from === 'welcome' ? [] : chosen.services.filter((id) => data.servicesById.has(id)));
      query = '';
      continent = null;
      country = null;
      opener = document.activeElement;
      for (const element of outside) element.inert = true;
      document.documentElement.classList.add('ob-open');
      root.hidden = false;
      go(from);
    },
    isOpen: () => !root.hidden,
  };
}
