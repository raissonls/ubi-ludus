// Competitions with a short data horizon (FR-34). For some competitions the free data plan only
// tells us about matches until tomorrow. The page must say so, so a list without those matches never
// looks like "there are none". Which competitions are short is decided by the pipeline from
// config/competitions.yml (a competition whose longest source reaches less than 14 days) and
// published as `coverage: "short"`; nothing here knows a competition by name.

/** Whether the data of this competition reaches only until tomorrow. */
export function isShortHorizon(competition) {
  return competition?.coverage === 'short';
}

/** The names of the short-horizon competitions with a match in these, in alphabetical order. */
export function shortCompetitionsIn(matches, data, extraIds = []) {
  const ids = new Set([...matches.map((match) => match.competition_id), ...extraIds]);
  const names = [];
  for (const id of ids) {
    const competition = data.competitionsById.get(id);
    if (isShortHorizon(competition)) names.push(competition.name);
  }
  return names.sort((a, b) => a.localeCompare(b, 'pt-BR'));
}

/** Whether the data has any competition with a short horizon at all. */
export function hasShortCompetitions(data) {
  return [...data.competitionsById.values()].some(isShortHorizon);
}

/** Names as one phrase: "A, B e C". */
export function joinNames(names, locale = 'pt-BR') {
  return new Intl.ListFormat(locale, { style: 'long', type: 'conjunction' }).format(names);
}

/**
 * What the notice below a list of matches says, or null for nothing.
 *
 * @param shown        the matches drawn
 * @param selectedId   the competition the visitor filtered on, if any
 * @returns {{key: string, values: object, count: number}|null}  a string key of horizon.* in pt-BR.json
 */
export function describeHorizonNotice({ shown, data, selectedId = '' }) {
  const names = shortCompetitionsIn(shown, data, selectedId ? [selectedId] : []);
  if (names.length > 0) {
    return {
      key: 'horizon.some',
      count: names.length,
      values: { competitions: joinNames(names) },
    };
  }
  // Nothing shown, no competition chosen and some competitions only reach until tomorrow: the
  // list may be empty only because of that, so say it.
  if (shown.length === 0 && !selectedId && hasShortCompetitions(data)) {
    return { key: 'horizon.empty', count: 0, values: {} };
  }
  return null;
}
