"""Smoke-run every page with a fake Streamlit + fake database.

Not a visual test: it proves no page has a typo / bad name / wrong call in
its code paths, once with buttons untouched and once with every button 'pressed'.
"""
import os
import sys
import types
import unittest
from contextlib import contextmanager
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Rerun(BaseException):
    pass


class Stop(BaseException):
    pass


class FakeSt(types.ModuleType):
    def __init__(self, press):
        super().__init__("streamlit")
        self.press = press
        self.session_state = {}
        self.query_params = {}
        self.secrets = {}
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: mock.MagicMock()

    # widgets
    def button(self, *a, **k): return self.press
    def form_submit_button(self, *a, **k): return self.press
    def text_input(self, label, value="", **k): return "x@y.z" if "mail" in label.lower() else ("abc" if not value else value)
    def number_input(self, *a, value=0.0, **k): return 5.0 if not value else value
    def date_input(self, *a, value=None, **k): return value or __import__("datetime").date(2026, 10, 26)
    def checkbox(self, *a, value=False, **k): return value
    def selectbox(self, label, options, format_func=str, **k):
        options = list(options)
        if options: format_func(options[0])
        return options[0] if options else None
    def radio(self, label, options, **k): return list(options)[0]
    def text_area(self, *a, **k): return "note"
    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [mock.MagicMock() for _ in range(n)]
    def tabs(self, labels): return [_ctx() for _ in labels]
    def form(self, *a, **k): return _ctx()
    def expander(self, *a, **k): return _ctx()
    def sidebar_(self): return _ctx()
    def rerun(self): raise Rerun()
    def stop(self): raise Stop()


@contextmanager
def _ctx():
    yield mock.MagicMock()


def install(press):
    fake = FakeSt(press)
    fake.sidebar = _ctx()
    fake.sidebar = mock.MagicMock()
    comp = types.ModuleType("streamlit.components")
    sys.modules["streamlit"] = fake
    for m in [k for k in sys.modules if k.split(".")[0] in ("core", "repo", "services", "views") and k != "core.log"]:
        del sys.modules[m]
    return fake


class SmokeTests(unittest.TestCase):
    def run_all(self, press):
        fake = install(press)
        from tests.fake_supabase import FakeDB
        from core import db as coredb
        from repo import assignments, nozzles, profiles, rates, shifts
        from services import sales as sales_svc, settlement as st_svc
        from views import attendant, diagnostics, manager, owner

        db = FakeDB()
        coredb._data_client = lambda: db
        profiles.upsert("o1", "Owner", "owner"); profiles.upsert("m1", "Mgr", "manager"); profiles.upsert("s1", "Ravi", "salesman")
        nozzles.create("N1", "petrol", 1000, "o1"); nozzles.create("N2", "diesel", 50, "o1")
        rates.set_rate("petrol", 100, "2026-01-01", "o1")
        duty = shifts.start("s1", "m1").first
        assignments.assign(duty["id"], 1, "m1")
        user = {"o1": ("owner", {"id": "o1", "name": "Owner", "role": "owner"}),
                "m1": ("manager", {"id": "m1", "name": "Mgr", "role": "manager"}),
                "s1": ("salesman", {"id": "s1", "name": "Ravi", "role": "salesman"})}

        def go(uid, fns):
            fake.session_state["user"] = user[uid][1]
            for fn in fns:
                try:
                    fn()
                except (Rerun, Stop):
                    pass

        # make some data so approval screens have something to show
        ctx = sales_svc.my_context(user["s1"][1]).data
        sales_svc.add_sale(user["s1"][1], ctx["shift"], ctx["assignments"][0], 10)
        st_svc.submit_breakup(user["s1"][1], ctx["shift"], 1000, 0, 0)

        go("s1", [attendant.home, attendant.sale_entry, attendant.breakup])
        go("m1", [manager.duty, manager.assign, manager.approvals, diagnostics.render])
        go("o1", [owner.users, owner.nozzles_page, owner.rates_page, manager.approvals, diagnostics.render])
        # roles are enforced
        fake.session_state["user"] = user["s1"][1]
        with self.assertRaises(Stop):
            owner.users()

    def test_no_press(self):
        self.run_all(False)

    def test_press_everything(self):
        self.run_all(True)


if __name__ == "__main__":
    unittest.main()
