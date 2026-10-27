"""
Settlement = ek duty ka poora hisaab (LOGIC.md 5 aur 7).

Flow:
  1. Salesman: payment breakup bhejta hai (cash + paytm + ccms + credit = uski entries ka total).
  2. Manager: closing reading save karta hai -> meter ka hisaab, nozzle free.
  3. Manager: Approve (farak ±₹2 ke andar) / Hold / Reopen.
     Approve database function mein ek transaction se hota hai: ya sab, ya kuch nahi (R10 fix).

Kaun kya likhta hai (ek dusre ka data kabhi overwrite nahi):
  - Salesman: cash/paytm/ccms/credit, entries_total, breakup_submitted_at
  - Manager closing: nozzle_readings, meter_total
"""
from core.calc import (ZERO, CalcError, D, breakup_matches_entries, cash_transfer_expected,
                       credit_limit_exceeded, meter_total, nozzle_closing, q2,
                       settlement_difference, SETTLEMENT_TOLERANCE, to_json, vehicle_allowed)
from core.db import AppError, audit, db, now_ist, one, rows, today_ist
from repo import credit, duties, rates, sales, testing


def for_shift(shift_id):
    return one(db().table("settlements").select("*").eq("shift_id", shift_id).limit(1).execute())


def get(settlement_id):
    return one(db().table("settlements").select("*").eq("id", settlement_id).limit(1).execute())


def closing_saved(s) -> bool:
    return bool(s and s.get("nozzle_readings"))


def difference_of(s):
    if not closing_saved(s):
        return None
    return settlement_difference(s.get("meter_total"), s.get("cash_amount"), s.get("paytm_amount"),
                                 s.get("ccms_amount"), s.get("credit_amount"))


def to_review(statuses=("pending", "hold", "reopened")):
    return rows(db().table("settlements").select("*").in_("status", list(statuses))
                .order("created_at", desc=True).execute())


def approved_on(on_date):
    return rows(db().table("settlements").select("*").eq("status", "approved").eq("date", on_date).execute())


# ======================= Salesman: payment breakup =======================
def submit_breakup(salesman_id, cash, paytm, ccms, credit_items):
    duty = duties.active_duty_for(salesman_id)
    if not duty:
        raise AppError("You do not have an active shift.")
    old = for_shift(duty["id"])
    if old and old.get("status") in ("hold", "approved"):
        raise AppError("This settlement is with the Manager.")
    if old and old.get("breakup_submitted_at"):
        raise AppError("Settlement already submitted. Ask the Manager to return it if you need to make changes.")

    # ---- credit lines check ----
    clean, credit_sum, given_sum, warnings = [], ZERO, ZERO, []
    for i, item in enumerate(credit_items or [], start=1):
        amt, given = q2(item.get("amount")), q2(item.get("cash_given"))
        if amt == 0 and given == 0:
            continue
        if amt < 0 or given < 0:
            raise AppError(f"Credit line {i}: amount cannot be negative.")
        party = credit.get(item.get("party_id"))
        if not party or not party.get("is_active"):
            raise AppError(f"Credit line {i}: party not found or inactive.")
        vehicle = (item.get("vehicle") or "").strip().upper()
        allowed = credit.vehicles_of(party)
        if amt > 0 and allowed and not vehicle_allowed(vehicle, allowed):
            raise AppError(f"{party['name']}: vehicle '{vehicle or '-'}' is not registered for this party.")
        if credit_limit_exceeded(party.get("current_balance"), credit.pending_increase(party["id"]),
                                 amt + given, party.get("credit_limit")):
            warnings.append(f"{party['name']}: credit limit of ₹{q2(party.get('credit_limit'))} will be exceeded.")
        clean.append({**item, "party": party, "amount": amt, "cash_given": given, "vehicle": vehicle})
        credit_sum += amt
        given_sum += given

    entries = sales.entries_total(duty["id"], salesman_id)
    try:
        ok, diff = breakup_matches_entries(entries, cash, paytm, ccms, credit_sum)
        transfer = cash_transfer_expected(cash, given_sum)
    except CalcError as exc:
        raise AppError(str(exc))
    if not ok:
        raise AppError(f"Cash + Paytm + CCMS + Credit does not match your sale entries (₹{entries}). "
                       f"Difference: ₹{diff}.")

    payload = {
        "cash_amount": to_json(cash), "paytm_amount": to_json(paytm), "ccms_amount": to_json(ccms),
        "credit_amount": to_json(credit_sum), "cash_given_to_creditor_amount": to_json(given_sum),
        "cash_transfer_expected": to_json(transfer), "entries_total": to_json(entries),
        "breakup_submitted_at": now_ist(), "status": "pending",
        "manager_note": "Submitted by salesman",
    }
    if closing_saved(old):
        payload["difference"] = to_json(settlement_difference(old.get("meter_total"), cash, paytm, ccms, credit_sum))

    if old:
        db().table("settlements").update(payload).eq("id", old["id"]).execute()
        sid, created_new = old["id"], False
    else:
        res = db().table("settlements").insert({
            **payload, "shift_id": duty["id"], "salesman_id": salesman_id,
            "date": duty.get("date") or today_ist(), "nozzle_readings": [], "meter_total": 0,
            "difference": 0, "created_at": now_ist(),
        }).execute()
        sid, created_new = one(res)["id"], True

    created_txn_ids = []
    try:
        credit.reject_open_for_reference(sid, salesman_id, "Replaced by new submission")
        for item in clean:
            for ttype, amt in (("sale", item["amount"]), ("cash_given", item["cash_given"])):
                if amt > 0:
                    t = credit.add_txn(item["party"]["id"], ttype, amt, sid, item.get("comment"),
                                       item["vehicle"], salesman_id, duty.get("date"))
                    created_txn_ids.append(t["id"])
    except Exception as exc:
        # Aadha hisaab na bache: sab wapas.
        if created_txn_ids:
            db().table("credit_transactions").delete().in_("id", created_txn_ids).execute()
        if created_new:
            db().table("settlements").delete().eq("id", sid).execute()
        else:
            restore = {k: old.get(k) for k in payload}
            db().table("settlements").update(restore).eq("id", sid).execute()
        raise AppError(f"Settlement could not be saved. Please try again. ({exc})")

    return warnings


