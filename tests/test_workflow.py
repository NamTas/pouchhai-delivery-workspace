import csv
import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import app


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'reviews.sqlite3'
        self.orders = app.load_orders()
        app.initialize(self.db, self.orders)
        self.id = next(o['order_id'] for o in self.orders if o['exception'] == 'Overdue in snapshot')

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, **kwargs):
        return dict(status='In review', owner='Support desk', priority='Normal', note='Reviewed the historical evidence.', version=0, **kwargs)

    def test_source_integrity_and_counts(self):
        manifest = json.loads((app.ROOT / 'data/provenance.json').read_text())
        self.assertEqual(hashlib.sha256(app.DATA.read_bytes()).hexdigest(), manifest['subset_sha256'])
        self.assertEqual(len(self.orders), 120)
        self.assertEqual(len({o['order_id'] for o in self.orders}), 120)
        self.assertEqual(sum(o['exception'] == 'Overdue in snapshot' for o in self.orders), 40)
        self.assertEqual(sum(o['exception'] == 'Delivered late' for o in self.orders), 60)
        for order in self.orders:
            self.assertLessEqual(order['purchased_at'], order['as_of'])
            for field in ['carrier_at', 'delivered_at']:
                self.assertTrue(not order[field] or order[field] <= order['as_of'])

    def test_only_exceptions_have_seeded_reviews(self):
        rows = app.list_orders(self.db)
        self.assertEqual(sum(bool(o['review']) for o in rows), 100)
        self.assertTrue(all(o['review'] is None for o in rows if o['exception'] == 'On time'))

    def test_initialization_does_not_reset_saved_records(self):
        app.update_review(self.id, self.payload(), self.db)
        app.initialize(self.db)
        row = next(r for r in app.list_orders(self.db) if r['order_id'] == self.id)
        self.assertEqual(row['review']['version'], 1)

    def test_valid_transition_persists_and_audits(self):
        result = app.update_review(self.id, self.payload(), self.db)
        self.assertEqual(result['status'], 'In review')
        self.assertEqual(result['version'], 1)
        events = app.events_for(self.id, self.db)
        self.assertEqual(len(events), 1)
        self.assertEqual(json.loads(events[0]['before_json'])['status'], 'New')
        self.assertEqual(events[0]['note'], self.payload()['note'])

    def test_new_cannot_skip_review(self):
        payload = self.payload(); payload['status'] = 'Resolved'; payload['resolution'] = app.REASONS[0]
        with self.assertRaises(app.ReviewError): app.update_review(self.id, payload, self.db)
        self.assertEqual(app.events_for(self.id, self.db), [])

    def test_owner_note_and_resolution_validation(self):
        for key, value in [('owner', 'Unassigned'), ('note', ''), ('note', 'x' * 1001), ('priority', 'Urgent'), ('version', True)]:
            payload = self.payload(); payload[key] = value
            with self.assertRaises(app.ReviewError): app.update_review(self.id, payload, self.db)
        app.update_review(self.id, self.payload(), self.db)
        payload = self.payload(); payload.update(status='Resolved', version=1)
        with self.assertRaises(app.ReviewError): app.update_review(self.id, payload, self.db)

    def test_close_and_reopen_clears_resolution(self):
        app.update_review(self.id, self.payload(), self.db)
        payload = self.payload(); payload.update(status='Resolved', version=1, resolution=app.REASONS[0])
        result = app.update_review(self.id, payload, self.db)
        self.assertEqual(result['resolution'], app.REASONS[0])
        payload.update(status='In review', version=2)
        result = app.update_review(self.id, payload, self.db)
        self.assertEqual(result['resolution'], '')
        self.assertEqual(len(app.events_for(self.id, self.db)), 3)

    def test_stale_version_returns_conflict(self):
        app.update_review(self.id, self.payload(), self.db)
        with self.assertRaises(app.ReviewError) as caught: app.update_review(self.id, self.payload(), self.db)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(len(app.events_for(self.id, self.db)), 1)

    def test_priority_sorting_is_operator_controlled(self):
        target = next(o['order_id'] for o in self.orders if o['exception'] == 'Delivered late')
        payload = self.payload(); payload['priority'] = 'High'
        app.update_review(target, payload, self.db)
        self.assertEqual(app.list_orders(self.db)[0]['order_id'], target)

    def test_export_escapes_formula_and_keeps_source_immutable(self):
        original = app.DATA.read_bytes()
        payload = self.payload(); payload['note'] = '=HYPERLINK("example")'
        app.update_review(self.id, payload, self.db)
        export = app.export_csv(self.db).decode('utf-8-sig')
        rows = list(csv.DictReader(export.splitlines()))
        row = next(row for row in rows if row['order_id'] == self.id)
        self.assertTrue(row['latest_note'].startswith("'="))
        self.assertEqual(app.DATA.read_bytes(), original)

    def test_ontime_has_no_review_endpoint(self):
        target = next(o['order_id'] for o in self.orders if o['exception'] == 'On time')
        with self.assertRaises(app.ReviewError) as caught: app.update_review(target, self.payload(), self.db)
        self.assertEqual(caught.exception.status, 404)

    def test_http_endpoints_and_request_boundary(self):
        server = app.make_server(0, self.db)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urllib.request.urlopen(base + '/api/orders?workspace=demo') as response:
                self.assertEqual(len(json.load(response)['orders']), 120)
            with urllib.request.urlopen(base + '/') as response:
                self.assertIn('Content-Security-Policy', response.headers)
                self.assertIn(b'Pouchhai', response.read())
            payload = self.payload(); payload['order_id'] = self.id
            for headers, body, status in [({}, payload, 403), ({'X-Review-Client':'pouchhai','Origin':'http://evil.example'}, payload, 403), ({'X-Review-Client':'pouchhai'}, [], 400)]:
                request = urllib.request.Request(base + '/api/review?workspace=demo', data=json.dumps(body).encode(), headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
                self.assertEqual(caught.exception.code, status)
            request = urllib.request.Request(base + '/api/review?workspace=demo', data=json.dumps(payload).encode(), headers={'X-Review-Client':'pouchhai','Content-Type':'application/json'})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(json.load(response)['review']['version'], 1)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
