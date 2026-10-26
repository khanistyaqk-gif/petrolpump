"""Login, logout, current user aur role check."""
import time

import streamlit as st

from core import session
from core.db import auth_client
from repo import duties, users

MAX_FAILS = 5
LOCK_SECONDS = 60
RECHECK_SECONDS = 60   # har minute profile/duty dobara check (band user turant bahar)


def _allowed(profile) -> tuple[bool, str]:
    if not profile or not profile.get("is_active"):
        return False, "Account band hai ya mila nahi. Owner se baat karein."
    if profile["role"] == "salesman" and not duties.active_duty_for(profile["id"]):
        return False, "Salesman login sirf duty chalu hone par. Manager se duty shuru karwayein."
    return True, ""


def _set_user(profile):
    st.session_state["user"] = {
        "id": profile["id"], "name": profile.get("name") or "User",
        "role": profile["role"], "phone": profile.get("phone"),
    }
    st.session_state["_checked_at"] = time.time()


def login(login_id: str, password: str) -> tuple[bool, str]:
    if st.session_state.get("_locked_until", 0) > time.time():
        return False, "Bahut baar galat try. 1 minute baad try karein."
    try:
        res = auth_client().auth.sign_in_with_password(
            {"email": users.login_to_email(login_id), "password": password})
        uid = res.user.id
    except Exception:
        fails = st.session_state.get("_fails", 0) + 1
        st.session_state["_fails"] = fails
        if fails >= MAX_FAILS:
            st.session_state["_locked_until"] = time.time() + LOCK_SECONDS
            st.session_state["_fails"] = 0
        return False, "Login ID ya password galat hai."

    st.session_state["_fails"] = 0
    profile = users.get_profile(uid)
    ok, msg = _allowed(profile)
    if not ok:
        return False, msg
    _set_user(profile)
    session.save(uid)
    return True, ""


def logout():
    session.clear()
    st.session_state["_logged_out"] = True


def current_user():
    user = st.session_state.get("user")
    if user and time.time() - st.session_state.get("_checked_at", 0) < RECHECK_SECONDS:
        return user

    uid = user["id"] if user else session.restore_user_id()
    if not uid:
        return None
    try:
        profile = users.get_profile(uid)
    except Exception:
        return user   # network ki chhoti dikkat par logout nahi
    ok, _ = _allowed(profile)
    if not ok:
        session.clear()
        return None
    _set_user(profile)
    return st.session_state["user"]


def require(*roles):
    user = current_user()
    if not user:
        st.error("Pehle login karein.")
        st.stop()
    if user["role"] not in roles:
        st.error("Aapko is page ki permission nahi hai.")
        st.stop()
    return user
