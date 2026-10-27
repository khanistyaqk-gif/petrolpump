"""Login, logout, current user and role checks."""
import time

import streamlit as st

from core import session
from core.db import auth_client
from repo import duties, users

MAX_FAILS = 5
LOCK_SECONDS = 60
RECHECK_SECONDS = 60   # re-check profile/shift every minute (disabled users are signed out)


def _allowed(profile) -> tuple[bool, str]:
    if not profile or not profile.get("is_active"):
        return False, "This account is inactive or does not exist. Please contact the Owner."
    if profile["role"] == "salesman" and not duties.active_duty_for(profile["id"]):
        return False, "Salesmen can log in only during an active shift. Please ask the Manager to start your shift."
    return True, ""


def _set_user(profile):
    st.session_state["user"] = {
        "id": profile["id"], "name": profile.get("name") or "User",
        "role": profile["role"], "phone": profile.get("phone"),
    }
    st.session_state["_checked_at"] = time.time()


def login(login_id: str, password: str) -> tuple[bool, str]:
    if st.session_state.get("_locked_until", 0) > time.time():
        return False, "Too many failed attempts. Please try again in 1 minute."
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
        return False, "Invalid login ID or password."

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
        return user   # do not sign out on a brief network error
    ok, _ = _allowed(profile)
    if not ok:
        session.clear()
        return None
    _set_user(profile)
    return st.session_state["user"]


def require(*roles):
    user = current_user()
    if not user:
        st.error("Please log in first.")
        st.stop()
    if user["role"] not in roles:
        st.error("You do not have permission to view this page.")
        st.stop()
    return user
