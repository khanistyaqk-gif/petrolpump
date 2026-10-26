"""One place that reads settings. Nothing else calls os.getenv / st.secrets."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # dotenv is optional
    pass

# name -> (required, what it is for)
SETTINGS = {
    "SUPABASE_URL": (True, "Supabase project URL"),
    "SUPABASE_ANON_KEY": (True, "Public key, used only for email/password login"),
    "SUPABASE_SERVICE_KEY": (False, "Server key for all data queries (recommended)"),
    "APP_SESSION_SECRET": (False, "32+ random chars; keeps logins after restart"),
}


def get(name: str):
    value = os.getenv(name)
    if value and value.strip():
        return value.strip()
    try:
        import streamlit as st
        value = st.secrets.get(name)
        if value and str(value).strip():
            return str(value).strip()
    except Exception:
        pass
    return None


def has_service_key() -> bool:
    return bool(get("SUPABASE_SERVICE_KEY"))


def mask(value):
    if not value:
        return "(not set)"
    return value[:4] + "…" + value[-3:] if len(value) > 10 else "set"


def check():
    """List of dicts: name, required, ok, shown, purpose."""
    rows = []
    for name, (required, purpose) in SETTINGS.items():
        value = get(name)
        rows.append({
            "name": name,
            "required": required,
            "ok": bool(value) or not required,
            "value": mask(value) if "KEY" in name or "SECRET" in name else (value or "(not set)"),
            "purpose": purpose,
        })
    return rows


def missing_required():
    return [r["name"] for r in check() if r["required"] and r["value"] == "(not set)"]
