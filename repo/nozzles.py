"""Nozzle setup. Meter reading sirf closing/testing se badhti hai; haath se sudhar sirf Owner, kaaran ke saath."""
from core.calc import D, q2, to_json
from core.db import FUEL_TYPES, AppError, audit, db, now_ist, one, rows


def list_nozzles(active_only=False):
    q = db().table("nozzles").select("*")
    if active_only:
        q = q.eq("is_active", True)
    return rows(q.order("nozzle_name").execute())


def get(nozzle_id):
    return one(db().table("nozzles").select("*").eq("id", nozzle_id).limit(1).execute())


def active_assignment(nozzle_id):
    return one(db().table("shift_assignments").select("*").eq("nozzle_id", nozzle_id)
               .eq("is_active", True).limit(1).execute())


def create(name, fuel_type, reading, by):
    name = (name or "").strip()
    if not name:
        raise AppError("Please enter the nozzle name.")
    if fuel_type not in FUEL_TYPES:
        raise AppError("Invalid fuel type.")
    if D(reading) < 0:
        raise AppError("Meter reading cannot be negative.")
    if any(n["nozzle_name"].strip().lower() == name.lower() for n in list_nozzles()):
        raise AppError("A nozzle with this name already exists.")
    db().table("nozzles").insert({
        "nozzle_name": name, "fuel_type": fuel_type,
        "current_reading": to_json(reading), "is_active": True, "created_at": now_ist(),
    }).execute()
    audit("nozzle_created", by, {"name": name, "fuel_type": fuel_type, "reading": str(q2(reading))})


def set_active(nozzle_id, active: bool, by):
    if not active and active_assignment(nozzle_id):
        raise AppError("This nozzle is assigned to an active shift. Record its closing reading first.")
    db().table("nozzles").update({"is_active": active}).eq("id", nozzle_id).execute()
    audit("nozzle_active" if active else "nozzle_inactive", by, {"nozzle": nozzle_id})


def correct_reading(nozzle_id, new_reading, reason, by):
    """Meter repair/reset jaisi haalat ke liye. Duty mein ho to nahi."""
    reason = (reason or "").strip()
    if not reason:
        raise AppError("Please enter a reason.")
    if D(new_reading) < 0:
        raise AppError("Meter reading cannot be negative.")
    if active_assignment(nozzle_id):
        raise AppError("This nozzle is assigned to an active shift. Record its closing reading first.")
    old = get(nozzle_id)
    db().table("nozzles").update({"current_reading": to_json(new_reading)}).eq("id", nozzle_id).execute()
    audit("nozzle_reading_corrected", by, {"nozzle": nozzle_id, "old": (old or {}).get("current_reading"),
                                           "new": str(q2(new_reading)), "reason": reason})
