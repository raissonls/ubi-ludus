// "Live now" and the countdown to kickoff (FR-26). The data is published once a day, so a match
// can be on right now while the data still says "scheduled", or say "live" long after it ended.
// The clock settles it: the page works out where each match stands from its kickoff and the time
// now, and keeps doing so while it is open, without reloading.
//
// What the clock can claim is limited: it knows when a match was meant to start, not how it is
// going. So it says "Em andamento" for the hours after kickoff and "Provavelmente encerrado" once
// a match has run past any normal length, never a score or a minute of play.

/** A countdown is shown from this long before kickoff (the date is enough before that). */
export const COUNTDOWN_FROM_MS = 24 * 60 * 60 * 1000;
/** A match is taken to be on for this long after kickoff (90 minutes, a break, extra time). */
export const LIVE_WINDOW_MS = 3 * 60 * 60 * 1000;
/** Closer than this, the countdown says "in a moment" instead of a number of minutes. */
export const SOON_MS = 30 * 1000;
/** How often the page looks at the clock again. */
export const TICK_MS = 10 * 1000;

const OPEN = new Set(['scheduled', 'rescheduled', 'live']);

/**
 * Where a match stands at `now`:
 *   null                               nothing to add (over, off, or still far away)
 *   {phase: 'countdown', msLeft}       kickoff is within a day
 *   {phase: 'live'}                    within the live window after kickoff
 *   {phase: 'over'}                    past the window, but the data still calls it open
 */
export function clockPhase({ status, kickoff }, now) {
  if (!OPEN.has(status)) return null;
  const at = Date.parse(kickoff);
  if (Number.isNaN(at)) return null;
  const elapsed = now.getTime() - at;
  if (elapsed < -COUNTDOWN_FROM_MS) return null;
  if (elapsed < 0) return { phase: 'countdown', msLeft: -elapsed };
  if (elapsed < LIVE_WINDOW_MS) return { phase: 'live' };
  return { phase: 'over' };
}

/** The words for a phase: which string and its values, or null for nothing to say. */
export function describePhase(found) {
  if (!found) return null;
  if (found.phase === 'live') return { key: 'clock.live', values: {} };
  if (found.phase === 'over') return { key: 'clock.over', values: {} };
  if (found.msLeft < SOON_MS) return { key: 'clock.soon', values: {} };
  // Whole minutes, rounded up, so it never says "0 min" before kickoff.
  const total = Math.ceil(found.msLeft / 60000);
  const hours = Math.floor(total / 60);
  const minutes = total % 60;
  if (hours === 0) return { key: 'clock.minutes', values: { minutes } };
  if (minutes === 0) return { key: 'clock.hours', values: { hours } };
  return { key: 'clock.hoursMinutes', values: { hours, minutes } };
}

/**
 * Keep the match cards under `root` in step with the clock. A card says what it needs through
 * `data-kickoff` and `data-state`; this adds a `data-phase` and a `.clock` line to it.
 *
 * @param clock      returns the current Date; tests pass one they control
 * @param isHidden   true while the tab is in the background (nobody is looking, so no work)
 */
export function createLiveClock({
  root,
  translator,
  clock = () => new Date(),
  isHidden = () => document.hidden,
}) {
  let timer = null;

  function clockLine(card) {
    let line = card.querySelector('.clock');
    if (!line) {
      line = document.createElement('span');
      line.className = 'clock';
      card.querySelector('.match-card__when').append(line);
    }
    return line;
  }

  function showPhase(card, found) {
    const words = describePhase(found);
    const phase = found?.phase ?? '';
    if (!words) {
      card.querySelector('.clock')?.remove();
      delete card.dataset.phase;
      return;
    }
    card.dataset.phase = phase;
    const line = clockLine(card);
    const text = translator.t(words.key, words.values);
    // A match the data already calls live says so itself while it is within the window.
    const redundant = phase === 'live' && card.dataset.state === 'live';
    line.hidden = redundant;
    line.className = `clock clock--${phase}`;
    line.replaceChildren();
    if (redundant) return;
    if (phase === 'live') {
      const dot = document.createElement('span');
      dot.className = 'live-dot';
      dot.setAttribute('aria-hidden', 'true');
      dot.textContent = '● ';
      line.append(dot);
    }
    line.append(document.createTextNode(text));
  }

  function update() {
    const now = clock();
    for (const card of root.querySelectorAll('.match-card[data-kickoff]')) {
      const found = clockPhase({ status: card.dataset.state, kickoff: card.dataset.kickoff }, now);
      showPhase(card, found);
    }
  }

  function onVisible() {
    if (!isHidden()) update(); // catch up at once when the tab comes back
  }

  return {
    update,
    /** Start looking at the clock every few seconds. Safe to call twice. */
    start() {
      if (timer !== null) return;
      timer = setInterval(() => {
        if (!isHidden()) update();
      }, TICK_MS);
      document.addEventListener('visibilitychange', onVisible);
    },
    stop() {
      clearInterval(timer);
      timer = null;
      document.removeEventListener('visibilitychange', onVisible);
    },
  };
}
