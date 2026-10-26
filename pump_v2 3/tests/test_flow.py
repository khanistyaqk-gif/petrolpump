"""Whole workflow on a fake database:
duty -> assign nozzle -> sales -> breakup -> manager closing -> approve.
Run:  python -m unittest discover -s tests -v
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.fake_supabase import FakeDB  # noqa: E402
from core import db as coredb  # noqa: E402
from repo import assignments, nozzles, rates, shifts  # noqa: E402
from services import calc, sales as sales_svc, settlement as st_svc  # noqa: E402

OWNER = {"id": "o1", "name": "Owner", "role": "owner"}
MGR = {"id": "m1", "name": "Mgr", "role": "manager"}
SAL = {"id": "s1", "name": "Ravi", "role": "salesman"}


class Base(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDB()
        coredb._data_client = lambda: self.fake
        self.assertTrue(nozzles.create("N1", "petrol", 1000, "o1").ok)
        self.assertTrue(rates.set_rate("petrol", 100, "2026-01-01", "o1").ok)

    def start_duty_and_assign(self):
        duty = shifts.start("s1", "m1"); self.assertTrue(duty.ok, duty)
        asg = assignments.assign(duty.first["id"], 1, "m1"); self.assertTrue(asg.ok, asg)
        ctx = sales_svc.my_context(SAL); self.assertTrue(ctx.ok, ctx)
        return ctx.data


class CalcTests(unittest.TestCase):
    def test_match(self):
        self.assertTrue(calc.payment_match(1000, 600, 300, 100)["is_matched"])
        self.assertFalse(calc.payment_match(1000, 600, 300, 50)["is_matched"])

    def test_meter_rows_errors(self):
        a = [{"id": 1, "nozzle_id": 1, "nozzle_name": "N1", "opening_reading": 100}]
        rows, total, errs = calc.meter_rows(a, [], {})
        self.assertTrue(errs and not rows)
        rows, total, errs = calc.meter_rows(a, [], {1: 50})
        self.assertIn("less than opening", errs[0])


class FlowTests(Base):
    def test_happy_path(self):
        ctx = self.start_duty_and_assign()
        shift, asg = ctx["shift"], ctx["assignments"][0]
        self.assertEqual(asg["opening_reading"], 1000)
        self.assertTrue(sales_svc.add_sale(SAL, shift, asg, 10).ok)
        self.assertTrue(sales_svc.add_sale(SAL, shift, asg, 5.5).ok)
        ctx = sales_svc.my_context(SAL).data
        self.assertEqual(ctx["total_sale"], 1550.0)

        bad = st_svc.submit_breakup(SAL, shift, 1000, 400, 100)
        self.assertFalse(bad.ok)
        self.assertIn("difference", bad.error)
        sub = st_svc.submit_breakup(SAL, shift, 1000, 400, 150)
        self.assertTrue(sub.ok, sub)
        sid = sub.first["id"]

        # locked after submit
        self.assertFalse(sales_svc.add_sale(SAL, shift, asg, 1).ok)
        self.assertFalse(st_svc.submit_breakup(SAL, shift, 1000, 400, 150).ok)

        # approve before closing is blocked
        self.assertIn("closing", st_svc.approve(MGR, sid).error.lower())
        # wrong closing: meter 20 L vs 15.5 entered
        save = st_svc.save_closing(MGR, sid, {asg["id"]: 1020})
        self.assertTrue(save.ok)
        self.assertFalse(save.data["matched"])
        self.assertFalse(st_svc.approve(MGR, sid).ok)
        # right closing
        self.assertTrue(st_svc.save_closing(MGR, sid, {asg["id"]: 1015.5}).data["matched"])
        done = st_svc.approve(MGR, sid)
        self.assertTrue(done.ok, done)
        self.assertEqual(done.first["status"], "approved")
        self.assertEqual(nozzles.get(1).first["current_reading"], 1015.5)
        self.assertEqual(assignments.for_shift(shift["id"]).rows, [])
        self.assertTrue(all(e["status"] == "approved" for e in self.fake.tables["sale_entries"]))

    def test_reject_then_fresh_sale(self):
        ctx = self.start_duty_and_assign()
        shift, asg = ctx["shift"], ctx["assignments"][0]
        sales_svc.add_sale(SAL, shift, asg, 10)
        sid = st_svc.submit_breakup(SAL, shift, 1000, 0, 0).first["id"]
        self.assertTrue(st_svc.reject(MGR, sid, "wrong").ok)
        self.assertEqual(sales_svc.my_context(SAL).data["total_sale"], 0)
        self.assertTrue(sales_svc.add_sale(SAL, shift, asg, 3).ok)
        again = st_svc.submit_breakup(SAL, shift, 300, 0, 0)
        self.assertTrue(again.ok, again)
        self.assertEqual(len(self.fake.tables["settlements"]), 1)  # same row reused

    def test_hold_and_reopen(self):
        ctx = self.start_duty_and_assign()
        sales_svc.add_sale(SAL, ctx["shift"], ctx["assignments"][0], 1)
        sid = st_svc.submit_breakup(SAL, ctx["shift"], 100, 0, 0).first["id"]
        self.assertTrue(st_svc.hold(MGR, sid, "wait").ok)
        self.assertFalse(st_svc.hold(MGR, sid, "again").ok)
        self.assertTrue(st_svc.reopen(MGR, sid).ok)

    def test_cancel_own_pending_entry(self):
        ctx = self.start_duty_and_assign()
        e = sales_svc.add_sale(SAL, ctx["shift"], ctx["assignments"][0], 4).first
        self.assertFalse(sales_svc.cancel_sale({"id": "other"}, e["id"]).ok)
        self.assertTrue(sales_svc.cancel_sale(SAL, e["id"]).ok)
        self.assertEqual(sales_svc.my_context(SAL).data["total_sale"], 0)


class RuleTests(Base):
    def test_one_duty_per_salesman(self):
        self.assertTrue(shifts.start("s1", "m1").ok)
        r = shifts.start("s1", "m1")
        self.assertFalse(r.ok)
        self.assertIn("already", r.error)

    def test_nozzle_cannot_be_double_assigned(self):
        a = shifts.start("s1", "m1").first["id"]
        b = shifts.start("s2", "m1").first["id"]
        self.assertTrue(assignments.assign(a, 1, "m1").ok)
        r = assignments.assign(b, 1, "m1")
        self.assertFalse(r.ok)
        self.assertIn("already assigned", r.error)

    def test_missing_rate_message(self):
        self.fake.tables["fuel_rates"].clear()
        ctx = self.start_duty_and_assign()
        r = sales_svc.add_sale(SAL, ctx["shift"], ctx["assignments"][0], 5)
        self.assertFalse(r.ok)
        self.assertIn("rate for petrol is not set", r.error)

    def test_no_duty_message(self):
        r = sales_svc.my_context(SAL)
        self.assertFalse(r.ok)
        self.assertIn("No active duty", r.error)

    def test_db_failure_is_reported_not_hidden(self):
        self.fake.fail_on[("shifts", "insert")] = "column shifts.date does not exist"
        r = shifts.start("s1", "m1")
        self.assertFalse(r.ok)
        self.assertIn("column shifts.date", r.error)
        self.assertEqual(r.where, "shifts.start")
        from core.log import recent_trace
        self.assertFalse(recent_trace(1)[0]["ok"])

    def test_partial_approval_is_explained_and_retryable(self):
        ctx = self.start_duty_and_assign()
        shift, asg = ctx["shift"], ctx["assignments"][0]
        sales_svc.add_sale(SAL, shift, asg, 10)
        sid = st_svc.submit_breakup(SAL, shift, 1000, 0, 0).first["id"]
        st_svc.save_closing(MGR, sid, {asg["id"]: 1010})
        self.fake.fail_on[("nozzles", "update")] = "permission denied"
        r = st_svc.approve(MGR, sid)
        self.assertFalse(r.ok)
        self.assertIn("Already done: sale entries approved", r.error)
        self.assertEqual(self.fake.tables["settlements"][0]["status"], "pending")
        self.fake.fail_on.clear()
        self.assertTrue(st_svc.approve(MGR, sid).ok)


if __name__ == "__main__":
    unittest.main()
