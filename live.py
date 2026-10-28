"""Current-date, user-owned order records. No courier API is implied."""
import csv
import io
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone

FIELDS = ('order_id', 'city', 'area', 'order_date', 'expected_delivery_date', 'dispatched_date', 'delivered_date', 'source_reference')
REQUIRED = {'order_id', 'city', 'order_date', 'expected_delivery_date'}


class DataError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def today():
    return datetime.now(timezone(timedelta(hours=6))).date()


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def connect(db):
    connection = sqlite3.connect(db, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize(connection):
    connection.executescript('''
    CREATE TABLE IF NOT EXISTS live_orders (
      order_id TEXT PRIMARY KEY, city TEXT NOT NULL, area TEXT NOT NULL DEFAULT '',
      order_date TEXT NOT NULL, expected_delivery_date TEXT NOT NULL,
      dispatched_date TEXT NOT NULL DEFAULT '', delivered_date TEXT NOT NULL DEFAULT '',
      source_reference TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS live_reviews (
      order_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'New',
      owner TEXT NOT NULL DEFAULT 'Unassigned', priority TEXT NOT NULL DEFAULT 'Normal',
      resolution TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 0,
      updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS live_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL, timestamp TEXT NOT NULL,
      before_json TEXT NOT NULL, after_json TEXT NOT NULL, note TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS order_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL, timestamp TEXT NOT NULL,
      before_json TEXT NOT NULL, after_json TEXT NOT NULL, note TEXT NOT NULL);
    ''')


def validate(payload, reference=None):
    reference = reference or today()
    if not isinstance(payload, dict):
        raise DataError('Expected an order object.')
    record = {}
    for field in FIELDS:
        value = payload.get(field, '')
        if value is None:
            value = ''
        if not isinstance(value, str):
            raise DataError(f'{field} must be text.')
        value = value.strip()
        if any(ord(character) < 32 for character in value):
            raise DataError(f'{field} must not contain control characters.')
        if len(value) > (250 if field == 'source_reference' else 80):
            raise DataError(f'{field} is too long.')
        record[field] = value
    for field in REQUIRED:
        if not record[field]:
            raise DataError(f'{field} is required.')
    for field in ('order_date', 'expected_delivery_date', 'dispatched_date', 'delivered_date'):
        value = record[field]
        if not value:
            continue
        try:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value:
                raise ValueError()
        except ValueError:
            raise DataError(f'{field} must be a valid YYYY-MM-DD date.') from None
    purchase = record['order_date']
    if purchase > reference.isoformat():
        raise DataError('Order date cannot be in the future.')
    for field in ('expected_delivery_date', 'dispatched_date', 'delivered_date'):
        if record[field] and record[field] < purchase:
            raise DataError(f'{field} cannot be before order_date.')
    for field in ('dispatched_date', 'delivered_date'):
        if record[field] and record[field] > reference.isoformat():
            raise DataError(f'{field} cannot be in the future. Leave it empty until confirmed.')
    if record['dispatched_date'] and record['delivered_date'] and record['delivered_date'] < record['dispatched_date']:
        raise DataError('Delivery cannot be before dispatch.')
    return record


def classify(record, reference=None):
    reference = reference or today()
    expected = date.fromisoformat(record['expected_delivery_date'])
    delivered = date.fromisoformat(record['delivered_date']) if record['delivered_date'] else None
    days = max(0, ((delivered or reference) - expected).days)
    kind = ('Delivered late' if days else 'On time') if delivered else ('Overdue' if days else 'On schedule')
    return kind, days


def sync_reviews(connection, reference=None):
    # Recalculate at read time: an undelivered order can become overdue overnight.
    for row in connection.execute('SELECT * FROM live_orders').fetchall():
        kind, _ = classify(dict(row), reference)
        if kind in ('Overdue', 'Delivered late'):
            connection.execute('INSERT OR IGNORE INTO live_reviews(order_id,updated_at) VALUES (?,?)', (row['order_id'], now()))


def orders(db, reference=None):
    reference = reference or today()
    with connect(db) as connection:
        sync_reviews(connection, reference)
        records = [dict(row) for row in connection.execute('SELECT * FROM live_orders')]
        reviews = {row['order_id']: dict(row) for row in connection.execute('SELECT * FROM live_reviews')}
    result = []
    for record in records:
        kind, days = classify(record, reference)
        result.append({**record, 'state': record['area'], 'country': 'Bangladesh',
                       'purchased_at': record['order_date'], 'estimated_at': record['expected_delivery_date'],
                       'carrier_at': record['dispatched_date'], 'delivered_at': record['delivered_date'],
                       'as_of': reference.isoformat(), 'exception': kind, 'delay_days': days,
                       'delivery_stage': 'Delivered' if record['delivered_date'] else 'In transit' if record['dispatched_date'] else 'Awaiting dispatch',
                       'review': reviews.get(record['order_id']), 'source_version': record['version']})
    rank = {'High': 0, 'Normal': 1, 'Low': 2}
    return sorted(result, key=lambda row: (row['review'] is None, bool(row['review'] and row['review']['status'] == 'Resolved'), rank.get((row['review'] or {}).get('priority'), 3), -row['delay_days'], row['order_id']))


def save(db, payload):
    record = validate(payload)
    action = payload.get('action', 'create')
    if action not in ('create', 'update'):
        raise DataError('Unknown order action.')
    note = payload.get('change_note', '')
    if action == 'update' and (not isinstance(note, str) or not 3 <= len(note.strip()) <= 1000):
        raise DataError('Describe the source correction in 3–1,000 characters.')
    with connect(db) as connection:
        connection.execute('BEGIN IMMEDIATE')
        old = connection.execute('SELECT * FROM live_orders WHERE order_id=?', (record['order_id'],)).fetchone()
        timestamp = now()
        if action == 'create':
            if old:
                raise DataError('That order ID already exists. Open the existing order to update it.', 409)
            insert(connection, record, timestamp, 'Added from order form')
        else:
            if not old:
                raise DataError('Order no longer exists.', 404)
            if type(payload.get('source_version')) is not int or payload['source_version'] != old['version']:
                raise DataError('This order changed in another tab. Reload the order before updating.', 409)
            connection.execute('UPDATE live_orders SET '+','.join(field+'=?' for field in FIELDS if field != 'order_id')+', version=version+1,updated_at=? WHERE order_id=?',
                               [record[field] for field in FIELDS if field != 'order_id'] + [timestamp, record['order_id']])
            after = dict(connection.execute('SELECT * FROM live_orders WHERE order_id=?', (record['order_id'],)).fetchone())
            connection.execute('INSERT INTO order_events(order_id,timestamp,before_json,after_json,note) VALUES(?,?,?,?,?)',
                               (record['order_id'], timestamp, json.dumps(dict(old)), json.dumps(after), note.strip()))
            connection.execute('UPDATE live_reviews SET version=version+1,updated_at=? WHERE order_id=?', (timestamp, record['order_id']))
        sync_reviews(connection)
    return record


def insert(connection, record, timestamp, note):
    connection.execute('INSERT INTO live_orders('+','.join(FIELDS)+',created_at,updated_at) VALUES('+','.join('?' for _ in FIELDS)+',?,?)', [record[field] for field in FIELDS] + [timestamp, timestamp])
    connection.execute('INSERT INTO order_events(order_id,timestamp,before_json,after_json,note) VALUES(?,?,?,?,?)',
                       (record['order_id'], timestamp, '{}', json.dumps(record), note))


def parse_import(text, existing):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 1_000_000:
        raise DataError('Choose a UTF-8 CSV smaller than 1 MB.')
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')), strict=True)
    if not reader.fieldnames or not REQUIRED <= set(reader.fieldnames):
        raise DataError('CSV needs columns: '+', '.join(sorted(REQUIRED)))
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise DataError('CSV has duplicate column headers.')
    valid, errors, seen = [], [], set()
    try:
        for line, row in enumerate(reader, start=2):
            if line > 501:
                raise DataError('Import at most 500 orders at a time.')
            if not any(value for value in row.values()):
                continue
            try:
                if None in row:
                    raise DataError('Extra CSV fields; quote values containing commas.')
                record = validate(row)
                if record['order_id'] in seen or record['order_id'] in existing:
                    raise DataError('Duplicate order ID. Existing orders must be updated individually.')
                seen.add(record['order_id']); valid.append(record)
            except DataError as exc:
                errors.append({'row': line, 'message': str(exc)})
    except csv.Error as exc:
        raise DataError(f'CSV could not be read: {exc}') from exc
    if not valid and not errors:
        raise DataError('CSV has no orders. Add rows beneath the template header.')
    return valid, errors


def import_csv(db, text, preview=False):
    with connect(db) as connection:
        connection.execute('BEGIN IMMEDIATE')
        existing = {row['order_id'] for row in connection.execute('SELECT order_id FROM live_orders')}
        records, errors = parse_import(text, existing)
        if not preview and errors:
            raise DataError(f'Nothing imported. Fix row {errors[0]["row"]}: {errors[0]["message"]}')
        if not preview:
            timestamp = now()
            for record in records:
                insert(connection, record, timestamp, 'Imported from CSV')
            sync_reviews(connection)
        return {'valid': not errors, 'count': len(records), 'errors': errors[:50], 'preview': records[:5], 'imported': len(records) if not preview else 0}


def order_events(db, order_id):
    with connect(db) as connection:
        return [dict(row) for row in connection.execute('SELECT * FROM order_events WHERE order_id=? ORDER BY id DESC', (order_id,))]


def export_orders(db, safe):
    buffer = io.StringIO(newline=''); writer = csv.writer(buffer); writer.writerow(FIELDS)
    with connect(db) as connection:
        for row in connection.execute('SELECT * FROM live_orders ORDER BY order_id'):
            writer.writerow([safe(row[field]) for field in FIELDS])
    return ('\ufeff'+buffer.getvalue()).encode('utf-8')


def template():
    return (','.join(FIELDS)+'\r\n').encode('utf-8')
