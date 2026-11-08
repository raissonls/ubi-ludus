// Dates and times for the visitor, always in Brazil's time. The data is in UTC; it is converted
// only here, for display (PRD FR-06). The zone is the IANA name, never a fixed offset, so any
// daylight saving rule applies, past or future.

import { LOCALE } from './i18n.js';

export const TIME_ZONE = 'America/Sao_Paulo';

const formatters = {
  date: new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  }),
  dayMonth: new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    day: 'numeric',
    month: 'short',
  }),
  time: new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }),
  dateTime: new Intl.DateTimeFormat(LOCALE, {
    timeZone: TIME_ZONE,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }),
  dayKey: new Intl.DateTimeFormat('en-CA', {
    timeZone: TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }),
};

function toDate(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw new RangeError(`Not a date: ${value}`);
  }
  return date;
}

/** "sáb., 14 de nov." for a UTC instant (an ISO string or a Date). */
export function formatDate(value) {
  return formatters.date.format(toDate(value));
}

/** "14 de nov." for a UTC instant: short, for a small card. */
export function formatDayMonth(value) {
  return formatters.dayMonth.format(toDate(value));
}

/** "16:00". */
export function formatTime(value) {
  return formatters.time.format(toDate(value));
}

/** "sáb., 14 de nov., 16:00". */
export function formatDateTime(value) {
  return formatters.dateTime.format(toDate(value));
}

/** "2026-11-14": the calendar day in Brazil, for grouping matches by day. */
export function dayKey(value) {
  return formatters.dayKey.format(toDate(value));
}
