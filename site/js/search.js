// Finding a team as the visitor types. Case, accents and punctuation do not matter ("sao paulo"
// finds "São Paulo", "barca" finds Barcelona through its alias), the same idea the pipeline uses
// to match provider spellings to our teams. Pure functions: no DOM, so they are easy to test.

const SPECIAL = { ø: 'o', æ: 'ae', œ: 'oe', ß: 'ss', đ: 'd', ł: 'l', ð: 'd', þ: 'th' };

/** Lower case, no accents, words separated by single spaces. */
export function normalise(text) {
  return String(text)
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[øæœßđłðþ]/g, (letter) => SPECIAL[letter])
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

/** Prepare the teams once, so each key press only compares text. */
export function buildIndex(teams) {
  return teams.map((team) => ({
    team,
    keys: [...new Set([team.name, team.short_name, ...(team.aliases ?? [])].map(normalise))].filter(Boolean),
  }));
}

// How well a key fits the query: lower is better, null is no fit.
function fit(key, query, tokens) {
  if (key === query) return 0;
  if (key.startsWith(query)) return 1;
  const words = key.split(' ');
  if (words.some((word) => word.startsWith(query))) return 2;
  if (tokens.length > 1 && tokens.every((token) => words.some((word) => word.startsWith(token)))) return 3;
  if (key.includes(query)) return 4;
  return null;
}

function byName(a, b) {
  return a.name.localeCompare(b.name, 'pt-BR');
}

/**
 * The teams that fit what was typed, best first, without those in `exclude` (ids), at most
 * `limit`. An empty query finds nothing.
 */
export function searchTeams(index, query, { exclude = new Set(), limit = 8 } = {}) {
  const text = normalise(query);
  if (!text) {
    return [];
  }
  const tokens = text.split(' ');
  const found = [];
  for (const { team, keys } of index) {
    if (exclude.has(team.id)) continue;
    const scores = keys.map((key) => fit(key, text, tokens)).filter((score) => score !== null);
    if (scores.length > 0) {
      found.push({ team, score: Math.min(...scores) });
    }
  }
  found.sort((a, b) => a.score - b.score || byName(a.team, b.team));
  return found.slice(0, limit).map((entry) => entry.team);
}

/**
 * What to offer before anything is typed: Brazilian teams first (this is a Brazilian site), then
 * the rest, each group by name.
 */
export function suggestTeams(index, { exclude = new Set(), limit = 8 } = {}) {
  return index
    .map((entry) => entry.team)
    .filter((team) => !exclude.has(team.id))
    .sort((a, b) => Number(b.country === 'BR') - Number(a.country === 'BR') || byName(a, b))
    .slice(0, limit);
}
