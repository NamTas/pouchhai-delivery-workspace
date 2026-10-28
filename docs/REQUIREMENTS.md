# Requirements and acceptance criteria

## R1 — Own orders

A user can create an order with ID, city, order date and expected delivery date. Optional area, dispatch date, delivery date and source reference are supported.

Acceptance: required fields and real calendar dates are validated on the server. Future order/actual-event dates and dates before purchase are rejected. Dispatch cannot be after delivery. Duplicate IDs do not overwrite records. My orders initially contains zero rows.

## R2 — CSV ingestion

A user can download a blank template, preview a UTF-8 CSV and import it.

Acceptance: 500-row/1 MB limit; unique IDs; invalid rows are identified before writing. The final import revalidates and commits all records atomically or none. Preview never writes. Existing records must be edited individually.

## R3 — Current-date delivery view

A user can inspect all orders or follow-ups, search/filter and paginate.

Acceptance: calculations use current Bangladesh date (UTC+6). Delivered on the promised date is on time. An undelivered order promised today is On schedule; tomorrow it is Overdue by one day. Actual delivery freezes the delay at the delivered date. A read/refresh can create a newly overdue follow-up after a date rollover.

## R4 — Evidence corrections

A user can open an order and update its source fields.

Acceptance: ID is immutable during editing. A source change needs a reason and the current source version. Before/after values and UTC save time are stored. Source changes invalidate older follow-up versions, preventing closure based on stale evidence. Recorded facts are not changed by follow-up status changes.

## R5 — Accountable follow-up

A user can assign an owner and priority, add a note, progress and resolve/reopen a follow-up.

Acceptance: New → In review; In review ↔ Waiting for partner; In review/Waiting → Resolved; Resolved → In review. Same-state saves with a new note are allowed. Progress needs an owner; notes are 3–1,000 characters; closure needs a listed reason. Reopening clears the active resolution and retains history. Source-date changes do not auto-close follow-ups.

## R6 — Persistence and separation

A user can refresh/restart and export current records.

Acceptance: data remains in SQLite; stale writes return a conflict. Live and demo orders, decisions and histories remain separate even when identifiers match. Demo cannot accept source edits/imports. Own records and follow-up summaries can be exported. Full history backup is the stopped application's SQLite file.

## R7 — Readable, neutral interface

The interface must support daily use without employer-specific branding or application copy.

Acceptance: normal body text is 15px, table text 13px, control text 13–14px and secondary operational labels at least 12px. Small navigation/eyebrow labels may be smaller. Native dates and optional fields are labelled. Desktop and narrow-mobile layouts have no root-page horizontal overflow; wide tables scroll internally. Save feedback relates to the current request. Font and scripts work offline.

## Freshness and boundaries

The UI polls local saved records every 30 seconds and offers manual Refresh. This is not external courier tracking. Network failure shows a stale-data notice. Local changes and user-provided source references are not independently authenticated by this application.
