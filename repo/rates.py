"""Fuel rate: har fuel ka har tarikh ka ek rate. History kabhi delete nahi."""
from decimal import Decimal

from core.calc import D, q2, to_json
from core.db import FUEL_TYPES, AppError, audit, db, now_ist, one, rows


def rate_row_for(fuel_type: str, on_date: str):
    """Us tarikh ya usse pehle ka sabse naya rate."""
    return one(
        db().table("fuel_rates").select("*")
        .eq("fuel_type", fuel_type).lte("effective_from", on_date)
        .order("effective_from", desc=True).order("created_at", desc=True)
        .limit(1).execute()
    )


def rate_for(fuel_type: str, on_date: str) -> Decimal | None:
    row = rate_row_for(fuel_type, on_date)
    if not row:
        return None
    rate = D(row.get("price_per_liter"))
    return rate if rate > 0 else None


def current_rates(on_date: str) -> dict:
    return {ft: rate_for(ft, on_date) for ft in FUEL_TYPES}


def history(fuel_type=None, limit=100):
    q = db().table("fuel_rates").select("*")
    if fuel_type:
        q = q.eq("fuel_type", fuel_type)
    return rows(q.order("effective_from", desc=True).limit(limit).execute())


def activity_on_or_after(on_date: str) -> bool:
    s = db().table("sale_entries").select("id").gte("date", on_date).limit(1).execute()
    if rows(s):
        return True
    return bool(rows(db().table("settlements").select("id").gte("date", on_date).limit(1).execute()))


def set_rate(fuel_type: str, price, effective_from: str, by: str):
    if fuel_type not in FUEL_TYPES:
        raise AppError("Galat fuel type.")
    price = q2(price)
    if price <= 0:
        raise AppError("Rate 0 se zyada hona chahiye.")

    old = one(db().table("fuel_rates").select("*").eq("fuel_type", fuel_type)
              .eq("effective_from", effective_from).limit(1).execute())
    db().table("fuel_rates").upsert({
        "fuel_type": fuel_type,
        "price_per_liter": to_json(price),
        "effective_from": effective_from,
        "created_by": by,
        "created_at": now_ist(),
    }, on_conflict="fuel_type,effective_from").execute()
    audit("rate_set", by, {"fuel_type": fuel_type, "date": effective_from, "price": str(price),
                            "old_price": (old or {}).get("price_per_liter")})
