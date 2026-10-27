"""
Stock (LOGIC.md 9):
- Tanker inward: Manager entry (pending) -> approve par tank + aur oil company ka bill (ek hi raasta, R7).
- Dip: physical stock entry -> approve par farak (physical − book) tank mein adjust (R6).
- Stock register: stock_moves se — har din opening / inward / sale / adjust / closing.
"""
from core.calc import ZERO, D, q2, to_json
from core.db import FUEL_TYPES, AppError, audit, db, fetch_all, now_ist, one, rows, today_ist
from repo import tanks


def _rpc(name, params):
    try:
        return getattr(db().rpc(name, params).execute(), "data", None)
    except Exception as exc:
        raise AppError(getattr(exc, "message", None) or str(exc))


# ---------------- Inward ----------------
def add_inward(on_date, fuel_type, oil_company_id, invoice_no, liters, amount, note, by):
    if fuel_type not in FUEL_TYPES:
        raise AppError("Invalid fuel type.")
    if not oil_company_id:
        raise AppError("Please select an oil company.")
    if q2(liters) <= 0 or q2(amount) <= 0:
        raise AppError("Please enter both litres and invoice amount.")
    tank = tanks.get_by_fuel(fuel_type)
    if not tank:
        raise AppError("No tank is set up for this fuel.")
    invoice_no = (invoice_no or "").strip()
    if invoice_no and rows(db().table("fuel_inward").select("id").eq("invoice_no", invoice_no)
                           .eq("oil_company_id", oil_company_id).in_("status", ["pending", "approved"]).execute()):
        raise AppError("This invoice number has already been entered.")
    db().table("fuel_inward").insert({
        "date": on_date, "fuel_type": fuel_type, "oil_company_id": oil_company_id,
        "invoice_no": invoice_no or None, "liters": to_json(liters), "amount": to_json(amount),
        "note": (note or "").strip() or None, "status": "pending", "created_by": by, "created_at": now_ist(),
    }).execute()
    audit("inward_added", by, {"fuel": fuel_type, "liters": str(q2(liters)), "amount": str(q2(amount))})


def inwards(status=None, limit=100):
    q = db().table("fuel_inward").select("*")
    if status:
        q = q.eq("status", status)
    return rows(q.order("date", desc=True).order("id", desc=True).limit(limit).execute())


def approve_inward(inward_id, by):
    _rpc("approve_inward_v2", {"p_id": inward_id, "p_by": by})
    audit("inward_approved", by, {"id": inward_id})


def reject(table, row_id, by):
    if table not in ("fuel_inward", "stock_dips"):
        raise AppError("Invalid table.")
    res = db().table(table).update({"status": "rejected", "approved_by": by, "approved_at": now_ist()}) \
        .eq("id", row_id).eq("status", "pending").execute()
    if not rows(res):
        raise AppError("This entry is not pending.")
    audit(f"{table}_rejected", by, {"id": row_id})


# ---------------- Dip ----------------
def add_dip(on_date, fuel_type, physical, dip_cm, note, by):
    tank = tanks.get_by_fuel(fuel_type)
    if not tank:
        raise AppError("No tank is set up for this fuel.")
    physical = q2(physical)
    if physical < 0 or physical > D(tank.get("capacity_liters")):
        raise AppError("Physical stock must be between 0 and tank capacity.")
    if rows(db().table("stock_dips").select("id").eq("fuel_type", fuel_type).eq("status", "pending").execute()):
        raise AppError("A dip entry for this fuel is already pending. Approve or reject it first.")
    book = q2(tank.get("current_stock"))
    db().table("stock_dips").insert({
        "date": on_date, "fuel_type": fuel_type, "dip_cm": to_json(dip_cm) if dip_cm else None,
        "physical_liters": to_json(physical), "book_liters": to_json(book),
        "variance": to_json(physical - book), "note": (note or "").strip() or None,
        "status": "pending", "created_by": by, "created_at": now_ist(),
    }).execute()
    audit("dip_added", by, {"fuel": fuel_type, "physical": str(physical), "book": str(book)})
    return q2(physical - book)


def dips(status=None, limit=100):
    q = db().table("stock_dips").select("*")
    if status:
        q = q.eq("status", status)
    return rows(q.order("date", desc=True).order("id", desc=True).limit(limit).execute())


def approve_dip(dip_id, by):
    _rpc("approve_dip_v2", {"p_id": dip_id, "p_by": by})
    audit("dip_approved", by, {"id": dip_id})


# ---------------- Register ----------------
def moves(fuel_type=None, from_date=None, to_date=None):
    def make():
        q = db().table("stock_moves").select("*")
        if fuel_type:
            q = q.eq("fuel_type", fuel_type)
        if from_date:
            q = q.gte("date", from_date)
        if to_date:
            q = q.lte("date", to_date)
        return q.order("date").order("id")
    return fetch_all(make)


def register(fuel_type, from_date, to_date):
    """Din-wise: opening, inward, sale, adjust, closing."""
    from core.calc import stock_register
    before = q2(sum((D(m["delta"]) for m in moves(fuel_type, to_date=_prev(from_date))), ZERO))
    return stock_register(before, moves(fuel_type, from_date, to_date))


def _prev(d):
    from datetime import date, timedelta
    return (date.fromisoformat(d) - timedelta(days=1)).isoformat()


def last_purchase_rates(as_of=None):
    """Har fuel ka aakhri approved tanker rate (bill / litre) — P&L ke liye."""
    out = {}
    for r in fetch_all(lambda: db().table("fuel_inward").select("*").eq("status", "approved")
                       .lte("date", as_of or today_ist()).order("date").order("id")):
        out[r["fuel_type"]] = (D(r["amount"]) / D(r["liters"]))
    return out


def reverse_inward(inward_id, by):
    _rpc("reverse_inward_v2", {"p_id": inward_id, "p_by": by})
    audit("inward_reversed", by, {"id": inward_id})


def reverse_dip(dip_id, by):
    _rpc("reverse_dip_v2", {"p_id": dip_id, "p_by": by})
    audit("dip_reversed", by, {"id": dip_id})
