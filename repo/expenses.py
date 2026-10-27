"""Kharcha (LOGIC.md 11): entry pending -> approve par cash/bank se minus (database function)."""
from core.calc import q2, to_json
from core.db import AppError, audit, db, now_ist, rows

CATEGORIES = ["Salary", "Electricity", "Maintenance", "Transport", "Office", "Bank charges", "Rent", "Miscellaneous"]


def add(on_date, category, description, amount, mode, bank_id, ref, by):
    if category not in CATEGORIES:
        raise AppError("Please select a category.")
    if q2(amount) <= 0:
        raise AppError("Amount must be greater than 0.")
    if mode not in ("cash", "bank"):
        raise AppError("Payment mode must be cash or bank.")
    if mode == "bank" and not bank_id:
        raise AppError("Please select a bank account.")
    db().table("expenses").insert({
        "date": on_date, "category": category, "description": (description or "").strip() or None,
        "amount": to_json(amount), "payment_mode": mode, "bank_account_id": bank_id if mode == "bank" else None,
        "reference_no": (ref or "").strip() or None, "status": "pending", "created_by": by, "created_at": now_ist(),
    }).execute()
    audit("expense_added", by, {"category": category, "amount": str(q2(amount)), "mode": mode})


def list_(status=None, from_date=None, to_date=None, limit=200):
    q = db().table("expenses").select("*")
    if status:
        q = q.eq("status", status)
    if from_date:
        q = q.gte("date", from_date)
    if to_date:
        q = q.lte("date", to_date)
    return rows(q.order("date", desc=True).order("id", desc=True).limit(limit).execute())


def approve(expense_id, by):
    try:
        db().rpc("approve_expense_v2", {"p_id": expense_id, "p_by": by}).execute()
    except Exception as exc:
        raise AppError(getattr(exc, "message", None) or str(exc))
    audit("expense_approved", by, {"id": expense_id})


def reject(expense_id, by):
    res = db().table("expenses").update({"status": "rejected", "approved_by": by, "approved_at": now_ist()}) \
        .eq("id", expense_id).eq("status", "pending").execute()
    if not rows(res):
        raise AppError("This expense is not pending.")
    audit("expense_rejected", by, {"id": expense_id})
