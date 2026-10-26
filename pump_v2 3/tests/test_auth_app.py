"""Login rules + token safety + the real app.py wiring, with fake Streamlit/DB."""
import os
import runpy
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.test_views_smoke import Rerun, Stop, install  # noqa: E402


def boot():
    fake = install(False)
    from tests.fake_supabase import FakeDB
    from core import db as coredb, auth
    from repo import profiles, shifts
    db = FakeDB()
    coredb._data_client = lambda: db
    profiles.upsert("o1", "Owner", "owner")
    profiles.upsert("s1", "Ravi", "salesman")
    profiles.upsert("s2", "Off", "salesman", is_active=False)
    return fake, db, auth, shifts


def sign_in_as(auth, uid):
    client = mock.MagicMock()
    client.auth.sign_in_with_password.return_value = mock.MagicMock(user=mock.MagicMock(id=uid))
    return mock.patch.object(auth, "auth_client", return_value=client)


class AuthTests(unittest.TestCase):
    def test_owner_login_and_token_restore(self):
        fake, db, auth, _ = boot()
        with sign_in_as(auth, "o1"):
            r = auth.login("A@B.com", "pw")
        self.assertTrue(r.ok, r)
        self.assertEqual(fake.session_state["user"]["role"], "owner")
        token = fake.query_params["s"]
        fake.session_state.clear()
        res = auth.restore()
        self.assertTrue(res.ok)
        self.assertEqual(fake.session_state["user"]["id"], "o1")

    def test_salesman_needs_duty(self):
        fake, db, auth, shifts = boot()
        with sign_in_as(auth, "s1"):
            r = auth.login("a@b.c", "pw")
        self.assertFalse(r.ok)
        self.assertIn("No active duty", r.error)
        shifts.start("s1", "o1")
        with sign_in_as(auth, "s1"):
            self.assertTrue(auth.login("a@b.c", "pw").ok)

    def test_inactive_and_missing_profile_messages(self):
        fake, db, auth, _ = boot()
        with sign_in_as(auth, "s2"):
            self.assertIn("switched off", auth.login("a@b.c", "pw").error)
        with sign_in_as(auth, "nobody"):
            r = auth.login("a@b.c", "pw")
        self.assertIn("no profile exists", r.error)
        self.assertIn("nobody", r.error)

    def test_wrong_password_reason_and_lockout(self):
        fake, db, auth, _ = boot()
        client = mock.MagicMock()
        client.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")
        with mock.patch.object(auth, "auth_client", return_value=client):
            for _ in range(5):
                r = auth.login("a@b.c", "bad")
            self.assertIn("Invalid login credentials", r.error)
            self.assertIn("Wait a minute", auth.login("a@b.c", "bad").error)

    def test_forged_and_expired_tokens(self):
        fake, db, auth, _ = boot()
        self.assertIsNone(auth.read_token("garbage"))
        t = auth.make_token("o1", ttl=-5)
        self.assertIsNone(auth.read_token(t))
        body, sig = auth.make_token("o1").split(".")
        self.assertIsNone(auth.read_token(body + "." + "0" * 64))

    def test_token_for_deactivated_user_is_refused(self):
        fake, db, auth, _ = boot()
        fake.query_params["s"] = auth.make_token("s2")
        res = auth.restore()
        self.assertFalse(res.ok)
        self.assertNotIn("user", fake.session_state)
        self.assertNotIn("s", fake.query_params)

    def test_logout_clears_everything(self):
        fake, db, auth, _ = boot()
        with sign_in_as(auth, "o1"):
            auth.login("a@b.c", "pw")
            auth.logout()
        self.assertNotIn("user", fake.session_state)
        self.assertNotIn("s", fake.query_params)


class AppTests(unittest.TestCase):
    def run_app(self, uid=None):
        fake, db, auth, shifts = boot()
        os.environ["SUPABASE_URL"] = "https://x.supabase.co"
        os.environ["SUPABASE_ANON_KEY"] = "anon-key-value-1234"
        shifts.start("s1", "o1")
        if uid:
            from repo import profiles
            p = profiles.get_any(uid).first
            fake.session_state["user"] = {"id": uid, "name": p["name"], "role": p["role"]}
        try:
            runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"))
        except (Rerun, Stop):
            pass
        return fake

    def test_app_all_roles(self):
        for uid in (None, "o1", "s1"):
            self.run_app(uid)

    def test_app_not_configured(self):
        for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY"):
            os.environ.pop(k, None)
        fake, *_ = boot()
        with mock.patch("core.config.get", return_value=None):
            with self.assertRaises(Stop):
                runpy.run_path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"))


if __name__ == "__main__":
    unittest.main()
