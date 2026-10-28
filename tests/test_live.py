import csv
import io
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import app
import live


class LiveOrdersTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'orders.sqlite3'
        app.initialize(self.db)
        self.today = live.today()

    def tearDown(self):
        self.temp.cleanup()

    def record(self, order_id='SHOP-101', **changes):
        row = dict(order_id=order_id, city='ঢাকা', area='Mirpur', order_date=(self.today-timedelta(days=5)).isoformat(), expected_delivery_date=(self.today-timedelta(days=2)).isoformat(), dispatched_date='', delivered_date='', source_reference='Business ledger 101')
        row.update(changes)
        return row

    def csv(self, rows):
        buffer = io.StringIO(); writer = csv.DictWriter(buffer, fieldnames=live.FIELDS)
        writer.writeheader(); writer.writerows(rows)
        return buffer.getvalue()

    def test_default_workspace_empty_and_separate_from_demo(self):
        self.assertEqual(app.orders_for('live',self.db),[])
        self.assertEqual(len(app.orders_for('demo',self.db)),120)

    def test_add_own_order_and_current_delay(self):
        live.save(self.db,self.record())
        order=app.orders_for('live',self.db)[0]
        self.assertEqual(order['exception'],'Overdue')
        self.assertEqual(order['delay_days'],2)
        self.assertEqual(order['review']['status'],'New')
        self.assertEqual(order['city'],'ঢাকা')
        self.assertEqual(len(app.orders_for('demo',self.db)),120)

    def test_on_schedule_can_become_overdue_without_edit(self):
        live.save(self.db,self.record(expected_delivery_date=self.today.isoformat()))
        self.assertEqual(live.orders(self.db,self.today)[0]['exception'],'On schedule')
        self.assertIsNone(live.orders(self.db,self.today)[0]['review'])
        tomorrow=self.today+timedelta(days=1)
        order=live.orders(self.db,tomorrow)[0]
        self.assertEqual(order['exception'],'Overdue')
        self.assertEqual(order['delay_days'],1)
        self.assertIsNotNone(order['review'])

    def test_date_based_delivery_categories(self):
        sample=self.record(delivered_date=(self.today-timedelta(days=2)).isoformat())
        self.assertEqual(live.classify(sample)[0],'On time')
        sample['delivered_date']=(self.today-timedelta(days=1)).isoformat()
        self.assertEqual(live.classify(sample),('Delivered late',1))

    def test_invalid_dates_and_future_actual_events(self):
        for field,value in [('order_date',(self.today+timedelta(days=1)).isoformat()),('dispatched_date','2025-02-30'),('delivered_date',(self.today+timedelta(days=1)).isoformat()),('expected_delivery_date','1900-01-01')]:
            with self.subTest(field=field):
                row=self.record();row[field]=value
                with self.assertRaises(live.DataError): live.save(self.db,row)
        self.assertEqual(app.orders_for('live',self.db),[])

    def test_delivered_cannot_precede_dispatch(self):
        row=self.record(dispatched_date=self.today.isoformat(), delivered_date=(self.today-timedelta(days=1)).isoformat())
        with self.assertRaises(live.DataError): live.save(self.db,row)

    def test_duplicate_id_does_not_overwrite(self):
        live.save(self.db,self.record())
        with self.assertRaises(live.DataError) as caught: live.save(self.db,self.record(city='Chattogram'))
        self.assertEqual(caught.exception.status,409)
        self.assertEqual(live.orders(self.db)[0]['city'],'ঢাকা')

    def test_update_source_requires_reason_and_version(self):
        live.save(self.db,self.record())
        row=self.record(action='update',source_version=0)
        with self.assertRaises(live.DataError):live.save(self.db,row)
        row['change_note']='Delivery confirmation received';row['delivered_date']=self.today.isoformat()
        live.save(self.db,row)
        result=live.orders(self.db)[0]
        self.assertEqual(result['source_version'],1)
        self.assertEqual(result['exception'],'Delivered late')
        self.assertEqual(len(live.order_events(self.db,'SHOP-101')),2)
        with self.assertRaises(live.DataError) as caught:live.save(self.db,row)
        self.assertEqual(caught.exception.status,409)

    def test_source_update_invalidates_stale_review(self):
        live.save(self.db,self.record())
        update=self.record(action='update',source_version=0,change_note='Source date corrected',delivered_date=self.today.isoformat())
        live.save(self.db,update)
        payload=dict(status='In review',owner='Support desk',priority='Normal',note='Reviewed old evidence',version=0)
        with self.assertRaises(app.ReviewError) as caught:app.update_review('SHOP-101',payload,self.db,'live')
        self.assertEqual(caught.exception.status,409)

    def test_csv_preview_writes_nothing(self):
        result=live.import_csv(self.db,self.csv([self.record(),self.record('SHOP-102')]),preview=True)
        self.assertTrue(result['valid']);self.assertEqual(result['count'],2)
        self.assertEqual(live.orders(self.db),[])

    def test_csv_all_or_nothing_and_rows_with_errors(self):
        text=self.csv([self.record(),self.record('SHOP-102',expected_delivery_date='invalid')])
        result=live.import_csv(self.db,text,preview=True)
        self.assertFalse(result['valid']);self.assertEqual(result['errors'][0]['row'],3)
        with self.assertRaises(live.DataError):live.import_csv(self.db,text)
        self.assertEqual(live.orders(self.db),[])

    def test_csv_duplicate_batch_and_existing_record(self):
        repeated=self.csv([self.record(),self.record()])
        with self.assertRaises(live.DataError):live.import_csv(self.db,repeated)
        live.save(self.db,self.record())
        with self.assertRaises(live.DataError):live.import_csv(self.db,self.csv([self.record()]))
        self.assertEqual(len(live.orders(self.db)),1)

    def test_import_success_and_activity(self):
        result=live.import_csv(self.db,self.csv([self.record(),self.record('SHOP-102')]))
        self.assertEqual(result['imported'],2)
        self.assertEqual(len(live.orders(self.db)),2)
        self.assertEqual(live.order_events(self.db,'SHOP-101')[0]['note'],'Imported from CSV')

    def test_empty_headers_extra_fields_and_import_size(self):
        for text in ['a,b\n1,2\n',live.template().decode(),','.join(live.FIELDS)+'\n'+','.join(['x']*10),'x'*1000001]:
            with self.subTest(text=text[:20]):
                with self.assertRaises(live.DataError):live.import_csv(self.db,text)

    def test_user_and_demo_identical_ids_remain_separate(self):
        demo=app.orders_for('demo',self.db)[0];live.save(self.db,self.record(demo['order_id']))
        app.update_review(demo['order_id'],dict(status='In review',owner='Support desk',priority='High',note='Own record reviewed',version=0),self.db,'live')
        original=next(row for row in app.orders_for('demo',self.db) if row['order_id']==demo['order_id'])
        self.assertEqual(original['review']['version'],0)

    def test_order_and_review_exports(self):
        live.save(self.db,self.record(source_reference='=HYPERLINK("x")'))
        data=live.export_orders(self.db,app.csv_safe).decode('utf-8-sig')
        exported=list(csv.DictReader(io.StringIO(data)))
        self.assertTrue(exported[0]['source_reference'].startswith("'="))
        self.assertIn('SHOP-101',app.export_csv(self.db,'live').decode())
        self.assertEqual(live.template().decode().splitlines()[0],','.join(live.FIELDS))


if __name__=='__main__':unittest.main()
