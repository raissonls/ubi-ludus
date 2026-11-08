// What the first-run flow shows, worked out from the published teams: the continents that have
// teams, the countries in each, and for each country its national team and its clubs. Pure
// functions (no DOM), so they are easy to test.

import { CONTINENTS } from './countries.js';
import { normalise } from './search.js';

/** A neutral shirt for a country whose national team is not published. */
export const NEUTRAL_SHIRT = { primary: '#9aa0ad', secondary: '#ffffff' };

/** The two colours a team's shirt is drawn with: its shirt, else its colours, else a neutral one. */
export function shirtOf(team) {
  return team?.shirt ?? team?.colors ?? NEUTRAL_SHIRT;
}

function byName(a, b) {
  return a.short_name.localeCompare(b.short_name, 'pt-BR');
}

/**
 * Group the teams by country and continent.
 *
 *   continents[]  { id, countries[], clubCount, featured[] } for each continent with a team
 *                 (a country the list of continents does not know is in a last group, "other")
 *   countries[]   { code, nation, clubs[], shirt } most clubs first, then by code
 *
 * `nation` is the national team (kind "national") or null; `clubs` are the others, by name.
 */
export function buildCatalog(teams) {
  const byCountry = new Map();
  for (const team of teams) {
    if (!byCountry.has(team.country)) {
      byCountry.set(team.country, { code: team.country, nation: null, clubs: [] });
    }
    const entry = byCountry.get(team.country);
    if (team.kind === 'national') {
      entry.nation = team;
    } else {
      entry.clubs.push(team);
    }
  }
  const byId = new Map(teams.map((team) => [team.id, team]));
  const placed = new Set();
  const groups = CONTINENTS.map((continent) => ({
    ...continent,
    countries: continent.countries.filter((code) => byCountry.has(code)),
  }));
  for (const group of groups) group.countries.forEach((code) => placed.add(code));
  // A country the list does not know still has to be reachable: it goes to a last group.
  const strangers = [...byCountry.keys()].filter((code) => !placed.has(code)).sort();
  if (strangers.length > 0) groups.push({ id: 'other', countries: strangers, featured: [] });

  const continents = [];
  for (const group of groups) {
    const countries = group.countries
      .map((code) => {
        const entry = byCountry.get(code);
        entry.clubs.sort(byName);
        return { ...entry, shirt: shirtOf(entry.nation ?? entry.clubs[0]) };
      })
      .sort((a, b) => b.clubs.length - a.clubs.length || a.code.localeCompare(b.code));
    if (countries.length === 0) continue;
    const featured = group.featured.map((id) => byId.get(id)).filter(Boolean);
    for (const country of countries) {
      if (featured.length >= 3) break;
      const team = country.nation ?? country.clubs[0];
      if (team && !featured.includes(team)) featured.push(team);
    }
    continents.push({
      id: group.id,
      countries,
      clubCount: countries.reduce((total, country) => total + country.clubs.length, 0),
      featured: featured.slice(0, 3),
    });
  }
  return { continents };
}

/** The countries whose name starts with what was typed (accents and case do not matter). */
export function searchCountries(catalog, query, nameOf) {
  const text = normalise(query);
  if (!text) return [];
  return catalog.continents
    .flatMap((continent) => continent.countries.map((country) => ({ continent, country })))
    .filter(({ country }) => normalise(nameOf(country.code)).startsWith(text));
}
