"""Salesman payment breakup + manager approval.

Status flow:  (none) -> pending -> approved
                         pending -> hold -> pending (reopen)
                         pending/hold -> rejected -> (salesman enters fresh sale) -> pending
Approval writes in a safe order (entries, nozzle readings, assignments, THEN
the settlement status), so a failure in the middle can simply be retried.
"""
from core.db import fail, ok
from core.log import get_logger
from core.timeutil import now_ist, today_ist
from repo import assignments, nozzles, sales, settlements, shifts
from services import calc

log = get_logger()


def submit_breakup(user, shift, cash, paytm, ccms):
    live = sales.live_for_shift(shift["id"])
    if not live.ok:
        return live
    total = round(sum(calc.f(e.get("amount")) for e in live.rows), 2)
    if total <= 0:
        return fail("There is no sale to submit. Add sale entries first.", "settlement.submit")
    match = calc.payment_match(total, cash, paytm, ccms)
    if min(match["cash"], match["paytm"], match["ccms"]) < 0:
        return fail("Amounts cannot be negative.", "settlement.submit")
    if not match["is_matched"]:
        return fail(f"Cash + Paytm + CCMS = {match['payment_total']:.2f} but total sale = {total:.2f} "
                    f"(difference {match['difference']:.2f}).", "settlement.submit")

    existing = settlements.for_shift(shift["id"])
    if not existing.ok:
        return existing
    row = existing.first
    if row and row.get("status") in ("pending", "hold", "approved"):
        return fail(f"Already submitted (status: {row['status']}). Manager must act first.", "settlement.submit")

    payload = {
        "shift_id": shift["id"], "salesman_id": user["id"], "date": today_ist(),
        "nozzle_readings": [], "meter_total": total, "entries_total": total, "difference": 0,
        "cash_amount": match["cash"], "paytm_amount": match["paytm"], "ccms_amount": match["ccms"],
        "credit_amount": 0, "cash_given_to_creditor_amount": 0, "cash_transfer_expected": match["cash"],
        "status": "pending", "manager_note": "Salesman payment breakup submitted",
    }
    if row:
        return settlements.update(row["id"], payload)
    payload["created_at"] = now_ist()
    return settlements.insert(payload)


def _payment_total(s):
    return round(calc.f(s.get("cash_amount")) + calc.f(s.get("paytm_amount"))
                 + calc.f(s.get("ccms_amount")) + calc.f(s.get("credit_amount")), 2)


def _load(settlement_id, allowed):
    res = settlements.get(settlement_id)
    if not res.ok:
        return res, None
    s = res.first
    if not s:
        return fail("Settlement not found.", "settlement.load"), None
    if s.get("status") not in allowed:
        return fail(f"Not allowed in status '{s.get('status')}'.", "settlement.load"), None
    return ok(s, "settlement.load"), s


def review_data(settlement, closing_inputs=None):
    """Assignments + entries + meter preview for the approval screen."""
    shift_id = settlement["shift_id"]
    a = assignments.for_shift(shift_id)
    if not a.ok:
        return a
    s = sales.live_for_shift(shift_id)
    if not s.ok:
        return s
    saved = {r["assignment_id"]: r["closing"] for r in (settlement.get("nozzle_readings") or []) if isinstance(r, dict)}
    inputs = dict(saved)
    inputs.update(closing_inputs or {})
    rows, meter_total, errors = calc.meter_rows(a.rows, s.rows, inputs)
    pay = _payment_total(settlement)
    return ok({"assignments": a.rows, "entries": s.rows, "rows": rows, "meter_total": meter_total,
               "errors": errors, "payment_total": pay, "difference": round(meter_total - pay, 2),
               "matched": (not errors) and abs(meter_total - pay) < 0.01, "saved_inputs": saved},
              "settlement.review")


def save_closing(manager, settlement_id, closing_inputs):
    res, s = _load(settlement_id, ("pending", "hold"))
    if not res.ok:
        return res
    rev = review_data(s, closing_inputs)
    if not rev.ok:
        return rev
    d = rev.data
    if d["errors"]:
        return fail(" | ".join(d["errors"]), "settlement.save_closing")
    stored = [{"assignment_id": r["assignment_id"], "nozzle_id": r["nozzle_id"], "opening": r["opening"],
               "closing": r["closing"], "meter_liters": r["meter_liters"], "meter_amount": r["meter_amount"]}
              for r in d["rows"]]
    upd = settlements.update(settlement_id, {
        "nozzle_readings": stored, "meter_total": d["meter_total"],
        "difference": d["difference"], "manager_note": f"Closing saved by {manager['name']}"})
    if not upd.ok:
        return upd
    return ok(d, "settlement.save_closing")


def approve(manager, settlement_id):
    res, s = _load(settlement_id, ("pending", "hold"))
    if not res.ok:
        return res
    if not s.get("nozzle_readings"):
        return fail("Save the closing readings first.", "settlement.approve")
    rev = review_data(s)
    if not rev.ok:
        return rev
    d = rev.data
    if d["errors"]:
        return fail("Closing readings incomplete: " + " | ".join(d["errors"]), "settlement.approve")
    if not d["matched"]:
        return fail(f"Meter sale {d['meter_total']:.2f} does not match payment {d['payment_total']:.2f} "
                    f"(difference {d['difference']:.2f}). Reject or hold instead.", "settlement.approve")

    done = []
    step = sales.set_status_for_shift(s["shift_id"], "approved", {"approved_by": manager["id"]})
    if not step.ok:
        return _partial(step, done)
    done.append("sale entries approved")
    for r in d["rows"]:
        step = nozzles.set_reading(r["nozzle_id"], r["closing"])
        if not step.ok:
            return _partial(step, done)
        done.append(f"nozzle {r['nozzle_id']} reading updated")
    for a in d["assignments"]:
        step = assignments.end(a["id"])
        if not step.ok:
            return _partial(step, done)
        done.append(f"assignment {a['id']} ended")
    final = settlements.update(settlement_id, {
        "status": "approved", "approved_by": manager["id"], "approved_at": now_ist(),
        "manager_note": f"Approved by {manager['name']}"})
    if not final.ok:
        return _partial(final, done)
    log.info("settlement.approve: #%s approved by %s", settlement_id, manager["name"])
    return final


def _partial(step, done):
    msg = f"Approval stopped at '{step.where}': {step.error}. Already done: {', '.join(done) or 'nothing'}. Safe to press Approve again."
    log.error(msg)
    return fail(msg, step.where)


def reject(manager, settlement_id, note):
    res, s = _load(settlement_id, ("pending", "hold"))
    if not res.ok:
        return res
    step = sales.set_status_for_shift(s["shift_id"], "rejected")
    if not step.ok:
        return step
    return settlements.update(settlement_id, {
        "status": "rejected", "nozzle_readings": [],
        "manager_note": (note or "Rejected by manager. Enter fresh sale.")})


def hold(manager, settlement_id, note):
    res, _ = _load(settlement_id, ("pending",))
    if not res.ok:
        return res
    return settlements.update(settlement_id, {"status": "hold", "manager_note": note or "Held by manager"})


def reopen(manager, settlement_id):
    res, _ = _load(settlement_id, ("hold",))
    if not res.ok:
        return res
    return settlements.update(settlement_id, {"status": "pending", "manager_note": "Reopened by manager"})
