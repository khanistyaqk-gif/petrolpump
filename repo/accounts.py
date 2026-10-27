"""Bank accounts aur oil companies (Owner setup)."""
from core.db import AppError, audit, db, one, rows


def banks(active_only=True):
    q = db().table("bank_accounts").select("*")
    if active_only:
        q = q.eq("is_active", True)
    return rows(q.order("name").execute())


def oil_companies(active_only=True):
    q = db().table("oil_companies").select("*")
    if active_only:
        q = q.eq("is_active", True)
    return rows(q.order("name").execute())


def _add(table, name, by):
    name = (name or "").strip()
    if not name:
        raise AppError("Please enter a name.")
    if any(r["name"].lower() == name.lower() for r in rows(db().table(table).select("name").execute())):
        raise AppError("This name already exists.")
    db().table(table).insert({"name": name}).execute()
    audit(f"{table}_added", by, {"name": name})


def add_bank(name, by):
    _add("bank_accounts", name, by)


def add_oil_company(name, by):
    _add("oil_companies", name, by)


def set_active(table, row_id, active, by):
    if table not in ("bank_accounts", "oil_companies"):
        raise AppError("Invalid table.")
    db().table(table).update({"is_active": bool(active)}).eq("id", row_id).execute()
    audit(f"{table}_active", by, {"id": row_id, "active": bool(active)})


def name_maps():
    return ({b["id"]: b["name"] for b in banks(False)}, {o["id"]: o["name"] for o in oil_companies(False)})


def get_bank(bank_id):
    return one(db().table("bank_accounts").select("*").eq("id", bank_id).limit(1).execute())


def rename(table, row_id, name, by):
    if table not in ("bank_accounts", "oil_companies"):
        raise AppError("Invalid table.")
    name = (name or "").strip()
    if not name:
        raise AppError("Please enter a name.")
    if any(r["id"] != row_id and r["name"].lower() == name.lower()
           for r in rows(db().table(table).select("id, name").execute())):
        raise AppError("This name already exists.")
    db().table(table).update({"name": name}).eq("id", row_id).execute()
    audit(f"{table}_renamed", by, {"id": row_id, "name": name})
