"""Pouchhai: a local delivery workspace (Python stdlib only)."""
import argparse
import csv
import io
import json
import re
import sqlite3
import threading
import webbrowser
import live
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'demo_orders.csv'
DB = ROOT / 'data' / 'reviews.sqlite3'
STATUSES = ('New', 'In review', 'Waiting for partner', 'Resolved')
OWNERS = ('Unassigned', 'Support desk', 'Operations desk', 'Quality review')
PRIORITIES = ('Normal', 'High', 'Low')
REASONS = ('Delivery confirmed', 'Customer updated', 'Follow-up complete', 'Data correction reviewed')
TRANSITIONS = {
    'New': {'New', 'In review'},
    'In review': {'In review', 'Waiting for partner', 'Resolved'},
    'Waiting for partner': {'Waiting for partner', 'In review', 'Resolved'},
    'Resolved': {'Resolved', 'In review'},
}


class ReviewError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def connect(db=DB):
    connection = sqlite3.connect(db, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def load_orders(path=DATA):
    with open(path, newline='', encoding='utf-8') as handle:
        orders = list(csv.DictReader(handle))
    for row in orders:
        row['delay_days'] = int(row['delay_days'])
    return orders


def initialize(db=DB, orders=None):
    orders = load_orders() if orders is None else orders
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    with connect(db) as connection:
        connection.executescript('''
        CREATE TABLE IF NOT EXISTS reviews (
          order_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'New',
          owner TEXT NOT NULL DEFAULT 'Unassigned', priority TEXT NOT NULL DEFAULT 'Normal',
          resolution TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL,
          timestamp TEXT NOT NULL, before_json TEXT NOT NULL,
          after_json TEXT NOT NULL, note TEXT NOT NULL);
        ''')
        live.initialize(connection)
        for order in orders:
            if order['exception'] != 'On time':
                connection.execute('INSERT OR IGNORE INTO reviews(order_id,updated_at) VALUES (?,?)', (order['order_id'], now()))


def list_orders(db=DB, orders=None):
    orders = load_orders() if orders is None else orders
    with connect(db) as connection:
        reviews = {r['order_id']: dict(r) for r in connection.execute('SELECT * FROM reviews')}
    out = [{**order, 'review': reviews.get(order['order_id'])} for order in orders]
    # Operator-assigned business priority first; older exceptions break ties.
    priority_rank = {'High': 0, 'Normal': 1, 'Low': 2}
    return sorted(out, key=lambda r: (r['review'] is None, r['review'] and r['review']['status'] == 'Resolved',
                                     priority_rank.get((r['review'] or {}).get('priority'), 3), -r['delay_days'], r['order_id']))


def update_review(order_id, payload, db=DB, workspace="demo"):
    review_table, event_table = review_tables(workspace)
    if not isinstance(payload, dict):
        raise ReviewError('Expected a JSON object.')
    status, owner, priority = (payload.get(key) for key in ('status', 'owner', 'priority'))
    note = payload.get('note', '')
    resolution = payload.get('resolution', '')
    version = payload.get('version')
    if status not in STATUSES or owner not in OWNERS or priority not in PRIORITIES:
        raise ReviewError('Choose a valid status, owner and priority.')
    if not isinstance(note, str) or not 3 <= len(note.strip()) <= 1000:
        raise ReviewError('Add a review note of 3–1,000 characters.')
    if type(version) is not int or version < 0:
        raise ReviewError('A valid record version is required. Reload this case.')
    if status != 'New' and owner == 'Unassigned':
        raise ReviewError('Assign an owner before progressing a case.')
    if status == 'Resolved' and resolution not in REASONS:
        raise ReviewError('Select a resolution reason before closing this review.')
    if status != 'Resolved':
        resolution = ''
    with connect(db) as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute(f'SELECT * FROM {review_table} WHERE order_id=?', (order_id,)).fetchone()
        if not row:
            raise ReviewError('No follow-up review exists for this order.', 404)
        before = dict(row)
        if before['version'] != version:
            raise ReviewError('This case changed in another tab. Reload the case before saving.', 409)
        if status not in TRANSITIONS[before['status']]:
            raise ReviewError(f"Move from {before['status']} to In review before choosing {status}.")
        timestamp = now()
        connection.execute(f'UPDATE {review_table} SET status=?,owner=?,priority=?,resolution=?,version=version+1,updated_at=? WHERE order_id=?',
                           (status, owner, priority, resolution, timestamp, order_id))
        after = dict(connection.execute(f'SELECT * FROM {review_table} WHERE order_id=?', (order_id,)).fetchone())
        connection.execute(f'INSERT INTO {event_table}(order_id,timestamp,before_json,after_json,note) VALUES (?,?,?,?,?)',
                           (order_id, timestamp, json.dumps(before), json.dumps(after), note.strip()))
    return after


def review_tables(workspace):
    if workspace == 'live':
        return 'live_reviews', 'live_events'
    if workspace == 'demo':
        return 'reviews', 'events'
    raise ReviewError('Unknown workspace.')


def orders_for(workspace, db=DB):
    review_tables(workspace)
    if workspace == 'live':
        return live.orders(db)
    return [{**row, 'country': 'Brazil'} for row in list_orders(db)]


def events_for(order_id, db=DB, workspace='demo'):
    _, table = review_tables(workspace)
    with connect(db) as connection:
        events = [{**dict(row), 'kind': 'review'} for row in connection.execute(f'SELECT * FROM {table} WHERE order_id=? ORDER BY id DESC', (order_id,))]
    if workspace == 'live':
        events += [{**row, 'kind': 'source'} for row in live.order_events(db, order_id)]
    return sorted(events, key=lambda event: (event['timestamp'], event['kind'], event['id']), reverse=True)


def csv_safe(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def export_csv(db=DB, workspace="demo"):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['order_id', 'city', 'state', 'snapshot', 'exception', 'delay_days', 'review_status', 'owner', 'priority', 'resolution', 'latest_note', 'version'])
    for order in orders_for(workspace, db):
        review = order['review']
        if review:
            events = [event for event in events_for(order['order_id'], db, workspace) if event['kind'] == 'review']
            values = [order['order_id'], order['city'], order['state'], order['as_of'], order['exception'], order['delay_days'],
                      review['status'], review['owner'], review['priority'], review['resolution'], events[0]['note'] if events else '', review['version']]
            writer.writerow([csv_safe(value) for value in values])
    return ('\ufeff' + buffer.getvalue()).encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, content, status=200, kind='application/json; charset=utf-8'):
        if not isinstance(content, bytes):
            content = json.dumps(content, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(content)

    def workspace(self):
        workspace = parse_qs(urlparse(self.path).query).get('workspace', ['live'])[0]
        review_tables(workspace)
        return workspace

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
            workspace = self.workspace()
            if parsed.path == '/api/orders':
                self.send({'orders': orders_for(workspace, self.server.db), 'today': live.today().isoformat()})
            elif parsed.path == '/api/meta':
                provenance = json.loads((ROOT / 'data/provenance.json').read_text())
                self.send({'provenance': provenance, 'statuses': STATUSES, 'owners': OWNERS, 'priorities': PRIORITIES, 'reasons': REASONS, 'today': live.today().isoformat(), 'timezone': 'Asia/Dhaka'})
            elif parsed.path == '/api/events':
                order_id = parse_qs(parsed.query).get('id', [''])[0]
                self.send({'events': events_for(order_id, self.server.db, workspace)})
            elif parsed.path == '/api/export':
                self.send(export_csv(self.server.db, workspace), kind='text/csv; charset=utf-8')
            elif parsed.path == '/api/export-orders':
                if workspace != 'live':
                    raise ReviewError('Source export is available for My orders only.')
                self.send(live.export_orders(self.server.db, csv_safe), kind='text/csv; charset=utf-8')
            elif parsed.path == '/api/template':
                self.send(live.template(), kind='text/csv; charset=utf-8')
            elif parsed.path in ('/', '/app.js', '/style.css', '/bengali.ttf'):
                file = ROOT / 'web' / ('index.html' if parsed.path == '/' else parsed.path[1:])
                kind = {'html': 'text/html', 'js': 'text/javascript', 'css': 'text/css', 'ttf': 'font/ttf'}[file.suffix[1:]]
                self.send(file.read_bytes(), kind=kind + '; charset=utf-8')
            else:
                self.send({'error': 'Not found'}, 404)
        except (ReviewError, live.DataError) as exc:
            self.send({'error': str(exc)}, exc.status)
        except sqlite3.Error:
            self.send({'error': 'Could not read the local workspace.'}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ('/api/review', '/api/order', '/api/import-preview', '/api/import'):
            return self.send({'error': 'Not found'}, 404)
        if self.headers.get('X-Review-Client') != 'pouchhai':
            return self.send({'error': 'Use the local workspace interface.'}, 403)
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            return self.send({'error': 'Cross-origin requests are not accepted.'}, 403)
        try:
            workspace = self.workspace()
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 2_100_000:
                raise ReviewError('Request must be smaller than 2 MB.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ReviewError('Expected a JSON object.')
            if path == '/api/review':
                order_id = payload.get('order_id', '')
                if not isinstance(order_id, str) or not 1 <= len(order_id) <= 80:
                    raise ReviewError('Invalid order identifier.')
                self.send({'review': update_review(order_id, payload, self.server.db, workspace)})
            else:
                if workspace != 'live':
                    raise ReviewError('Add/import/update orders in My orders, not the demo dataset.')
                if path == '/api/order':
                    self.send({'order': live.save(self.server.db, payload)})
                else:
                    self.send(live.import_csv(self.server.db, payload.get('csv'), preview=path.endswith('preview')))
        except (ReviewError, live.DataError) as exc:
            self.send({'error': str(exc)}, exc.status)
        except (ValueError, UnicodeError):
            self.send({'error': 'Invalid JSON request.'}, 400)
        except sqlite3.Error:
            self.send({'error': 'Could not save locally. Retry or check the data folder permissions.'}, 500)


def make_server(port=8765, db=DB):
    initialize(db)
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.db = db
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open', action='store_true', help='Open the local UI in your default browser')
    args = parser.parse_args()
    try:
        server = make_server(args.port)
    except OSError as exc:
        parser.exit(1, f'Cannot start: {exc}. Try --port 8766.\n')
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Pouchhai / পৌঁছাই — {url}\nMy orders uses your records and the current Bangladesh date. Demo data is separate. Ctrl+C to stop.')
    if args.open:
        threading.Timer(.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
