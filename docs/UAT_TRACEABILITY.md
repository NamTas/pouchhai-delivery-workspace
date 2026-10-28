# Acceptance checks and traceability

| Requirement | Implementation | Automated checks |
|---|---|---|
| R1 own orders | `live.validate/save` and order form | required/date/duplicate tests; browser create order |
| R2 preview/import | `live.parse_import/import_csv` and import dialog | preview writes nothing; invalid batch and duplicates roll back; browser preview/import |
| R3 current date | `live.today/classify/orders` | current-day classification and simulated next-day rollover; browser current delay |
| R4 corrections | `live.save`, source versions/history | required correction note, stale source rejection, stale review after source update; browser delivery-date change |
| R5 follow-up | `app.update_review` | guarded transition, owner/note validation, closure/reopen; browser follow-up save |
| R6 persistence/separation | separate SQLite tables, exports | identical-ID isolation, exports, restart-safe seeding; browser demo switch and reload |
| R7 readability | CSS and neutral workspace UI | browser table-font check, mobile form/overflow and page-error checks; visual desktop/mobile inspection |

## Manual real-record trial

Prepared tasks for the actual user, not a completed external pilot:

1. Take 10 source records you are authorised to use. Record the source and date of capture.
2. Import them using the blank template. Compare IDs/count/dates with the source.
3. Check one future-due, one overdue and one delivered order against the current date.
4. Update an actual confirmed delivery and explain the correction in the note.
5. Assign and close a follow-up when justified by your evidence.
6. Restart the application, verify saved details and inspect the activity history.
7. Export and compare records; back up the database with the app stopped.
8. Record any mismatch and its expected behaviour before changing rules.

## Scope questions for future users

Are calendar dates sufficient? Which courier status export is available? Are cancellations or returns needed? Who owns follow-up decisions? Do any customers require working-day deadlines? These questions should be validated before adding integrations or broader rules.
