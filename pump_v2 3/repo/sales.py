from core.db import run
from core.timeutil import now_ist, today_ist

LIVE_EXCLUDE = ("rejected", "cancelled")


def live_for_shift(shift_id):
    return run("sales.live_for_shift", lambda c: c.table("sale_entries").select("*").eq("shift_id", shift_id)
               .neq("status", "rejected").neq("status", "cancelled").order("entry_time").execute())


def create(shift_id, nozzle_id, salesman_id, fuel_type, liters, rate, rate_date, rate_snapshot):
    payload = {
        "shift_id": shift_id, "nozzle_id": nozzle_id, "salesman_id": salesman_id,
        "date": today_ist(), "entry_time": now_ist(), "fuel_type": fuel_type,
        "liters": liters, "rate": rate, "locked_rate": rate, "rate_date": rate_date,
        "rate_snapshot": rate_snapshot, "amount": round(liters * rate, 2),
        "payment_mode": None, "credit_party_id": None, "vehicle_number": None,
        "status": "pending", "created_at": now_ist(),
    }
    return run("sales.create", lambda c: c.table("sale_entries").insert(payload).execute())


def get(entry_id):
    return run("sales.get", lambda c: c.table("sale_entries").select("*").eq("id", entry_id).limit(1).execute())


def cancel(entry_id):
    return run("sales.cancel", lambda c: c.table("sale_entries").update({"status": "cancelled"}).eq("id", entry_id).execute())


def set_status_for_shift(shift_id, new_status, extra=None):
    """Applies to live (not rejected/cancelled) entries only."""
    payload = {"status": new_status, **(extra or {})}
    return run(f"sales.set_status_for_shift({new_status})", lambda c: c.table("sale_entries").update(payload)
               .eq("shift_id", shift_id).neq("status", "rejected").neq("status", "cancelled").execute())
