// Writing an iCalendar file (RFC 5545), the format Google Calendar, Apple Calendar and the rest
// import (FR-28). Pure: events in, text out. Everything that comes from data goes through
// escapeText(), so a name can never end a property and start another one.

const CRLF = '\r\n';
/** A line may be at most 75 octets (bytes), the line break not counted. */
const MAX_OCTETS = 75;
/** How long an event lasts when the data does not say: a match, a break, a little extra. */
export const DEFAULT_DURATION_MS = 2 * 60 * 60 * 1000;

const CONTROL = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g;

const encoder = new TextEncoder();
const octets = (character) => encoder.encode(character).length;

/**
 * A value for a TEXT property: control characters become spaces, then backslash, semicolon and
 * comma are escaped and a line break becomes the two characters \n. The result has no line break
 * left in it, so nothing in it can be taken for another property.
 */
export function escapeText(value) {
  return String(value ?? '')
    .replace(/\r\n|\r/g, '\n')
    .replace(CONTROL, ' ')
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\n/g, '\\n');
}

/**
 * Fold a line to 75 octets: the rest goes on following lines that start with one space. A
 * character is never cut in two (accents take two or more octets).
 */
export function foldLine(line) {
  const lines = [];
  let current = '';
  let size = 0;
  for (const character of line) {
    const width = octets(character);
    // A continuation line begins with a space, which counts as one of its 75.
    const limit = lines.length === 0 ? MAX_OCTETS : MAX_OCTETS - 1;
    if (size + width > limit) {
      lines.push(current);
      current = '';
      size = 0;
    }
    current += character;
    size += width;
  }
  lines.push(current);
  return lines.map((part, position) => (position === 0 ? part : ` ${part}`)).join(CRLF);
}

/** An address for a URI property: printable ASCII only, so it cannot carry a line break or a space. */
export function cleanUri(value) {
  return String(value ?? '').replace(/[^!-~]/g, '');
}

/** "2026-11-03T22:00:00Z" as "20261103T220000Z". */
export function utcStamp(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw new RangeError(`Not a date: ${value}`);
  }
  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
}

function eventLines(event, stamp) {
  const start = new Date(event.start);
  const end = new Date(start.getTime() + (event.durationMs ?? DEFAULT_DURATION_MS));
  const lines = [
    'BEGIN:VEVENT',
    `UID:${escapeText(event.uid)}`,
    `DTSTAMP:${stamp}`,
    `DTSTART:${utcStamp(start)}`,
    `DTEND:${utcStamp(end)}`,
    `SUMMARY:${escapeText(event.summary)}`,
  ];
  if (event.description) lines.push(`DESCRIPTION:${escapeText(event.description)}`);
  if (event.url) lines.push(`URL:${cleanUri(event.url)}`);
  lines.push('STATUS:CONFIRMED', 'TRANSP:TRANSPARENT', 'END:VEVENT');
  return lines;
}

/**
 * A calendar with these events.
 *
 * @param events  {uid, start (ISO, UTC), summary, description?, url?, durationMs?}
 * @param name    shown by calendars that import the file as a calendar of its own
 * @param now     the moment of writing (DTSTAMP), a Date
 */
export function buildCalendar(events, { name, now }) {
  const stamp = utcStamp(now);
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Ubi Ludus//Onde assistir futebol//PT-BR',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    `X-WR-CALNAME:${escapeText(name)}`,
    ...events.flatMap((event) => eventLines(event, stamp)),
    'END:VCALENDAR',
  ];
  return lines.map(foldLine).join(CRLF) + CRLF;
}
