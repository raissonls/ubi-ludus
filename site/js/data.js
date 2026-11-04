// Loads the five published files (matches, teams, competitions, broadcasters, status) from the
// data/ folder next to the site. They are the same files the pipeline validated against its
// schemas, so this only checks what the page depends on: that each file is JSON, that its format
// version is one this code understands, and that the lists it reads are there.

/** The format version (the "1" of "1.0") this code can read. A higher one means the site is old. */
export const SUPPORTED_MAJOR = 1;

export const FILES = ['matches', 'teams', 'competitions', 'broadcasters', 'status'];

// What each file must hold, besides schema_version and generated_at.
const LISTS = {
  matches: ['matches'],
  teams: ['teams'],
  competitions: ['competitions'],
  broadcasters: ['broadcasters', 'services'],
  status: [],
};

/**
 * A file could not be loaded or is not what the page expects. `file` says which, and `kind` why:
 *   network  the file could not be reached (offline, DNS, a refused connection)
 *   http     the server answered, but not with the file
 *   invalid  the file arrived but is not what the page reads
 *   version  the file is in a newer format than this site knows (the site is the old one)
 */
export class DataError extends Error {
  constructor(file, message, kind = 'invalid', options) {
    super(`${file}.json: ${message}`, options);
    this.name = 'DataError';
    this.file = file;
    this.kind = kind;
  }
}

/** Check a parsed file is what the page reads. Returns it, or throws a DataError. */
export function validate(name, document) {
  if (document === null || typeof document !== 'object' || Array.isArray(document)) {
    throw new DataError(name, 'is not an object');
  }
  const major = Number.parseInt(String(document.schema_version).split('.')[0], 10);
  if (!Number.isInteger(major)) {
    throw new DataError(name, 'has no schema_version');
  }
  if (major !== SUPPORTED_MAJOR) {
    throw new DataError(
      name,
      `is in format ${document.schema_version}; this site reads ${SUPPORTED_MAJOR}.x`,
      'version',
    );
  }
  for (const list of LISTS[name]) {
    if (!Array.isArray(document[list])) {
      throw new DataError(name, `has no "${list}" list`);
    }
  }
  return document;
}

async function loadFile(name, baseUrl, fetchImpl) {
  const url = new URL(`${name}.json`, baseUrl);
  let response;
  try {
    // no-cache: ask the server whether the file changed (a cheap 304), so a day's update shows.
    response = await fetchImpl(url, { cache: 'no-cache' });
  } catch (error) {
    throw new DataError(name, 'could not be reached', 'network', { cause: error });
  }
  if (!response.ok) {
    throw new DataError(name, `the server answered HTTP ${response.status}`, 'http');
  }
  let document;
  try {
    document = await response.json();
  } catch (error) {
    throw new DataError(name, 'is not valid JSON', 'invalid', { cause: error });
  }
  return validate(name, document);
}

function index(records) {
  return new Map(records.map((record) => [record.id, record]));
}

/** Fetch and check the five files at once, as an object by name. Throws a DataError. */
export async function fetchDocuments(baseUrl, fetchImpl = fetch) {
  const loaded = await Promise.all(FILES.map((name) => loadFile(name, baseUrl, fetchImpl)));
  return Object.fromEntries(FILES.map((name, position) => [name, loaded[position]]));
}

/**
 * Load all five files at once. Throws a DataError naming the first file that failed.
 *
 * Returns the records, an index by id for each kind (for looking a team up from a match), and
 * the status document.
 */
export async function loadData(baseUrl, fetchImpl = fetch) {
  return buildData(await fetchDocuments(baseUrl, fetchImpl));
}

/** The records and indexes the page uses, from the five checked documents. */
export function buildData(documents) {
  const { matches, teams, competitions, broadcasters, status } = documents;
  return {
    matches: matches.matches,
    teams: teams.teams,
    competitions: competitions.competitions,
    broadcasters: broadcasters.broadcasters,
    services: broadcasters.services,
    status,
    teamsById: index(teams.teams),
    competitionsById: index(competitions.competitions),
    broadcastersById: index(broadcasters.broadcasters),
    servicesById: index(broadcasters.services),
  };
}
