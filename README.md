# পৌঁছাই / Pouchhai

**A local delivery workspace for small shops and operations teams.** Add your order records, see which deliveries need attention, update delivery evidence and keep follow-ups in one place.

## Run

Python 3.10+; no pip packages, API key or internet connection needed.

```powershell
python app.py --open
```

If Windows uses `py`, run `py app.py --open`. Open http://127.0.0.1:8765 if the browser does not open automatically. Windows: `run_windows.bat`; macOS/Linux: `bash run_mac_linux.sh`. VS Code: open the extracted `pouchhai-live` folder, then Terminal → New Terminal. Stop with Ctrl+C. For a busy port: `python app.py --port 8766 --open`.

## Use your actual records

The app opens **My orders**, an empty workspace. It does not populate your workspace with invented sales or old sample orders.

1. Click **Add order**.
2. Enter an order ID, city, order date and expected delivery date from your ledger, order confirmation or consignment record.
3. Add dispatched/delivered dates only when known. Add a source reference if useful; customer names, phone numbers and full addresses are not required.
4. Open an order and choose **Update order / delivery** when confirmation arrives. Changes need a reason and retain a history.
5. Review overdue or delivered-late orders in the **Follow-up queue**. Assign an owner, record the next step and resolve or reopen as appropriate.

Orders expected today are not overdue. An undelivered order becomes overdue on the following Bangladesh calendar date. Delay uses calendar days, not courier working days or contractual SLA rules. Missing delivery data is a reason to verify the record, not proof that the shipment is lost.

## Import a CSV

Click **Import CSV → Download blank CSV template**, or use `data/import_template.csv`.

Columns:

```csv
order_id,city,area,order_date,expected_delivery_date,dispatched_date,delivered_date,source_reference
```

- Required: `order_id`, `city`, `order_date`, `expected_delivery_date`.
- Dates must be `YYYY-MM-DD`; optional actual dates can stay blank. UTF-8 CSV, including a BOM, is supported.
- Keep order IDs unique. Up to 500 records / 1 MB per import.
- Choose the file, click **Check file**, inspect the preview/errors, then **Import orders**.
- Import is all-or-nothing. Duplicate IDs, invalid dates or any invalid row prevent the entire batch being saved. Nothing is silently overwritten.
- Import adds new records. To correct an existing order, open that order and use **Update order / delivery**.

The blank template contains no example orders. Use the fields from records you are authorised to use. Extra CSV columns are ignored; map your source into the documented template first.

## Current-date updates, not courier integration

My orders recalculates delays using the current **Bangladesh date (UTC+6)**. The UI refreshes saved records every 30 seconds; Refresh updates immediately. Records added/changed in another local browser tab appear on refresh. Overnight date changes can create a follow-up for an order that has just become overdue.

**No courier API is connected.** Dispatch/delivery evidence comes from your entries or imported records. The app does not retrieve Pathao/Steadfast/RedX tracking events, contact customers, or mark an actual courier shipment delivered. Automatic external tracking would require a specific provider's authorised API and credentials.

Updating delivery facts does not silently close a follow-up; review the evidence and close it with a reason. If previously closed work needs attention, reopen it as In review.

## What is saved

Your source records and review decisions are stored in `data/reviews.sqlite3`, including source corrections and before/after follow-up history. Refreshing or restarting retains them. Version checks prevent stale tabs from silently overwriting newer source records or review decisions.

Export orders and follow-up summaries from the footer. Spreadsheet formula-like strings are escaped in CSV output. This can add an apostrophe to unusual text beginning with `=`, `+`, `-` or `@`; CSV is a human-readable export, not a lossless database backup.

**Full backup:** stop the app and copy `data/reviews.sqlite3` somewhere safe. Restoring that file with the app stopped retains the complete workspace and history. Do not replace a database while the app is running.

Local, single-user use only. There is no login, cloud backup or production role separation. Keep the app bound to localhost as provided.

## Separate demo dataset

Select **Demo data · Olist** to inspect the historical 120-order Brazilian sample. It uses a fixed August 2018 snapshot; its follow-ups are stored separately and never mix with My orders. Add/import/source-edit actions are disabled in the demo. Switch back to My orders for your own data.

Demo source and license: Olist's [Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), CC BY-NC-SA 4.0. Exact source capture, transformations and hashes: `data/provenance.json`. Demo exception rates are not population performance estimates.

## Verification

```bash
python -m unittest discover -s tests -v
```

Tests use temporary databases and labelled test fixtures, not customer records. The test database is not shipped. Browser checks are optional developer tooling; see `docs/RELEASE_NOTES.md`.

No merchant pilot, live courier connection or measured reduction in delivery delays is claimed. Practical validation should use your own source records and compare dates/statuses with those sources.

## Files

- `app.py`: local API and follow-up workflow.
- `live.py`: own-order validation, current-date classification, CSV preview/import and source history.
- `web/`: responsive interface; readable text and offline Bangla font.
- `data/`: blank import template and separate Olist demo data.
- `docs/`: requirements, acceptance checks, business scope and release notes.
- `tests/`: backend and optional browser checks.

Application code: MIT. Olist demo data and bundled font have separate licenses; see `LICENSE.md`. Developed with AI assistance; no external organisation endorsement is implied.
