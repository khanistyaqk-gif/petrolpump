"""
Testing (LOGIC.md 6):
- Testing karte hi nozzle ki meter reading utne litre aage.
- Fuel tank mein wapas -> stock par asar 0.
- Nozzle kisi chalu duty mein ho to testing usi allotment se judti hai.
- Settlement mein testing ALLOTMENT se match hoti hai, tarikh se nahi (R2 fix:
  raat 12 ke baad hui testing bhi sahi duty se minus hogi).
"""
from core.calc import ZERO, D, q2, to_json
from core.db import AppError, audit, db, now_ist, one, rows, today_ist

MAX_TESTING_LITERS = 100   # galti se 1000 type na ho jaye


def create(nozzle_id, liters, remark, by):
    liters = q2(liters)
    if liters <= 0:
        raise AppError("Please enter testing litres.")
    if liters > MAX_TESTING_LITERS:
        raise AppError(f"Testing cannot exceed {MAX_TESTING_LITERS} L. Please check the number.")

    nozzle = one(db().table("nozzles").select("*").eq("id", nozzle_id).limit(1).execute())
    if not nozzle or not nozzle.get("is_active"):
        raise AppError("Nozzle not found or inactive.")

    before = q2(nozzle.get("current_reading"))
    after = q2(before + liters)
    a = one(db().table("shift_assignments").select("id, shift_id, salesman_id")
            .eq("nozzle_id", nozzle_id).eq("is_active", True).limit(1).execute()) or {}

    res = db().table("daily_testing").insert({
        "date": today_ist(), "fuel_type": nozzle["fuel_type"], "nozzle_id": nozzle_id,
        "shift_id": a.get("shift_id"), "assignment_id": a.get("id"), "salesman_id": a.get("salesman_id"),
        "reading_before": to_json(before), "reading_after": to_json(after),
        "testing_liters": to_json(liters), "returned_to_tank": True,
        "remark": (remark or "").strip(), "status": "approved", "tested_by": by, "created_at": now_ist(),
    }).execute()
    row = one(res)
    if not row:
        raise AppError("Testing entry could not be saved.")

    # Reading sirf tab badhao jab beech mein kisi ne na badli ho (do log ek saath testing na kar dein).
    cur = nozzle.get("current_reading")
    q = db().table("nozzles").update({"current_reading": to_json(after)}).eq("id", nozzle_id)
    q = q.eq("current_reading", cur) if cur is not None else q.is_("current_reading", "null")
    upd = q.execute()
    if not rows(upd):
        db().table("daily_testing").delete().eq("id", row["id"]).execute()
        raise AppError("This nozzle was just changed by someone else. Please try again.")

    audit("testing_added", by, {"nozzle": nozzle_id, "liters": str(liters), "assignment": a.get("id")})
    return row


def liters_for_assignment(assignment_id):
    if not assignment_id:
        return ZERO
    data = rows(db().table("daily_testing").select("testing_liters")
                .eq("assignment_id", assignment_id).eq("status", "approved").execute())
    return q2(sum((D(r.get("testing_liters")) for r in data), ZERO))


def list_for_date(on_date):
    return rows(db().table("daily_testing").select("*, nozzles:nozzle_id(nozzle_name)")
                .eq("date", on_date).order("created_at", desc=True).execute())
