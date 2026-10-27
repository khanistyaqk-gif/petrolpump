"""
Salesman ki sale entry (LOGIC.md 4).
- Sirf apni chalu duty ke nozzle par.
- Rate = duty ki tarikh ka rate, entry ke saath lock.
- Hisaab jama (breakup submit) hone ke baad entry nahi jud/kat sakti — jab tak Manager reopen na kare.
"""
from core.calc import ZERO, CalcError, D, q2, sale_amount, to_json
from core.db import AppError, audit, db, now_ist, one, rows, today_ist
from repo import duties, rates

LIVE = lambda r: (r.get("status") or "pending") not in ("rejected", "cancelled")  # noqa: E731


def _editable(shift_id):
    s = one(db().table("settlements").select("status, breakup_submitted_at")
            .eq("shift_id", shift_id).limit(1).execute())
    if not s:
        return True
    if s.get("status") in ("hold", "approved"):
        return False
    return not s.get("breakup_submitted_at")


def duty_nozzles(shift_id, salesman_id):
    """Is duty ke saare nozzle (closing ke baad bhi), taaki reopen par entry sudhar sake."""
    return [a for a in duties.assignments(shift_id)
            if a.get("salesman_id") == salesman_id
            and (a.get("is_active") or a.get("closing_reading") is not None)]   # hataya gaya nozzle nahi


def live_entries(shift_id, salesman_id):
    data = rows(db().table("sale_entries").select("*, nozzles:nozzle_id(nozzle_name)")
                .eq("shift_id", shift_id).eq("salesman_id", salesman_id)
                .order("entry_time", desc=True).execute())
    return [r for r in data if LIVE(r)]


def entries_total(shift_id, salesman_id):
    return q2(sum((D(r.get("amount")) for r in live_entries(shift_id, salesman_id)), ZERO))


def add_entry(salesman_id, nozzle_id, liters):
    duty = duties.active_duty_for(salesman_id)
    if not duty:
        raise AppError("You do not have an active shift.")
    if not _editable(duty["id"]):
        raise AppError("Your settlement has been submitted. Ask the Manager to return it if you need to make changes.")

    assignment = next((a for a in duty_nozzles(duty["id"], salesman_id) if a["nozzle_id"] == nozzle_id), None)
    if not assignment:
        raise AppError("This nozzle is not assigned to your shift.")
    if any(e["nozzle_id"] == nozzle_id for e in live_entries(duty["id"], salesman_id)):
        name = (assignment.get("nozzles") or {}).get("nozzle_name") or "this nozzle"
        raise AppError(f"An entry for {name} already exists. Use Edit or Cancel on that entry to change it.")
    fuel = (assignment.get("nozzles") or {}).get("fuel_type")
    shift_date = duty.get("date") or today_ist()
    rate_row = rates.rate_row_for(fuel, shift_date)
    if not rate_row or D(rate_row.get("price_per_liter")) <= 0:
        raise AppError(f"No {fuel} rate is set for {shift_date}. Please ask the Owner to set the rate.")
    rate = q2(rate_row["price_per_liter"])
    try:
        amount = sale_amount(liters, rate)
    except CalcError as exc:
        raise AppError(str(exc))

    try:
        _insert_entry(duty, nozzle_id, salesman_id, shift_date, fuel, liters, rate, rate_row, amount)
    except Exception as exc:
        if "uniq_live_sale_per_nozzle" in str(exc) or "duplicate" in str(exc).lower():
            raise AppError("An entry for this nozzle already exists.")
        raise
    return amount


def _insert_entry(duty, nozzle_id, salesman_id, shift_date, fuel, liters, rate, rate_row, amount):
    db().table("sale_entries").insert({
        "shift_id": duty["id"], "nozzle_id": nozzle_id, "salesman_id": salesman_id,
        "date": shift_date, "entry_time": now_ist(), "fuel_type": fuel,
        "liters": to_json(liters), "rate": to_json(rate), "rate_date": shift_date,
        "rate_snapshot": {"fuel_type": fuel, "locked_rate": str(rate), "rate_date": rate_row.get("effective_from"),
                          "rate_id": rate_row.get("id"), "source": "fuel_rates"},
        "amount": to_json(amount), "status": "pending", "created_at": now_ist(),
    }).execute()


def _own_pending(entry_id, salesman_id):
    e = one(db().table("sale_entries").select("*").eq("id", entry_id).limit(1).execute())
    if not e or e.get("salesman_id") != salesman_id or not LIVE(e):
        raise AppError("Entry not found.")
    if (e.get("status") or "pending") != "pending" or not _editable(e["shift_id"]):
        raise AppError("Your settlement has been submitted. Ask the Manager to return it if you need to make changes.")
    return e


def edit_entry(entry_id, salesman_id, liters):
    """Litre badlo. Rate wahi rahega jo entry ke waqt laga tha."""
    e = _own_pending(entry_id, salesman_id)
    try:
        amount = sale_amount(liters, e["rate"])
    except CalcError as exc:
        raise AppError(str(exc))
    db().table("sale_entries").update({"liters": to_json(liters), "amount": to_json(amount)}) \
        .eq("id", entry_id).eq("status", "pending").execute()
    audit("sale_edited", salesman_id, {"entry": entry_id, "old_liters": e.get("liters"), "new_liters": str(q2(liters))})
    return amount


def cancel_entry(entry_id, salesman_id):
    e = _own_pending(entry_id, salesman_id)
    db().table("sale_entries").update({"status": "cancelled"}).eq("id", entry_id).execute()
    audit("sale_cancelled", salesman_id, {"entry": entry_id, "liters": e.get("liters")})


def history(salesman_id, limit=200):
    return rows(db().table("sale_entries").select("*, nozzles:nozzle_id(nozzle_name)")
                .eq("salesman_id", salesman_id).order("entry_time", desc=True).limit(limit).execute())