# ======================= Manager: closing reading =======================
def closing_preview(shift_id, closing_inputs):
    """Save kiye bina hisaab dikhao. Galti ho to CalcError/AppError."""
    shift = duties.get(shift_id)
    if not shift:
        raise AppError("Shift not found.")
    shift_date = shift.get("date") or today_ist()
    result = []
    for a in duties.assignments(shift_id):
        if a.get("salesman_id") != shift["salesman_id"]:
            continue
        first_time = a.get("closing_reading") is None
        if first_time and not a.get("is_active"):
            continue    # galti se allot hua aur hataya gaya
        nozzle = a.get("nozzles") or {}
        name = nozzle.get("nozzle_name") or f"Nozzle {a['nozzle_id']}"
        closing = closing_inputs.get(a["id"])

        if first_time:
            if D(closing) < D(nozzle.get("current_reading")):
                raise AppError(f"{name}: closing ({q2(closing)}) is less than the current meter reading "
                               f"({q2(nozzle.get('current_reading'))}, includes testing).")
        else:
            newer = one(db().table("shift_assignments").select("id").eq("nozzle_id", a["nozzle_id"])
                        .gt("id", a["id"]).limit(1).execute())
            if newer:
                raise AppError(f"{name} has moved to the next shift — its closing reading can no longer be changed.")
            if D(nozzle.get("current_reading")) != D(a.get("closing_reading")):
                raise AppError(f"{name}: the meter changed after closing — please ask the Owner to check.")

        rate = rates.rate_for(nozzle.get("fuel_type"), shift_date)
        try:
            row = nozzle_closing(a.get("opening_reading"), closing, testing.liters_for_assignment(a["id"]),
                                 rate or 0, name)
        except CalcError as exc:
            raise AppError(str(exc))
        result.append({"assignment": a, "nozzle": nozzle, "first_time": first_time, "calc": row,
                       "fuel_type": nozzle.get("fuel_type"), "name": name, "shift_date": shift_date})
    if not result:
        raise AppError("No nozzles are assigned to this shift.")
    return result


