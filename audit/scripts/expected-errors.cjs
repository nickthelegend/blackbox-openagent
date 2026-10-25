// Only the deliberately removed resource in each negative check is expected.
function expectedMissingResource(row, origin) {
  if (row === 22) return origin + '/empty/data/index.json';
  if (row === 23) return origin + '/missing/data/slip_grip-000/run.json';
  return null;
}

function expectedMissingResponse(row, origin, event) {
  return event.status === 404 && event.url === expectedMissingResource(row, origin);
}

function expectedMissingConsole(row, origin, event) {
  return event.type === 'error' &&
    event.text === 'Failed to load resource: the server responded with a status of 404 (File not found)' &&
    event.location?.url === expectedMissingResource(row, origin);
}

module.exports = { expectedMissingResponse, expectedMissingConsole };
