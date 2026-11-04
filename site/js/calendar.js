// "Add to calendar" (FR-28): one match, or every upcoming match of the teams the visitor follows.
// The file is written here, in the browser, from the data already on the page, and handed to the
// browser as a download. Nothing is sent anywhere, and nothing in the file says which teams the
// visitor follows.

import { buildCalendar } from './ics.js';
import { formatDateTime } from './format.js';
import { roundText } from './match-card.js';
import { describeMatch } from './match-model.js';
import { upcomingMatches } from './matches-preview.js';

/** The teams of a model as one text: "Palmeiras x Flamengo". */
function teamsOf(model, translator) {
  return [model.home, model.away]
    .map((side) => side.name ?? translator.t('matches.tbd'))
    .join(` ${translator.t('card.versus')} `);
}

/**
 * The event for one match. The description says where to watch exactly as the card does: the
 * broadcasters with how sure we are, or that it is not confirmed, never a guess (FR-13).
 */
export function describeEvent(model, { translator, url }) {
  const round = roundText(model.round, translator);
  const lines = [round ? `${model.competition} · ${round}` : model.competition];
  if (model.badges.length > 0) {
    const names = model.badges.map(
      (badge) => `${badge.name} (${translator.t(`card.badge.${badge.confidence}`)})`,
    );
    lines.push(`${translator.t('card.watch')}: ${names.join(', ')}.`);
    if (model.confidence !== 'confirmed') lines.push(translator.t('calendar.check'));
  } else {
    lines.push(translator.t('card.confidence.unknown'));
  }
  lines.push(translator.t('calendar.from', { when: formatDateTime(model.kickoff) }));
  return {
    uid: `${model.id}@ubi-ludus`,
    start: model.kickoff,
    summary: teamsOf(model, translator),
    description: lines.join('\n'),
    url,
  };
}

function fileName(text) {
  const slug = String(text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return `ubi-ludus-${slug || 'jogos'}.ics`;
}

/** Hand a text to the browser as a file to save. */
export function saveFile(name, text, type = 'text/calendar;charset=utf-8') {
  const address = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = address;
  link.download = name;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(address), 10_000);
}

/**
 * @param url    the address of the site, put in each event
 * @param save   (name, text) => void; tests pass their own
 */
export function createCalendar({
  data,
  translator,
  clock = () => new Date(),
  url = '',
  save = saveFile,
}) {
  const calendarOf = (matches, name) => {
    const events = matches.map((match) =>
      describeEvent(describeMatch(match, data), { translator, url }),
    );
    return buildCalendar(events, { name, now: clock() });
  };

  return {
    /** Save one match as a calendar file. */
    saveMatch(match) {
      const model = describeMatch(match, data);
      save(fileName(match.id), calendarOf([match], teamsOf(model, translator)));
    },

    /** The matches still to come (or on) of these teams, soonest first. */
    upcoming(teamIds) {
      return upcomingMatches(data.matches, teamIds, clock(), Infinity);
    },

    /** Save them all as one calendar file; returns how many there were. */
    saveFollowed(teamIds) {
      const matches = this.upcoming(teamIds);
      if (matches.length > 0) {
        save(fileName('meus-times'), calendarOf(matches, translator.t('calendar.name')));
      }
      return matches.length;
    },
  };
}
