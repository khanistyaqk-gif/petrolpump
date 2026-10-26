from core.db import fail, run
from core.timeutil import now_ist, today_ist


def active_for(salesman_id):
    return run("shifts.active_for", lambda c: c.table("shifts").select("*")
               .eq("salesman_id", salesman_id).eq("is_active", True).order("id", desc=True).limit(1).execute())


def get(shift_id):
    return run("shifts.get", lambda c: c.table("shifts").select("*").eq("id", shift_id).limit(1).execute())


def list_active():
    return run("shifts.list_active", lambda c: c.table("shifts").select("*").eq("is_active", True).order("id").execute())


def history(limit=50):
    return run("shifts.history", lambda c: c.table("shifts").select("*").order("id", desc=True).limit(limit).execute())


def shift_date(shift: dict) -> str:
    return (shift or {}).get("date") or today_ist()


def start(salesman_id, started_by):
    existing = active_for(salesman_id)
    if not existing.ok:
        return existing
    if existing.first:
        return fail("This salesman already has an active duty.", "shifts.start")
    payload = {"salesman_id": salesman_id, "started_by": started_by, "is_active": True}
    return run("shifts.start", lambda c: c.table("shifts").insert(payload).execute())


def end(shift_id):
    """Ends the duty and its nozzle assignments. Stops at the first failure
    and says which step failed."""
    r1 = run("shifts.end.assignments", lambda c: c.table("shift_assignments")
             .update({"is_active": False, "ended_at": now_ist()}).eq("shift_id", shift_id).eq("is_active", True).execute())
    if not r1.ok:
        return r1
    return run("shifts.end.shift", lambda c: c.table("shifts")
               .update({"is_active": False, "ended_at": now_ist()}).eq("id", shift_id).execute())
