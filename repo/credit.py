"""
Credit party (udhaar) — LOGIC.md 8.
Balance SIRF approve par badalta hai (database function approve_settlement_v2 mein).
"""
from core.calc import ZERO, D, q2, to_json
from core.db import AppError, audit, db, fetch_all, now_ist, one, rows, today_ist

OPEN = ("pending", "hold", "reopened")


def vehicles_of(party) -> list:
    v = party.get("vehicles") or []
    if isinstance(v, str):
        v = [x for x in v.replace(",", "\n").splitlines()]
    return [str(x).strip() for x in v if str(x).strip()]


def list_parties(active_only=False):
    q = db().table("credit_parties").select("*")
    if active_only:
        q = q.eq("is_active", True)
    return rows(q.order("name").execute())


def get(party_id):
    return one(db().table("credit_parties").select("*").eq("id", party_id).limit(1).execute())


def save_party(party_id, name, phone, limit, vehicles_text, is_active, by):
    name = (name or "").strip()
    if not name:
        raise AppError("Please enter the party name.")
    if D(limit) < 0:
        raise AppError("Credit limit cannot be negative.")
    vehicles = [x.strip().upper() for x in (vehicles_text or "").replace(",", "\n").splitlines() if x.strip()]
    data = {"name": name, "phone": (phone or "").strip() or None, "credit_limit": to_json(limit),
            "vehicles": vehicles, "is_active": bool(is_active)}
    if party_id:
        db().table("credit_parties").update(data).eq("id", party_id).execute()
        audit("party_updated", by, {"party": party_id, **data})
    else:
        db().table("credit_parties").insert({**data, "current_balance": 0, "created_by": by,
                                             "created_at": now_ist()}).execute()
        audit("party_created", by, data)


def pending_increase(party_id):
    """Abhi approve nahi hua udhaar (sale + cash diya) — limit check mein judta hai."""
    data = rows(db().table("credit_transactions").select("amount, type, status")
                .eq("party_id", party_id).in_("type", ["sale", "cash_given"]).in_("status", list(OPEN)).execute())
    return q2(sum((D(r.get("amount")) for r in data), ZERO))


def add_txn(party_id, txn_type, amount, reference_id, note, vehicle, by, entry_date=None):
    if D(amount) <= 0:
        raise AppError("Amount must be greater than 0.")
    final_note = " | ".join(x for x in [(note or "").strip(), f"Vehicle: {vehicle}" if vehicle else ""] if x)
    res = db().table("credit_transactions").insert({
        "date": entry_date or today_ist(), "party_id": party_id, "type": txn_type,
        "amount": to_json(amount), "payment_mode": "credit",
        "reference_id": str(reference_id) if reference_id is not None else None,
        "note": final_note or None, "status": "pending", "created_by": by, "created_at": now_ist(),
    }).execute()
    return one(res)


def txns_for_reference(reference_id):
    return rows(db().table("credit_transactions").select("*, credit_parties:party_id(name, credit_limit, current_balance)")
                .eq("reference_id", str(reference_id)).in_("type", ["sale", "cash_given"])
                .order("id").execute())


def reject_open_for_reference(reference_id, by, note):
    db().table("credit_transactions").update({
        "status": "rejected", "approved_by": by, "approved_at": now_ist(), "approval_note": note,
    }).eq("reference_id", str(reference_id)).in_("type", ["sale", "cash_given"]).in_("status", list(OPEN)).execute()


def ledger(party_id, limit=200):
    return rows(db().table("credit_transactions").select("*").eq("party_id", party_id)
                .order("created_at", desc=True).limit(limit).execute())


def record_payment(party_id, amount, mode, bank_id, on_date, ref, note, by):
    if q2(amount) <= 0:
        raise AppError("Amount must be greater than 0.")
    try:
        db().rpc("record_party_payment_v2", {
            "p_party_id": party_id, "p_amount": to_json(amount), "p_mode": mode,
            "p_bank_id": bank_id if mode == "bank" else None, "p_date": on_date or today_ist(),
            "p_ref": (ref or "").strip() or None, "p_note": (note or "").strip() or None, "p_by": by,
        }).execute()
    except Exception as exc:
        raise AppError(getattr(exc, "message", None) or str(exc))
    audit("party_payment", by, {"party": party_id, "amount": str(q2(amount)), "mode": mode})


def set_opening(party_id, amount, on_date, by):
    try:
        db().rpc("party_opening_v2", {"p_party_id": party_id, "p_amount": to_json(amount),
                                      "p_date": on_date or today_ist(), "p_by": by}).execute()
    except Exception as exc:
        raise AppError(getattr(exc, "message", None) or str(exc))
    audit("party_opening", by, {"party": party_id, "amount": str(q2(amount))})


def statement(party_id, from_date, to_date):
    """Opening (from_date se pehle tak), har approved entry, closing."""
    from core.calc import party_statement
    data = fetch_all(lambda: db().table("credit_transactions").select("*").eq("party_id", party_id)
                     .eq("status", "approved").lte("date", to_date).order("date").order("id"))
    return party_statement(data, from_date)


def _rpc(name, params):
    try:
        return getattr(db().rpc(name, params).execute(), "data", None)
    except Exception as exc:
        raise AppError(getattr(exc, "message", None) or str(exc))


def reverse_payment(txn_id, by):
    _rpc("reverse_party_payment_v2", {"p_txn_id": txn_id, "p_by": by})
    audit("party_payment_reversed", by, {"txn": txn_id})
