from core.db import run


def get_any(user_id):
    return run("profiles.get_any", lambda c: c.table("profiles").select("*").eq("id", user_id).limit(1).execute())


def list_all():
    return run("profiles.list_all", lambda c: c.table("profiles").select("*").order("name").execute())


def list_active_salesmen():
    return run("profiles.list_active_salesmen", lambda c: c.table("profiles").select("*")
               .eq("role", "salesman").eq("is_active", True).order("name").execute())


def upsert(user_id, name, role, phone=None, is_active=True):
    payload = {"id": user_id, "name": name, "role": role, "phone": phone or None, "is_active": is_active}
    return run("profiles.upsert", lambda c: c.table("profiles").upsert(payload).execute())


def set_active(user_id, active: bool):
    return run("profiles.set_active", lambda c: c.table("profiles").update({"is_active": active}).eq("id", user_id).execute())
