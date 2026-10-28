# Version 2.0 — own-order workspace

## Changes

- Increased operational text sizes and contrast. Body text 15px; table text 13px; most controls 13–14px; secondary data labels at least 12px. The bundled Bangla font remains available offline.
- Removed employer, job-application and personal-profile copy from the interface and documentation. The application is described as a general delivery workspace.
- My orders is the default and starts empty. Historical Olist data remains behind a separate Demo data selector.
- Added order creation and source-date updates with server validation, source versions, correction reasons and activity history.
- Added blank CSV template, UTF-8 decoding, file checking/preview and all-or-nothing import. Import never overwrites existing orders.
- Current Bangladesh date determines overdue status. Reads/refreshes can create a follow-up when an order crosses its due date overnight.
- The page polls saved local records every 30 seconds and offers manual Refresh. This is local record freshness, not a courier connection.
- Added own-order CSV export. Complete stopped-app SQLite backups preserve both source records and history.
- Preserved follow-up state validation, closure/reopen, audit history and stale-write protection. Source corrections also invalidate stale follow-up versions.

## Verification

28 backend unittest cases passed. The tests cover both the original historical-review rules and the new own-order workflow: empty initial state, data isolation, dates, duplicate IDs, current-day/next-day status, source changes, stale versions, preview/no-write, atomic batch import and export.

The Chromium browser acceptance run passed and covered empty My orders, neutral interface copy, own-order creation, readable table font, delivery-date update, current-delay counters, follow-up save/closure, literal note display, CSV preview/import, demo separation, reload persistence, exports, search, help, local automatic refresh and narrow-mobile forms/overflow. The separate-record write appeared through the real 30-second polling timer. Test records are temporary fixtures, not merchant data, and are not shipped.

Desktop and mobile layouts were visually inspected. Internal screenshots are not part of the delivered package.

No external merchant pilot, real courier API test or measured business saving is claimed. These are the next validation activities for actual users, separate from implementation tests.

## Remaining limits

- No external tracking integration or authenticated multi-user deployment.
- Calendar-date rules only; no cancellation, COD, return, refund or working-day SLA workflow.
- Users must confirm source accuracy. Source references are recorded but are not independently authenticated.
- Source edits do not automatically close a follow-up; reopening and closure remain deliberate decisions.
- CSV exports are spreadsheet-safe summaries, not lossless full-history backups. Back up the stopped app's database for complete recovery.
- Cross-browser and assistive-technology certification has not been completed.

## Run checks

```bash
python -m unittest discover -s tests -v
```

Optional browser tests need Node and Playwright, which are not app runtime dependencies:

```bash
npm install --no-save playwright
npx playwright install chromium
node tests/browser_smoke.cjs
```

The browser test waits for an actual 30-second local refresh. Use `PYTHON=py` where Windows uses the Python launcher; `PLAYWRIGHT_MODULE` and `CHROMIUM_EXECUTABLE` can point to an existing installation. All test databases are temporary.
