from core.db import fail, run
from core.schema import FUEL_TYPES
from core.timeutil import now_ist, today_ist


def current(fuel_type, as_of=None):
    as_of = as_of or today_ist()
    return run("rates.current", lambda c: c.table("fuel_rates").select("*").eq("fuel_type", fuel_type)
               .lte("effective_from", as_of).order("effective_from", desc=True).order("created_at", desc=True)
               .limit(1).execute())


def history(limit=100):
    return run("rates.history", lambda c: c.table("fuel_rates").select("*")
               .order("effective_from", desc=True).order("created_at", desc=True).limit(limit).execute())


def set_rate(fuel_type, price, effective_from, created_by):
    if fuel_type not in FUEL_TYPES:
        return fail(f"Unknown fuel type: {fuel_type}", "rates.set")
    if float(price or 0) <= 0:
        return fail("Rate must be greater than 0.", "rates.set")
    payload = {"fuel_type": fuel_type, "price_per_liter": float(price),
               "effective_from": str(effective_from), "created_by": created_by, "created_at": now_ist()}
    return run("rates.set", lambda c: c.table("fuel_rates").insert(payload).execute())
