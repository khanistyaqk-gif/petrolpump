"""
Duty (shifts) aur nozzle allotment (shift_assignments).

Rules (LOGIC.md 2):
- Duty Manager shuru karta hai; ek salesman ki ek hi chalu duty.
- Ek nozzle ek waqt mein ek hi duty mein (DB unique index bhi).
- Opening reading apne aap = nozzle ki current reading.
- Closing save hote hi nozzle free ho jaata hai (agli duty ki opening = closing).
- Duty settlement approve hone par apne aap band hoti hai.
"""
from core.calc import D
from core.db import AppError, audit, db, now_ist, one, rows, today_ist


def active_duty_for(salesman_id):
    return one(db().table("shifts").select("*").eq("salesman_id", salesman_id)
               .eq("is_active", True).order("id", desc=True).limit(1).execute())


def get(shift_id):
    return one(db().table("shifts").select("*").eq("id", shift_id).limit(1).execute())


def active_duties():
    return rows(db().table("shifts").select("*, profiles:salesman_id(id, name, phone)")
                .eq("is_active", True).order("id", desc=True).execute())


def assignments(shift_id, active_only=False):
    q = db().table("shift_assignments").select("*, nozzles:nozzle_id(*)").eq("shift_id", shift_id)
    if active_only:
        q = q.eq("is_active", True)
    return rows(q.order("id").execute())


def free_nozzles():
    busy = {r["nozzle_id"] for r in rows(db().table("shift_assignments").select("nozzle_id")
                                         .eq("is_active", True).execute())}
    nozzles = rows(db().table("nozzles").select("*").eq("is_active", True).order("nozzle_name").execute())
    return [n for n in nozzles if n["id"] not in busy]


def start_duty(salesman_id, manager_id):
    profile = one(db().table("profiles").select("*").eq("id", salesman_id).limit(1).execute())
    if not profile or not profile.get("is_active") or profile.get("role") != "salesman":
        raise AppError("Salesman nahi mila ya account band hai.")
    if active_duty_for(salesman_id):
        raise AppError(f"{profile['name']} ki duty pehle se chalu hai.")
    try:
        res = db().table("shifts").insert({
            "salesman_id": salesman_id, "started_by": manager_id, "is_active": True,
            "date": today_ist(), "started_at": now_ist(),
        }).execute()
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise AppError("Is salesman ki duty pehle se chalu hai.")
        raise
    audit("duty_started", manager_id, {"salesman": salesman_id})
    return one(res)


def _settlement_status(shift_id):
    s = one(db().table("settlements").select("status, breakup_submitted_at")
            .eq("shift_id", shift_id).limit(1).execute())
    return s


def assign_nozzle(shift_id, nozzle_id, manager_id):
    shift = get(shift_id)
    if not shift or not shift.get("is_active"):
        raise AppError("Chalu duty nahi mili.")
    s = _settlement_status(shift_id)
    if s and (s.get("breakup_submitted_at") or s.get("status") in ("hold", "approved")):
        raise AppError("Is duty ka hisaab jama ho chuka hai, ab naya nozzle nahi jod sakte.")

    nozzle = one(db().table("nozzles").select("*").eq("id", nozzle_id).limit(1).execute())
    if not nozzle or not nozzle.get("is_active"):
        raise AppError("Nozzle nahi mila ya band hai.")
    busy = one(db().table("shift_assignments").select("id").eq("nozzle_id", nozzle_id)
               .eq("is_active", True).limit(1).execute())
    if busy:
        raise AppError(f"{nozzle['nozzle_name']} pehle se kisi aur duty mein hai.")

    try:
        db().table("shift_assignments").insert({
            "shift_id": shift_id, "salesman_id": shift["salesman_id"], "nozzle_id": nozzle_id,
            "opening_reading": nozzle.get("current_reading") or 0,
            "is_active": True, "assigned_by": manager_id, "created_at": now_ist(),
        }).execute()
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "uniq" in str(exc).lower():
            raise AppError(f"{nozzle['nozzle_name']} abhi-abhi kisi aur ko allot hua.")
        raise
    audit("nozzle_assigned", manager_id, {"shift": shift_id, "nozzle": nozzle_id,
                                          "opening": nozzle.get("current_reading")})


def remove_assignment(assignment_id, manager_id):
    """Galti se allot hua nozzle hatana. Sirf tab jab us par koi sale/testing nahi hui."""
    a = one(db().table("shift_assignments").select("*, nozzles:nozzle_id(*)")
            .eq("id", assignment_id).limit(1).execute())
    if not a or not a.get("is_active"):
        raise AppError("Allotment nahi mila.")
    sales = rows(db().table("sale_entries").select("id, status").eq("shift_id", a["shift_id"])
                 .eq("nozzle_id", a["nozzle_id"]).execute())
    if any((r.get("status") or "pending") not in ("rejected", "cancelled") for r in sales):
        raise AppError("Is nozzle par sale entry ho chuki hai. Hatane ke bajaye closing karein.")
    nozzle = a.get("nozzles") or {}
    if D(nozzle.get("current_reading")) != D(a.get("opening_reading")):
        raise AppError("Is nozzle ki reading badal chuki hai (testing?). Hatane ke bajaye closing karein.")
    db().table("shift_assignments").update({"is_active": False, "ended_at": now_ist()}) \
        .eq("id", assignment_id).execute()
    audit("nozzle_unassigned", manager_id, {"assignment": assignment_id})


def end_empty_duty(shift_id, manager_id):
    """Sirf aisi duty band karna jisme koi nozzle/sale nahi (galti se shuru hui)."""
    if assignments(shift_id, active_only=True):
        raise AppError("Is duty mein nozzle allot hain. Pehle closing karein, phir settlement approve karein.")
    live = [r for r in rows(db().table("sale_entries").select("status").eq("shift_id", shift_id).execute())
            if (r.get("status") or "pending") not in ("rejected", "cancelled")]
    s = _settlement_status(shift_id)
    if live or (s and s.get("status") != "approved"):
        raise AppError("Is duty ka hisaab baaki hai. Settlement approve karne par duty apne aap band hogi.")
    db().table("shifts").update({"is_active": False, "ended_at": now_ist()}).eq("id", shift_id).execute()
    audit("duty_ended_empty", manager_id, {"shift": shift_id})
