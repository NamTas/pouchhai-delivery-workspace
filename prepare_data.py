"""Reproduce the small historical snapshot from the official Olist Kaggle ZIP."""
import argparse
import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AS_OF = '2018-08-31 23:59:59'
SOURCE = 'https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce'


def prepare(zip_path, destination=ROOT / 'data'):
    with zipfile.ZipFile(zip_path) as archive:
        raw = archive.read('olist_orders_dataset.csv')
        orders = list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
        customers = {r['customer_id']: r for r in csv.DictReader(io.StringIO(archive.read('olist_customers_dataset.csv').decode()))}
    groups = {'Overdue in snapshot': [], 'Delivered late': [], 'On time': []}
    for row in orders:
        purchase, estimate = row['order_purchase_timestamp'], row['order_estimated_delivery_date']
        # A fixed recent purchase window keeps the demo bounded. No post-cutoff outcome
        # or undated cancellation status is used to infer an active case.
        if not ('2018-07-01' <= purchase <= AS_OF) or not estimate or estimate > AS_OF:
            continue
        if row['order_status'] in ('canceled', 'unavailable'):
            continue
        received = row['order_delivered_customer_date']
        carrier = row['order_delivered_carrier_date']
        received = received if received and received <= AS_OF else ''
        carrier = carrier if carrier and carrier <= AS_OF else ''
        # The estimate is a calendar date. Delivery on that date is not late.
        end = received[:10] if received else AS_OF[:10]
        days = max(0, (datetime.fromisoformat(end) - datetime.fromisoformat(estimate[:10])).days)
        if not received and days == 0:
            continue
        kind = 'Delivered late' if received and days else 'On time' if received else 'Overdue in snapshot'
        customer = customers[row['customer_id']]
        groups[kind].append({
            'order_id': row['order_id'], 'city': customer['customer_city'], 'state': customer['customer_state'],
            'purchased_at': purchase, 'estimated_at': estimate, 'carrier_at': carrier,
            'delivered_at': received, 'as_of': AS_OF, 'exception': kind, 'delay_days': days,
            'delivery_stage': 'Delivered' if received else 'In transit' if carrier else 'Awaiting dispatch',
        })
    selected = []
    for group, count in [('Overdue in snapshot', 40), ('Delivered late', 60), ('On time', 20)]:
        candidates = sorted(groups[group], key=lambda r: r['order_id'])
        if len(candidates) < count:
            raise ValueError(f'Insufficient rows for {group}: {len(candidates)}')
        selected.extend(candidates[:count])
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / 'demo_orders.csv'
    with output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader(); writer.writerows(selected)
    manifest = {
        'source': SOURCE, 'publisher': 'Olist', 'license': 'CC BY-NC-SA 4.0',
        'license_url': 'https://creativecommons.org/licenses/by-nc-sa/4.0/',
        'downloaded_at': datetime.now(timezone.utc).isoformat(),
        'orders_source_sha256': hashlib.sha256(raw).hexdigest(),
        'subset_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'as_of': AS_OF, 'purchase_window': '2018-07-01 through snapshot',
        'selection': 'Sort eligible IDs ascending within each group; select 40 overdue, 60 delivered-late, 20 on-time.',
        'rows': len(selected), 'available_in_window': {key: len(value) for key, value in groups.items()},
        'notice': 'Historical Brazilian proxy data, not Bangladeshi orders or cold-chain measurements. Exception-enriched convenience sample; do not infer population rates. Workflow states and notes are local demo records, not real customer tickets.',
        'transformations': 'Join customer city/state only; exclude customer identifiers, reviews and payments. Mask carrier/delivery events after the cutoff. Date-based lateness; nights/weekends included. Exclude canceled/unavailable statuses because cancellation dates are absent; original terminal statuses may create selection bias.',
    }
    (destination / 'provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({'selected': len(selected), 'available': manifest['available_in_window']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip', help='Official Kaggle ZIP downloaded by you')
    args = parser.parse_args()
    prepare(args.zip)
