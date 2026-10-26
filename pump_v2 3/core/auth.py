"""Login, session and logout. Small on purpose.

Session = st.session_state["user"] plus a signed token in the URL (?s=...)
so a browser refresh keeps you logged in. No cookies / localStorage / JS.
Closing the tab logs you out of that tab (by design: simple and predictable).
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

import streamlit as st

from core import config
from core.db import Result, auth_client, fail, ok
from core.log import get_logger
from repo import profiles, shifts

log = get_logger()

PARAM = "s"
TTL_SECONDS = 12 * 60 * 60
_EPHEMERAL = secrets.token_hex(32)  # used when APP_SESSION_SECRET is not set


def _key() -> bytes:
    secret = config.get("APP_SESSION_SECRET")
    return (secret if secret and len(secret) >= 16 else _EPHEMERAL).encode()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def make_token(user_id: str, ttl: int = TTL_SECONDS) -> str:
    body = _b64(json.dumps({"id": user_id, "exp": int(time.time()) + ttl}).encode())
    sig = hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_token(token):
    """Returns user id or None. Token only carries the id; role/name always
    come fresh from the database, so a stale token can never grant access."""
    try:
        body, sig = str(token).split(".", 1)
        good = hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            return None
        data = json.loads(_unb64(body))
        if int(data["exp"]) < time.time():
            return None
        return data["id"]
    except Exception:
        return None


def current_user():
    return st.session_state.get("user")


def _public(profile: dict, email: str = None) -> dict:
    return {
        "id": profile["id"],
        "name": profile.get("name") or "User",
        "role": profile["role"],
        "phone": profile.get("phone"),
        "email": email,
    }


def _load_user(user_id: str, email: str = None) -> Result:
    """Profile + duty rules. Every refusal says exactly why."""
    res = profiles.get_any(user_id)
    if not res.ok:
        return Result(False, error=f"Could not read profile ({res.error})", where="auth.load")
    profile = res.first
    if not profile:
        return fail("Login is correct but no profile exists for this user. "
                    "Owner must add it (Users → Auth UUID: %s)." % user_id, "auth.load")
    if not profile.get("is_active"):
        return fail("This user is switched off (inactive). Ask the owner.", "auth.load")
    if profile.get("role") not in ("owner", "manager", "salesman"):
        return fail(f"Profile has an unknown role: {profile.get('role')!r}.", "auth.load")
    if profile["role"] == "salesman":
        duty = shifts.active_for(user_id)
        if not duty.ok:
            return Result(False, error=f"Could not check duty ({duty.error})", where="auth.load")
        if not duty.first:
            return fail("No active duty. Manager must start your duty first.", "auth.load")
    return ok(_public(profile, email), "auth.load")


def login(email: str, password: str) -> Result:
    email = (email or "").strip().lower()
    if not email or not password:
        return fail("Email and password are required.", "auth.login")

    locked = st.session_state.get("_locked_until", 0)
    if locked > time.time():
        return fail("Too many wrong attempts. Wait a minute and try again.", "auth.login")

    try:
        response = auth_client().auth.sign_in_with_password({"email": email, "password": password})
        auth_user = response.user
    except Exception as exc:
        fails = st.session_state.get("_fails", 0) + 1
        st.session_state["_fails"] = fails
        if fails >= 5:
            st.session_state["_locked_until"] = time.time() + 60
            st.session_state["_fails"] = 0
        message = getattr(exc, "message", None) or str(exc) or type(exc).__name__
        log.warning("auth.login: Supabase refused sign-in for %s: %s", email, message)
        return Result(False, error=f"Supabase sign-in failed: {message}", where="auth.login")

    if not auth_user:
        return fail("Supabase returned no user.", "auth.login")

    st.session_state["_fails"] = 0
    result = _load_user(auth_user.id, email)
    if result.ok:
        st.session_state["user"] = result.data
        st.query_params[PARAM] = make_token(result.data["id"])
        log.info("auth.login: %s (%s) logged in", result.data["name"], result.data["role"])
    return result


def restore() -> Result:
    """Called on every run when nobody is logged in: use ?s=<token> if present."""
    token = st.query_params.get(PARAM)
    if not token:
        return Result(False, error=None, where="auth.restore")
    user_id = read_token(token)
    if not user_id:
        st.query_params.pop(PARAM, None)
        return Result(False, error="Your session expired. Please log in again.", where="auth.restore")
    result = _load_user(user_id)
    if result.ok:
        st.session_state["user"] = result.data
    else:
        st.query_params.pop(PARAM, None)
    return result


def logout():
    user = st.session_state.get("user")
    if user:
        log.info("auth.logout: %s", user.get("name"))
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.pop(PARAM, None)
    if not config.has_service_key():
        try:
            auth_client().auth.sign_out()
        except Exception:
            pass
