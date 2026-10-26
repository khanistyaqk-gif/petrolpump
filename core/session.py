"""
Refresh ke baad login bana rahe — signed token (HMAC) browser localStorage/cookie mein.
Purane app ka tested tareeka, saaf karke. Token APP_SESSION_SECRET se sign hota hai.

Dhyan: token page URL mein bhi aata hai (?s=...). Login ke baad URL ya screenshot share na karein.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

import streamlit as st
import streamlit.components.v1 as components

from core.db import setting

PARAM = "s"
STORE_KEY = "pump_v2_session"
TTL_SECONDS = 7 * 24 * 60 * 60
_FALLBACK_SECRET = secrets.token_hex(32)


def _key() -> bytes:
    secret = setting("APP_SESSION_SECRET")
    if not secret or len(secret) < 16:
        secret = _FALLBACK_SECRET   # secure, par restart par sab logout
    return secret.encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload: str) -> str:
    return hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(user_id: str) -> str:
    payload = _b64(json.dumps({"id": user_id, "exp": int(time.time()) + TTL_SECONDS}).encode())
    return f"{payload}.{_sign(payload)}"


def read_token(token) -> str | None:
    """Sahi aur valid token ho to user_id, warna None."""
    try:
        payload, sig = str(token).split(".", 1)
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        data = json.loads(_unb64(payload))
        if int(data.get("exp", 0)) < time.time():
            return None
        return data.get("id")
    except Exception:
        return None


def _bridge(token: str = "", clear: bool = False):
    components.html(
        f"""<script>
(function(){{
  const W = window.parent || window, KEY = {json.dumps(STORE_KEY)}, P = {json.dumps(PARAM)};
  const TOKEN = {json.dumps(token)}, CLEAR = {"true" if clear else "false"};
  const ck = (v, age) => {{ try {{ W.document.cookie = KEY + '=' + encodeURIComponent(v) + '; path=/; max-age=' + age + '; SameSite=Lax'; }} catch(e){{}} }};
  const getCk = () => {{ try {{ for (const p of (W.document.cookie||'').split(';')) {{ const t = p.trim(); if (t.startsWith(KEY+'=')) return decodeURIComponent(t.slice(KEY.length+1)); }} }} catch(e){{}} return ''; }};
  if (CLEAR) {{
    try {{ W.localStorage.removeItem(KEY); }} catch(e){{}} ck('', 0);
    const u = new URL(W.location.href); if (u.searchParams.has(P)) {{ u.searchParams.delete(P); W.history.replaceState(null,'',u.toString()); }}
    return;
  }}
  if (TOKEN) {{ try {{ W.localStorage.setItem(KEY, TOKEN); }} catch(e){{}} ck(TOKEN, {TTL_SECONDS}); return; }}
  let saved = ''; try {{ saved = W.localStorage.getItem(KEY) || ''; }} catch(e){{}} if (!saved) saved = getCk();
  if (saved) {{ const u = new URL(W.location.href); if (!u.searchParams.get(P)) {{ u.searchParams.set(P, saved); W.location.replace(u.toString()); }} }}
}})();
</script>""",
        height=0,
    )


def save(user_id: str):
    st.session_state.pop("_logged_out", None)
    token = make_token(user_id)
    st.session_state["_token"] = token
    st.query_params[PARAM] = token
    _bridge(token=token)


def clear():
    st.session_state.pop("_token", None)
    st.session_state.pop("user", None)
    if PARAM in st.query_params:
        del st.query_params[PARAM]
    _bridge(clear=True)


def keep():
    """Har run par token browser mein save rahe (login ke turant baad rerun se bridge chhoot sakta hai)."""
    token = st.session_state.get("_token")
    if token:
        if st.query_params.get(PARAM) != token:
            st.query_params[PARAM] = token
        _bridge(token=token)


def restore_user_id() -> str | None:
    """Session ya URL token se user_id. Kuch na mile to browser se token wapas laane ki koshish."""
    if st.session_state.get("_logged_out"):
        # Logout ke baad browser mein bacha token wapas na aaye — saaf karte raho.
        if PARAM in st.query_params:
            del st.query_params[PARAM]
        _bridge(clear=True)
        return None
    token = st.session_state.get("_token") or st.query_params.get(PARAM)
    if not token:
        _bridge()
        return None
    user_id = read_token(token)
    if not user_id:
        clear()
        return None
    st.session_state["_token"] = token
    if st.query_params.get(PARAM) != token:
        st.query_params[PARAM] = token
    return user_id
