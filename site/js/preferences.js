// The visitor's choices: the teams they follow, the services they have and whether to hide what
// they cannot watch (PRD FR-22, FR-25).
//
// They are saved in this browser's localStorage and nowhere else. Nothing here, or anywhere in the
// site, sends them over the network. This is the only module that touches storage.
//
// Storage can be missing or refuse to work (private modes, blocked site data, a full disk). The
// site must work then too, so every access is guarded and the choices fall back to memory for the
// visit; isPersistent() says which of the two is happening.

export const STORAGE_KEY = 'ubi-ludus:preferences';
/** Set once the visitor has seen the first-run flow (finished or skipped), so it is not shown again. */
export const ONBOARDED_KEY = 'ubi-ludus:onboarded';
export const VERSION = 1;
export const MAX_IDS = 200;

const ID = /^[a-z0-9]+(-[a-z0-9]+)*$/;

/** Keep only well-formed ids, once each, at most MAX_IDS. Anything else is dropped. */
export function cleanIds(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  const seen = new Set();
  for (const item of value) {
    if (typeof item === 'string' && item.length <= 80 && ID.test(item)) {
      seen.add(item);
    }
    if (seen.size >= MAX_IDS) {
      break;
    }
  }
  return [...seen];
}

/** Keep only the ids that exist in the data, so a stale or hand-edited value cannot reach the page. */
export function restrictTo(preferences, { teams, services }) {
  return {
    teams: preferences.teams.filter((id) => teams.has(id)),
    services: preferences.services.filter((id) => services.has(id)),
    onlyWatchable: preferences.onlyWatchable,
  };
}

function parse(text) {
  let stored;
  try {
    stored = JSON.parse(text);
  } catch {
    return null;
  }
  if (stored === null || typeof stored !== 'object' || stored.version !== VERSION) {
    return null;
  }
  return {
    teams: cleanIds(stored.teams),
    services: cleanIds(stored.services),
    onlyWatchable: stored.onlyWatchable === true,
  };
}

/**
 * @param getStorage returns the storage object; it may throw, as a browser does when site data is
 *   blocked. Tests pass a fake.
 */
export function createPreferences(getStorage = () => globalThis.localStorage) {
  const listeners = new Set();
  let persistent = true;
  let state = { teams: [], services: [], onlyWatchable: false };
  let onboarded = false;

  function storage() {
    try {
      const found = getStorage();
      if (found) {
        return found;
      }
    } catch {
      // Access itself can throw (SecurityError). Handled below, like a missing storage.
    }
    persistent = false;
    return null;
  }

  function load() {
    const store = storage();
    if (!store) {
      return;
    }
    try {
      const text = store.getItem(STORAGE_KEY);
      const stored = text === null ? null : parse(text);
      if (stored) {
        state = stored;
      }
      onboarded = store.getItem(ONBOARDED_KEY) === '1';
    } catch {
      persistent = false;
    }
  }

  function save() {
    const store = storage();
    if (!store) {
      return;
    }
    try {
      store.setItem(STORAGE_KEY, JSON.stringify({ version: VERSION, ...state }));
      persistent = true;
    } catch {
      persistent = false; // full, or refused: the choice still holds for this visit
    }
  }

  function changed() {
    for (const listener of listeners) {
      listener(get());
    }
  }

  function get() {
    return { teams: [...state.teams], services: [...state.services], onlyWatchable: state.onlyWatchable };
  }

  load();

  return {
    get,
    setTeams(ids) {
      state = { ...state, teams: cleanIds(ids) };
      save();
      changed();
    },
    setServices(ids) {
      state = { ...state, services: cleanIds(ids) };
      save();
      changed();
    },
    /** Hide the matches the visitor has no way to watch ("only what I can watch"). */
    setOnlyWatchable(value) {
      state = { ...state, onlyWatchable: value === true };
      save();
      changed();
    },
    /**
     * Take these choices for this visit only, without saving them (a shared link, FR-29). Fields
     * left out keep their value. The next change the visitor makes saves what is then in memory.
     */
    adopt({ teams, services, onlyWatchable }) {
      state = {
        teams: teams ? cleanIds(teams) : state.teams,
        services: services ? cleanIds(services) : state.services,
        onlyWatchable: typeof onlyWatchable === 'boolean' ? onlyWatchable : state.onlyWatchable,
      };
    },
    /** Whether the visitor has already seen the first-run flow. */
    isOnboarded() {
      return onboarded;
    },
    /** Remember that the first-run flow was seen (finished or skipped). */
    markOnboarded() {
      onboarded = true;
      const store = storage();
      if (store) {
        try {
          store.setItem(ONBOARDED_KEY, '1');
        } catch {
          persistent = false; // it still holds for this visit
        }
      }
    },
    /** Forget everything: the saved copy and the one in memory ("Reset my data"). */
    reset() {
      state = { teams: [], services: [], onlyWatchable: false };
      onboarded = false;
      const store = storage();
      if (store) {
        try {
          store.removeItem(STORAGE_KEY);
          store.removeItem(ONBOARDED_KEY);
        } catch {
          persistent = false;
        }
      }
      changed();
    },
    /** Call listener with the new choices after every change. Returns a function that stops it. */
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    /** False when the choices are only in memory because storage is missing or refused. */
    isPersistent() {
      return persistent;
    },
  };
}
