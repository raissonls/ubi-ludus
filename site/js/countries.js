// Where each country is and what it is called, for the first-run flow (continent, country, team).

import { LOCALE } from './i18n.js';

const regionNames = new Intl.DisplayNames([LOCALE], { type: 'region' });

/** The name of a country in the page's language. England is a part of a country: the strings file names it. */
export function countryName(code, translator) {
  if (code.includes('-')) {
    return translator.t(['countries', code].join('.'));
  }
  try {
    return regionNames.of(code) ?? code;
  } catch {
    return code;
  }
}

/**
 * The six parts of the world and the countries in each (ISO codes, GB-ENG for England). A country
 * is shown only when the published data has a team from it, so this list can be longer than what
 * is on screen; a new country needs no change here unless it is missing from the list.
 *
 * `featured` are the teams whose shirts decorate the continent's card, when they are published.
 */
export const CONTINENTS = [
  {
    id: 'south-america',
    countries: ['BR', 'AR', 'UY', 'CL', 'CO', 'PY', 'PE', 'EC', 'BO', 'VE'],
    featured: ['flamengo', 'palmeiras', 'argentina'],
  },
  {
    id: 'europe',
    countries: [
      'GB-ENG', 'ES', 'IT', 'DE', 'FR', 'PT', 'NL', 'BE', 'TR', 'GR', 'AT', 'CH', 'SE', 'NO',
      'DK', 'FI', 'IE', 'PL', 'CZ', 'SK', 'HU', 'HR', 'RS', 'RO', 'BG', 'UA', 'RU', 'AZ', 'GE',
    ],
    featured: ['real-madrid', 'liverpool', 'bayern-munchen'],
  },
  {
    id: 'north-america',
    countries: ['US', 'MX', 'CA', 'CR', 'PA', 'HN', 'JM'],
    featured: ['estados-unidos', 'mexico', 'canada'],
  },
  {
    id: 'africa',
    countries: ['MA', 'SN', 'NG', 'EG', 'ZA', 'GH', 'CM', 'DZ', 'TN', 'CI', 'ML'],
    featured: ['marrocos', 'senegal', 'nigeria'],
  },
  {
    id: 'asia',
    countries: ['JP', 'KR', 'SA', 'IR', 'QA', 'AE', 'CN', 'IN', 'UZ', 'IQ'],
    featured: ['japao', 'coreia-do-sul', 'arabia-saudita'],
  },
  {
    id: 'oceania',
    countries: ['AU', 'NZ'],
    featured: ['australia', 'nova-zelandia'],
  },
];
