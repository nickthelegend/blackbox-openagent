"""Check negative-case error classification without running Chrome."""

import json
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("row,path", [(22, "/empty/data/index.json"), (23, "/missing/data/slip_grip-000/run.json")])
def test_missing_data_error_allowlist(row, path):
    root = Path(__file__).resolve().parent.parent
    # Exercise the same JS classifier used by the later browser audit.
    result = subprocess.run(
        ["node", "-e", """
const assert = require('node:assert/strict');
const {expectedMissingResponse, expectedMissingConsole} = require('./audit/scripts/expected-errors.cjs');
const [row, path] = JSON.parse(process.argv[1]);
const origin = 'http://127.0.0.1:8731';
const response = {status: 404, url: origin + path};
const error = {
  type: 'error',
  text: 'Failed to load resource: the server responded with a status of 404 (File not found)',
  location: {url: response.url},
};
assert.equal(expectedMissingResponse(row, origin, response), true);
assert.equal(expectedMissingConsole(row, origin, error), true);
for (const url of [origin + '/favicon.ico', origin + '/empty/data/other.json', 'https://other.test' + path]) {
  assert.equal(expectedMissingResponse(row, origin, {...response, url}), false);
  assert.equal(expectedMissingConsole(row, origin, {...error, location: {url}}), false);
}
assert.equal(expectedMissingResponse(row, origin, {...response, status: 500}), false);
assert.equal(expectedMissingConsole(row, origin, {...error, text: 'Uncaught TypeError'}), false);
assert.equal(expectedMissingConsole(row, origin, {...error, text: 'net::ERR_CONNECTION_REFUSED'}), false);
assert.equal(expectedMissingConsole(row, origin, {...error, location: {}}), false);
assert.equal(expectedMissingResponse(1, origin, response), false);
assert.equal(expectedMissingConsole(1, origin, error), false);
""", json.dumps([row, path])],
        cwd=root, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
