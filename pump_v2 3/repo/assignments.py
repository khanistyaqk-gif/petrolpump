from core.db import fail, ok, run
from core.timeutil import now_ist
from repo import nozzles, shifts


def for_shift(shift_id, active_only=True):
    def build(c):
        q = c.table("shift_assignments").select("*").eq("shift_id", shift_id)
        if active_only:
            q = q.eq("is_active", True)
        return q.order("id").execute()
    res = run("assignments.for_shift", build)
    if not res.ok or not res.rows:
        return res
    noz = nozzles.list_all()
    if not noz.ok:
        return noz
    by_id = {n["id"]: n for n in noz.rows}
    merged = []
    for row in res.rows:
        n = by_id.get(row["nozzle_id"]) or {}
        merged.append({**row, "nozzle_name": n.get("nozzle_name"), "fuel_type": n.get("fuel_type"),
                       "nozzle_active": n.get("is_active", True)})
    return ok(merged, "assignments.for_shift")


def active_for_nozzle(nozzle_id):
    return run("assignments.active_for_nozzle", lambda c: c.table("shift_assignments").select("*")
               .eq("nozzle_id", nozzle_id).eq("is_active", True).execute())


def assign(shift_id, nozzle_id, assigned_by):
    shift = shifts.get(shift_id)
    if not shift.ok:
        return shift
    if not shift.first or not shift.first.get("is_active"):
        return fail("Duty is not active.", "assignments.assign")
    noz = nozzles.get(nozzle_id)
    if not noz.ok:
        return noz
    nozzle = noz.first
    if not nozzle:
        return fail("Nozzle not found.", "assignments.assign")
    if not nozzle.get("is_active", True):
        return fail("Nozzle is inactive.", "assignments.assign")
    busy = active_for_nozzle(nozzle_id)
    if not busy.ok:
        return busy
    if busy.first:
        return fail("This nozzle is already assigned to another active duty.", "assignments.assign")
    payload = {"shift_id": shift_id, "salesman_id": shift.first["salesman_id"], "nozzle_id": nozzle_id,
               "opening_reading": float(nozzle.get("current_reading") or 0), "is_active": True,
               "assigned_by": assigned_by, "created_at": now_ist()}
    return run("assignments.assign", lambda c: c.table("shift_assignments").insert(payload).execute())


def end(assignment_id):
    return run("assignments.end", lambda c: c.table("shift_assignments")
               .update({"is_active": False, "ended_at": now_ist()}).eq("id", assignment_id).execute())
