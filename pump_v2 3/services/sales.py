from core.db import fail, ok
from repo import assignments, rates, sales, settlements, shifts

LOCKED = ("pending", "hold", "approved")


def _locked(shift_id):
    res = settlements.for_shift(shift_id)
    if not res.ok:
        return res, None
    status = (res.first or {}).get("status")
    return res, status


def my_context(user):
    """Everything an attendant screen needs, or a Result explaining why not."""
    duty = shifts.active_for(user["id"])
    if not duty.ok:
        return duty
    if not duty.first:
        return fail("No active duty. Ask the manager to start your duty.", "sales.context")
    shift = duty.first
    assigned = assignments.for_shift(shift["id"])
    if not assigned.ok:
        return assigned
    entries = sales.live_for_shift(shift["id"])
    if not entries.ok:
        return entries
    st_res, status = _locked(shift["id"])
    if not st_res.ok:
        return st_res
    total = round(sum(float(e.get("amount") or 0) for e in entries.rows), 2)
    return ok({"shift": shift, "assignments": assigned.rows, "entries": entries.rows,
               "settlement": st_res.first, "settlement_status": status, "total_sale": total}, "sales.context")


def add_sale(user, shift, assignment, liters):
    try:
        liters = round(float(liters), 2)
    except (TypeError, ValueError):
        return fail("Liters must be a number.", "sales.add")
    if liters <= 0:
        return fail("Liters must be greater than 0.", "sales.add")
    if assignment.get("salesman_id") != user["id"] or assignment.get("shift_id") != shift["id"]:
        return fail("This nozzle is not assigned to you on this duty.", "sales.add")

    res, status = _locked(shift["id"])
    if not res.ok:
        return res
    if status in LOCKED:
        return fail(f"Sale already sent to manager (status: {status}). New entries are not allowed.", "sales.add")

    fuel = assignment["fuel_type"]
    date = shifts.shift_date(shift)
    rate_res = rates.current(fuel, date)
    if not rate_res.ok:
        return rate_res
    row = rate_res.first
    if not row:
        return fail(f"Fuel rate for {fuel} is not set for {date}. Owner must set it first.", "sales.add")
    rate = float(row["price_per_liter"])
    snapshot = {"fuel_type": fuel, "locked_rate": rate, "rate_date": row.get("effective_from"),
                "source": "fuel_rates", "rate_id": row.get("id")}
    return sales.create(shift["id"], assignment["nozzle_id"], user["id"], fuel, liters, rate,
                        shifts.shift_date(shift), snapshot)


def cancel_sale(user, entry_id):
    res = sales.get(entry_id)
    if not res.ok:
        return res
    entry = res.first
    if not entry:
        return fail("Entry not found.", "sales.cancel")
    if entry["salesman_id"] != user["id"]:
        return fail("You can cancel only your own entries.", "sales.cancel")
    if entry.get("status") != "pending":
        return fail("Only pending entries can be cancelled.", "sales.cancel")
    _, status = _locked(entry["shift_id"])
    if status in LOCKED:
        return fail(f"Sale already sent to manager (status: {status}).", "sales.cancel")
    return sales.cancel(entry_id)