def save_closing(shift_id, closing_inputs, manager_id):
    s = for_shift(shift_id)
    if s and s.get("status") == "approved":
        raise AppError("An approved settlement cannot be changed.")
    preview = closing_preview(shift_id, closing_inputs)
    shift = duties.get(shift_id)

    snapshot = []
    for p in preview:
        a, c, nozzle = p["assignment"], p["calc"], p["nozzle"]
        expected_now = nozzle.get("current_reading") if p["first_time"] else a.get("closing_reading")
        q = db().table("nozzles").update({"current_reading": to_json(c["closing"])}).eq("id", a["nozzle_id"])
        q = q.eq("current_reading", expected_now) if expected_now is not None else q.is_("current_reading", "null")
        if not rows(q.execute()):
            raise AppError(f"{p['name']}: the meter was just changed. Refresh the page and save again.")
        upd = {"closing_reading": to_json(c["closing"])}
        if p["first_time"]:
            upd.update({"is_active": False, "ended_at": now_ist()})
        db().table("shift_assignments").update(upd).eq("id", a["id"]).execute()

        snapshot.append({
            "assignment_id": a["id"], "nozzle_id": a["nozzle_id"], "nozzle_name": p["name"],
            "fuel_type": p["fuel_type"],
            "opening": to_json(c["opening"]), "closing": to_json(c["closing"]),
            "gross_liters": to_json(c["gross_liters"]),
            "testing_liters": to_json(c["testing_liters"]), "testing_adj": to_json(c["testing_liters"]),
            "net_sale_liters": to_json(c["net_sale_liters"]), "actual_liters": to_json(c["net_sale_liters"]),
            "rate": to_json(c["rate"]), "locked_rate": to_json(c["rate"]), "rate_date": p["shift_date"],
            "sale_amount": to_json(c["sale_amount"]), "amount_formula": "net_sale_liters * rate",
        })

    total = meter_total([p["calc"] for p in preview])
    data = {"nozzle_readings": snapshot, "meter_total": to_json(total),
            "date": shift.get("date") or today_ist(), "manager_note": "Closing recorded by manager"}
    if s:
        if s.get("breakup_submitted_at"):
            data["difference"] = to_json(settlement_difference(total, s.get("cash_amount"), s.get("paytm_amount"),
                                                               s.get("ccms_amount"), s.get("credit_amount")))
        db().table("settlements").update(data).eq("id", s["id"]).execute()
    else:
        db().table("settlements").insert({
            **data, "shift_id": shift_id, "salesman_id": shift["salesman_id"], "status": "pending",
            "cash_amount": 0, "paytm_amount": 0, "ccms_amount": 0, "credit_amount": 0,
            "entries_total": to_json(sales.entries_total(shift_id, shift["salesman_id"])),
            "difference": 0, "created_at": now_ist(),
        }).execute()
    audit("closing_saved", manager_id, {"shift": shift_id, "meter_total": str(total)})
    return total


# ======================= Manager: approve / hold / reopen =======================
def approve(settlement_id, manager_id):
    try:
        res = db().rpc("approve_settlement_v2", {
            "p_settlement_id": settlement_id, "p_manager_id": manager_id,
            "p_tolerance": float(SETTLEMENT_TOLERANCE),
        }).execute()
    except Exception as exc:
        msg = getattr(exc, "message", None) or str(exc)
        if "approve_settlement_v2" in msg and ("not find" in msg or "does not exist" in msg):
            raise AppError("Database function not found. Please run sql/01_schema.sql.")
        raise AppError(f"Approval failed: {msg}")
    audit("settlement_approved", manager_id, {"settlement": settlement_id})
    return getattr(res, "data", None)


def hold(settlement_id, note, manager_id):
    s = get(settlement_id)
    if not s or s.get("status") == "approved":
        raise AppError("This settlement cannot be put on hold.")
    db().table("settlements").update({"status": "hold", "manager_note": note or "Put on hold by manager"}) \
        .eq("id", settlement_id).execute()
    audit("settlement_hold", manager_id, {"settlement": settlement_id, "note": note})


def reopen(settlement_id, note, manager_id):
    """Salesman ko wapas bhejo: wo entries sudhaar ke hisaab dobara bhej sake."""
    s = get(settlement_id)
    if not s or s.get("status") == "approved":
        raise AppError("An approved settlement cannot be returned.")
    if not (duties.get(s["shift_id"]) or {}).get("is_active"):
        raise AppError("The shift has ended — the salesman cannot log in.")
    db().table("settlements").update({
        "status": "reopened", "breakup_submitted_at": None, "manager_note": note or "Returned by manager",
    }).eq("id", settlement_id).execute()
    credit.reject_open_for_reference(settlement_id, manager_id, "Returned to salesman")
    audit("settlement_reopened", manager_id, {"settlement": settlement_id, "note": note})
