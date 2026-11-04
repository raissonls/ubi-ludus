import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  DEFAULT_DURATION_MS,
  buildCalendar,
  cleanUri,
  escapeText,
  foldLine,
  utcStamp,
} from '../js/ics.js';

const NOW = new Date('2026-11-02T12:30:45Z');
const event = (changes = {}) => ({
  uid: 'fx-1@ubi-ludus',
  start: '2026-11-03T22:00:00Z',
  summary: 'Palmeiras x Flamengo',
  description: 'Campeonato Brasileiro · Rodada 34',
  url: 'https://example.org/',
  ...changes,
});
const build = (events, name = 'Ubi Ludus') => buildCalendar(events, { name, now: NOW });
const octets = (text) => new TextEncoder().encode(text).length;
const unfold = (text) => text.replace(/\r\n /g, '');

test('text is escaped the way the format asks: backslash, semicolon, comma and line breaks', () => {
  assert.equal(escapeText('a\\b'), 'a\\\\b');
  assert.equal(escapeText('a;b,c'), 'a\\;b\\,c');
  assert.equal(escapeText('one\ntwo\r\nthree\rfour'), 'one\\ntwo\\nthree\\nfour');
  assert.equal(escapeText(null), '');
  assert.equal(escapeText(undefined), '');
});

test('control characters become spaces, so nothing odd reaches the file', () => {
  assert.equal(escapeText('a\u0000b\u0007c\u001bd\u007fe'), 'a b c d e');
  assert.equal(escapeText('tab\there'), 'tab\there'); // a tab is fine in text
});

test('a name cannot end a property and start another', () => {
  const hostile = 'Time\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:Falso';
  const file = build([event({ summary: hostile, description: hostile })]);
  const lines = file.split('\r\n');
  assert.equal(lines.filter((line) => line === 'BEGIN:VEVENT').length, 1);
  assert.equal(lines.filter((line) => line === 'END:VEVENT').length, 1);
  assert.equal(lines.filter((line) => line.startsWith('SUMMARY:')).length, 1);
  assert.equal(file.replace(/\r\n/g, '').includes('\n'), false); // no bare line break left
  assert.ok(unfold(file).includes('SUMMARY:Time\\nEND:VEVENT\\nBEGIN:VEVENT\\nSUMMARY:Falso'));
});

test('a long line is folded to 75 octets, and unfolds to the same text', () => {
  const line = `DESCRIPTION:${'palavra, '.repeat(40)}fim`;
  const folded = foldLine(line);
  const parts = folded.split('\r\n');
  assert.ok(parts.length > 1);
  parts.forEach((part, position) => {
    assert.ok(octets(part) <= 75, `${position}: ${octets(part)}`);
    if (position > 0) assert.ok(part.startsWith(' '));
  });
  assert.equal(unfold(folded), line);
});

test('folding counts octets, not characters, and never cuts a character in two', () => {
  const line = `SUMMARY:${'ação é ótima '.repeat(30)}😀😀😀`;
  const folded = foldLine(line);
  for (const part of folded.split('\r\n')) {
    assert.ok(octets(part) <= 75, part);
    assert.equal(part.includes('�'), false);
  }
  assert.equal(unfold(folded), line);
});

test('a short line is left alone', () => {
  assert.equal(foldLine('SUMMARY:Curto'), 'SUMMARY:Curto');
});

test('dates are written in UTC without separators', () => {
  assert.equal(utcStamp('2026-11-03T22:00:00Z'), '20261103T220000Z');
  assert.equal(utcStamp(new Date('2026-12-31T23:59:59.999Z')), '20261231T235959Z');
  assert.equal(utcStamp('2026-11-03T19:00:00-03:00'), '20261103T220000Z');
  assert.throws(() => utcStamp('not a date'), RangeError);
});

test('the file is a calendar with one event for each match, CRLF all through', () => {
  const file = build([event(), event({ uid: 'fx-2@ubi-ludus', summary: 'Outro' })]);
  assert.ok(file.startsWith('BEGIN:VCALENDAR\r\nVERSION:2.0\r\n'));
  assert.ok(file.endsWith('END:VCALENDAR\r\n'));
  assert.equal(file.replace(/\r\n/g, '').includes('\n'), false);
  assert.equal(file.replace(/\r\n/g, '').includes('\r'), false);
  const lines = file.split('\r\n');
  assert.equal(lines.filter((line) => line === 'BEGIN:VEVENT').length, 2);
  assert.equal(lines.filter((line) => line === 'END:VEVENT').length, 2);
  assert.ok(lines.includes('PRODID:-//Ubi Ludus//Onde assistir futebol//PT-BR'));
});

test('an event has what calendars need: UID, DTSTAMP, DTSTART, DTEND and SUMMARY', () => {
  const lines = build([event()]).split('\r\n');
  assert.ok(lines.includes('UID:fx-1@ubi-ludus'));
  assert.ok(lines.includes('DTSTAMP:20261102T123045Z')); // the moment of writing
  assert.ok(lines.includes('DTSTART:20261103T220000Z'));
  assert.ok(lines.includes('DTEND:20261104T000000Z'));
  assert.ok(lines.includes('SUMMARY:Palmeiras x Flamengo'));
  assert.ok(lines.includes('TRANSP:TRANSPARENT')); // a match does not make the visitor busy
  assert.equal(DEFAULT_DURATION_MS, 2 * 60 * 60 * 1000);
});

test('the length of an event can be given', () => {
  const lines = build([event({ durationMs: 90 * 60 * 1000 })]).split('\r\n');
  assert.ok(lines.includes('DTEND:20261103T233000Z'));
});

test('no line of the file is longer than 75 octets', () => {
  const long = 'Um jogo, com vírgulas; e ponto-e-vírgula, e acentuação demais. '.repeat(12);
  const file = build([event({ description: long, summary: long })], 'Nome, do; calendário '.repeat(8));
  for (const line of file.split('\r\n')) assert.ok(octets(line) <= 75, line);
});

test('an event without a description or address leaves those lines out', () => {
  const lines = build([event({ description: '', url: '' })]).split('\r\n');
  assert.equal(lines.some((line) => line.startsWith('DESCRIPTION')), false);
  assert.equal(lines.some((line) => line.startsWith('URL')), false);
});

test('the address is kept to printable ASCII, with no space or line break', () => {
  assert.equal(cleanUri('https://example.org/a b\r\nEND:VEVENT'), 'https://example.org/abEND:VEVENT');
  const lines = build([event({ url: 'https://x.org/\r\nBEGIN:VEVENT' })]).split('\r\n');
  assert.equal(lines.filter((line) => line === 'BEGIN:VEVENT').length, 1);
});

test('a start that is not a date is refused rather than written', () => {
  assert.throws(() => build([event({ start: 'soon' })]), RangeError);
});

test('an empty calendar is still a calendar', () => {
  const file = build([]);
  assert.ok(file.includes('BEGIN:VCALENDAR') && file.includes('END:VCALENDAR'));
  assert.equal(file.includes('BEGIN:VEVENT'), false);
});
