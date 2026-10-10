"""Model and serving invariants, with saved artifacts and observed history."""
import hashlib
import unittest
from pydantic import ValidationError
from service import Forecaster, ForecastRequest
from features import ROOT

class ForecastChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.engine=Forecaster()
    def request(self,**change):
        return ForecastRequest(**{'item_id':'EO020','start_date':'2026-10-10','end_date':'2026-11-08','stock_qty':100,**change})
    def test_exact_range_and_determinism(self):
        p=self.engine.forecast(self.request());q=self.engine.forecast(self.request())
        self.assertEqual(p,q);self.assertEqual(len(p['daily']),30)
        self.assertEqual(p['daily'][0]['date'],'2026-10-10');self.assertEqual(p['daily'][-1]['date'],'2026-11-08')
        self.assertGreater(len({r['predicted_qty'] for r in p['daily']}),7)
    def test_no_recursive_dependency(self):
        a=self.engine.forecast(self.request());b=self.engine.forecast(self.request(start_date='2026-10-20'))
        self.assertEqual([r['predicted_qty'] for r in a['daily'][10:]],[r['predicted_qty'] for r in b['daily']])
    def test_stock_not_demand(self):
        a=self.engine.forecast(self.request());b=self.engine.forecast(self.request(stock_qty=10000))
        self.assertEqual(a['total_expected_demand'],b['total_expected_demand']);self.assertIsNone(b['first_shortage_date'])
    def test_closures_and_multiplier(self):
        closed=self.engine.forecast(self.request(opening_hours=[0]*7,holiday_hours=0))
        self.assertEqual(closed['total_expected_demand'],0)
        a=self.engine.forecast(self.request());b=self.engine.forecast(self.request(demand_factor=2))
        self.assertAlmostEqual(b['total_expected_demand'],2*a['total_expected_demand'],delta=.02)
        o=self.engine.forecast(self.request(overrides=[{'date':'2026-10-12','planned_open_hours':0}]))
        self.assertEqual(o['daily'][2]['predicted_qty'],0);self.assertEqual(o['daily'][2]['upper_qty'],0)
    def test_dated_receipts(self):
        p=self.engine.forecast(self.request(stock_qty=0,on_order_qty=200,receipts=[{'date':'2026-10-12','quantity':200}]))
        self.assertEqual(p['daily'][0]['confirmed_receipt_qty'],0);self.assertEqual(p['daily'][2]['confirmed_receipt_qty'],200)
        self.assertAlmostEqual(p['daily'][2]['net_balance_qty'],200-sum(r['predicted_qty'] for r in p['daily'][:3]),delta=.001)
    def test_newyear_and_future_calendars(self):
        p=self.engine.forecast(self.request(start_date='2027-04-05',end_date='2027-04-20'))
        rows={r['date']:r for r in p['daily']}
        self.assertEqual(rows['2027-04-13']['predicted_qty'],0);self.assertTrue(rows['2027-04-20']['is_public_holiday'])
        q=self.engine.forecast(self.request(start_date='2028-01-01',end_date='2028-01-02'))
        self.assertTrue(any('calendar missing' in w for w in q['warnings']))
    def test_validation(self):
        for changes in [{'end_date':'2026-10-09'},{'stock_qty':-1},{'opening_hours':[9]*6},{'on_order_qty':0,'receipts':[{'date':'2026-10-12','quantity':1}]},{'overrides':[{'date':'2026-10-12','planned_open_hours':25}]}]:
            with self.assertRaises(ValidationError):self.request(**changes)
        with self.assertRaises(ValueError):self.engine.forecast(self.request(item_id='unknown'))
        with self.assertRaises(ValueError):self.engine.forecast(self.request(item_id='OF-A',stock_qty=.5))
        with self.assertRaises(ValueError):self.engine.forecast(self.request(start_date='2025-11-01',end_date='2025-11-20'))
    def test_all_units_and_history_immutable(self):
        path=ROOT/'data/daily_inventory_ledger.csv';before=hashlib.sha256(path.read_bytes()).hexdigest()
        for item in self.engine.catalog.index:
            p=self.engine.forecast(self.request(item_id=item))
            self.assertGreaterEqual(p['total_expected_demand'],0)
            self.assertEqual(p['recommended_order_qty']%p['order_pack_qty'],0)
            self.assertTrue(all(r['lower_qty']<=r['upper_qty'] for r in p['daily']))
        self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main(verbosity=2)
