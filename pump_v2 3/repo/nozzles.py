from core.db import fail, run
from core.schema import FUEL_TYPES
from core.timeutil import now_ist


def list_all():
    return run("nozzles.list_all", lambda c: c.table("nozzles").select("*").order("id").execute())


def get(nozzle_id):
    return run("nozzles.get", lambda c: c.table("nozzles").select("*").eq("id", nozzle_id).limit(1).execute())


def create(name, fuel_type, reading, created_by):
    name = (name or "").strip()
    if not name:
        return fail("Nozzle name is required.", "nozzles.create")
    if fuel_type not in FUEL_TYPES:
        return fail(f"Unknown fuel type: {fuel_type}", "nozzles.create")
    payload = {"nozzle_name": name, "fuel_type": fuel_type, "current_reading": float(reading or 0),
               "is_active": True, "created_by": created_by, "created_at": now_ist()}
    return run("nozzles.create", lambda c: c.table("nozzles").insert(payload).execute())


def set_active(nozzle_id, active: bool):
    return run("nozzles.set_active", lambda c: c.table("nozzles").update({"is_active": active}).eq("id", nozzle_id).execute())


def set_reading(nozzle_id, reading):
    return run("nozzles.set_reading", lambda c: c.table("nozzles")
               .update({"current_reading": float(reading)}).eq("id", nozzle_id).execute())
