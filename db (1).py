"""Settings, Supabase clients, time aur common error."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
from supabase import Client, create_client

IST = ZoneInfo("Asia/Kolkata")
FUEL_TYPES = ["petrol", "diesel", "premium_petrol", "premium_diesel"]
FUEL_LABELS = {
    "petrol": "Petrol", "diesel": "Diesel",
    "premium_petrol": "Premium Petrol", "premium_diesel": "Premium Diesel",
}
ROLES = ["owner", "manager", "salesman"]
ROLE_LABELS = {"owner": "Owner", "manager": "Manager", "salesman": "Salesman"}


class AppError(Exception):
    """User ko dikhane layak error (Hinglish message)."""


def supabase_url() -> str | None:
    """'https://x.supabase.co/rest/v1/' jaisa URL bhi chal jaye — sirf project ka address rakho."""
    url = setting("SUPABASE_URL")
    if not url:
        return None
    url = url.strip().rstrip("/")
    for tail in ("/rest/v1", "/auth/v1"):
        if url.endswith(tail):
            url = url[: -len(tail)]
    return url.rstrip("/")


def setting(name: str, default=None):
    value = os.getenv(name)
    if value and value.strip():
        return value.strip()
    try:
        value = st.secrets.get(name)
        if value and str(value).strip():
            return str(value).strip()
    except Exception:
        pass
    return default


@st.cache_resource
def db() -> Client:
    """Server-side data client (service key). Browser tak kabhi nahi jaata."""
    url, key = supabase_url(), setting("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL aur SUPABASE_SERVICE_KEY secrets mein daalein.")
    return create_client(url, key)


def auth_client() -> Client:
    """Har login ke liye naya client — ek user ka session dusre se mix na ho."""
    url, key = supabase_url(), setting("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL aur SUPABASE_ANON_KEY secrets mein daalein.")
    return create_client(url, key)


def now_ist() -> str:
    return datetime.now(IST).isoformat()


def today_ist() -> str:
    return datetime.now(IST).date().isoformat()


def one(result):
    data = getattr(result, "data", None) or []
    return data[0] if data else None


def rows(result):
    return getattr(result, "data", None) or []


def audit(action: str, user_id=None, details: dict | None = None):
    """Zaroori badlavon ka log. Fail ho to kaam nahi rukta."""
    try:
        db().table("audit_log").insert({
            "action": action,
            "user_id": user_id,
            "details": details or {},
            "created_at": now_ist(),
        }).execute()
    except Exception as exc:
        print("audit_log failed:", exc)
