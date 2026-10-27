"""Users = Supabase Auth (login) + profiles table (naam, role, active)."""
from core.db import ROLES, AppError, audit, db, one, rows, setting

LOGIN_DOMAIN = setting("LOGIN_DOMAIN", "pump.local")


def login_to_email(login: str) -> str:
    """Salesman ko email ki zaroorat nahi: 'ramesh' -> 'ramesh@pump.local'."""
    login = (login or "").strip().lower()
    return login if "@" in login else f"{login}@{LOGIN_DOMAIN}"


def get_profile(user_id):
    if not user_id:
        return None
    return one(db().table("profiles").select("*").eq("id", user_id).limit(1).execute())


def list_profiles(role=None, active_only=False):
    q = db().table("profiles").select("*")
    if role:
        q = q.eq("role", role)
    if active_only:
        q = q.eq("is_active", True)
    return rows(q.order("name").execute())


def active_owner_count() -> int:
    return len(list_profiles(role="owner", active_only=True))


def create_user(name, login, password, role, phone, created_by):
    name, login = (name or "").strip(), (login or "").strip().lower()
    if not name or not login:
        raise AppError("Name and login ID are required.")
    if role not in ROLES:
        raise AppError("Invalid role.")
    if len(password or "") < 6:
        raise AppError("Password must be at least 6 characters.")

    email = login_to_email(login)
    try:
        res = db().auth.admin.create_user({"email": email, "password": password, "email_confirm": True})
    except Exception as exc:
        msg = str(exc)
        if "already" in msg.lower() or "registered" in msg.lower():
            raise AppError("This login ID already exists.")
        raise AppError(f"Could not create login: {msg}")

    uid = res.user.id
    try:
        db().table("profiles").upsert({
            "id": uid, "name": name, "role": role,
            "phone": (phone or "").strip() or None, "is_active": True, "login": login,
        }, on_conflict="id").execute()
    except Exception as exc:
        # Aadha kaam na rahe: profile fail hua to login bhi hata do.
        try:
            db().auth.admin.delete_user(uid)
        except Exception:
            pass
        raise AppError(f"Could not save profile: {exc}")

    audit("user_created", created_by, {"user": uid, "role": role, "login": login})
    return uid


def update_user(user_id, by, *, role=None, is_active=None, name=None, phone=None):
    current = get_profile(user_id)
    if not current:
        raise AppError("User not found.")

    is_last_owner = current["role"] == "owner" and current.get("is_active") and active_owner_count() <= 1
    if is_last_owner and ((role and role != "owner") or is_active is False):
        raise AppError("This is the only active Owner — role/status cannot be changed.")
    if user_id == by and is_active is False:
        raise AppError("You cannot deactivate your own account.")
    if role and role not in ROLES:
        raise AppError("Invalid role.")

    fields = {k: v for k, v in {"role": role, "is_active": is_active, "name": name,
                                "phone": phone}.items() if v is not None}
    if fields:
        db().table("profiles").update(fields).eq("id", user_id).execute()
        audit("user_updated", by, {"user": user_id, **fields})


def reset_password(user_id, new_password, by):
    if len(new_password or "") < 6:
        raise AppError("Password must be at least 6 characters.")
    try:
        db().auth.admin.update_user_by_id(user_id, {"password": new_password})
    except Exception as exc:
        raise AppError(f"Could not change password: {exc}")
    audit("password_reset", by, {"user": user_id})
