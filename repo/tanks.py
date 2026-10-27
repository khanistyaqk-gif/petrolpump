"""
Tank setup. Stock hamesha adjust_tank_v2 (database function) se badalta hai —
har badlav stock_moves mein, isliye stock register kabhi galat nahi (R6).
"""
from core.calc import D, q2, to_json
from core.db import FUEL_TYPES, AppError, audit, db, now_ist, one, rows, today_ist


def list_tanks():
    return rows(db().table("stock_tanks").select("*").eq("is_active", True).order("fuel_type").execute())


def get_by_fuel(fuel_type):
    return one(db().table("stock_tanks").select("*").eq("fuel_type", fuel_type)
               .eq("is_active", True).limit(1).execute())


def adjust(fuel_type, delta, kind, ref_table, ref_id, note, by, on_date=None):
    try:
        res = db().rpc("adjust_tank_v2", {
            "p_fuel": fuel_type, "p_delta": to_json(delta), "p_kind": kind, "p_date": on_date or today_ist(),
            "p_ref_table": ref_table, "p_ref_id": ref_id, "p_note": note, "p_by": by,
        }).execute()
    except Exception as exc:
        raise AppError(getattr(exc, "message", None) or str(exc))
    return getattr(res, "data", None)


def create(fuel_type, name, capacity, opening, by):
    if fuel_type not in FUEL_TYPES:
        raise AppError("Invalid fuel type.")
    if get_by_fuel(fuel_type):
        raise AppError("A tank for this fuel already exists.")
    if D(capacity) <= 0:
        raise AppError("Please enter the tank capacity.")
    if D(opening) < 0 or D(opening) > D(capacity):
        raise AppError("Opening stock must be between 0 and tank capacity.")
    res = db().table("stock_tanks").insert({
        "fuel_type": fuel_type, "tank_name": (name or "").strip() or f"{fuel_type} tank",
        "capacity_liters": to_json(capacity), "opening_stock": to_json(opening), "current_stock": 0,
        "is_active": True, "created_by": by, "created_at": now_ist(),
    }).execute()
    tank = one(res)
    if D(opening) > 0:
        try:
            adjust(fuel_type, opening, "opening", "stock_tanks", str(tank["id"]), "Opening stock", by)
        except AppError:
            db().table("stock_tanks").delete().eq("id", tank["id"]).execute()
            raise
    audit("tank_created", by, {"fuel_type": fuel_type, "opening": str(q2(opening))})


def correct_stock(fuel_type, new_stock, reason, by):
    reason = (reason or "").strip()
    if not reason:
        raise AppError("Please enter a reason.")
    tank = get_by_fuel(fuel_type)
    if not tank:
        raise AppError("Tank not found.")
    delta = q2(D(new_stock) - D(tank.get("current_stock")))
    if delta == 0:
        raise AppError("Stock is already at this value.")
    adjust(fuel_type, delta, "correction", "stock_tanks", str(tank["id"]), reason, by)
    audit("tank_stock_corrected", by, {"fuel_type": fuel_type, "old": tank.get("current_stock"),
                                       "new": str(q2(new_stock)), "reason": reason})
