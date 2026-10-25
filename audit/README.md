# First full-plan run

Result: **36 PASS / 4 FAIL / 1 UNTESTED** across all 41 rows in `AUDIT.md`.

Failures:

- **BB-001:** first-load Chrome console error and unexpected HTTP 404 for `/favicon.ico`.
- **BB-022:** the missing-index error state renders the exact requested instructions. Its planned index 404 still generates a console error; an unexpected favicon 404 also occurs. Strict zero-console-error policy therefore fails the row.
- **BB-023:** the missing-run error state renders the exact requested instructions. Its planned run.json 404 generates a console error, failing the row under the same policy.
- **BB-024:** switching reels pauses playback, but collision initializes at 8.04 s instead of the required 0.00 s.

**BB-040 is UNTESTED:** needs BLACKBOX_LLM_API_KEY or NVIDIA_API_KEY. No live LLM calls were made. BB-041 uses only the user-authorized localhost unreachable-endpoint pytest test, which passed.

Chrome for Testing 156.0.8078.4 ran headless through Playwright. Main flows used 1280×800; BB-025 used 375×812. The app was started with `.venv/bin/python -m blackbox serve --port 8730`. The error scenarios used copies of `web/` on port 8731; only the index or run JSON in the corresponding copy was deleted. Repository recordings were preserved. Existing simulated recordings remained visibly labeled SIMULATED. No browser routes, HTTP responses, product data, or checks were mocked or stubbed.

Every UI/HTTP row has a JPEG, console log, network log, and assertion record. HTTP rows use real GET requests through the Chrome browser context's APIRequestContext; body artifacts are in `http/`. CLI rows have the actual command, exit code, stdout and stderr. The CLI simulation and tampering used a temporary directory, which was removed. API credentials were excluded from CLI subprocess environments and `BLACKBOX_BACKEND=rules` prevented environment-selected live calls.

BB-019's expected collision start was corrected before execution from 9.20 s to the recorded `failure_moment.t0` of 9.24 s. The rounded 9.2 s headline was preserved. No other product expectation was relaxed. BB-041's expected cell records the explicitly requested fallback regression test.

Two automation assertions were corrected by reviewing the same run's stored measurements and screenshots, without repeating any flow: BB-015's native nearest scrolling leaves the outer border at 800.078125 CSS px, rounding to physical pixel 800, while the complete document text is visible; BB-025's visible short labels compute to `block` because they are flex items, rather than `inline`. The expected cell requires visible short labels, not that computed display value. The raw observations and assessment explanations remain in each result JSON.

Chrome's automatic favicon loads produce console messages and server access entries but do not appear in Playwright's Page.response stream. The corresponding per-row network logs include those responses with explicit server-log provenance. Original console records and server access logs are retained.

The heavy slot was acquired in the foreground and released by an EXIT trap. Both owned server PIDs were killed and waited for; their ports no longer accepted connections. Chrome closed normally. See `lifecycle.log` and `summary.json`. Evidence totals about 4.7 MB, with every screenshot under 200 KB.

Product code was kept unchanged. This report records remaining failures; fixes require a separate authorized product change. `scripts/` preserves the execution and assessment code; Node modules and browser caches live outside the repository. No deploy or push was performed.
