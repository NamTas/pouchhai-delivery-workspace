# Business scope

## User and problem

A small shop or delivery operations user has order dates in a ledger, spreadsheet or courier confirmation. They need a clear list of overdue orders and a way to record who is following up. A historical dashboard alone cannot support day-to-day work.

## Workflow

Add/import own orders → inspect current delivery evidence → update confirmed dates → review overdue/delivered-late records → assign a next action → document closure or reopen.

The tool does not replace a courier's tracking system. Source evidence must come from the user or a documented CSV export. A missing timestamp may be a stale record rather than a missing shipment.

## Useful scope

- Add a real order individually or import the documented CSV.
- Recalculate delay from the current Bangladesh date.
- Correct source dates with a reason and a version check.
- Assign follow-ups, record decisions, retain history and export.
- Keep historical demonstration data in a separate workspace.

## Proposed user validation

Use 10–20 records you are authorised to handle. Check imported IDs and dates against the source. Verify which orders should be overdue today, record a real confirmation, and confirm persistence after restarting. Ask a user to find a pending order and explain its next step without coaching.

These are evaluation tasks, not completed merchant-pilot results. No business savings or faster delivery has been measured.

## Constraints

Local use on one computer; no authentication or courier integration. Date-based rules do not model working days, time windows, cancellations, COD settlements, refunds or legal SLAs. The first version focuses on recording and reviewing confirmed delivery facts.
