"""
Money Control (LOGIC.md 10). Saari aawak/jaawak money_txns mein; balance = sum(amount).
- cash, paytm, ccms minus mein nahi ja sakte (database function rokta hai). Bank (OD/CC) ja sakta hai.
- 'oil' account = oil company ko kitna dena hai (+ bill, − payment/CCMS adjust).
"""
from core.calc import ZERO, D, q2, to_json
from core.db import AppError, audit, db, rows, today_ist

ACCOUNTS = ["cash", "bank", "paytm", "ccms", "oil"]
ACCOUNT_LABELS = {"cash": "Cash in hand", "bank": "Bank", "paytm": "Paytm / UPI", "ccms": "CCMS / Card",
                  "oil": "Payable to oil company"}
KIND_LABELS = {
    "sale": "Sale (settlement)", "party_payment": "Payment from credit party", "cash_deposit": "Cash deposited to bank",
    "paytm_settlement": "Paytm settled to bank", "ccms_adjust": "CCMS adjusted with oil company",
    "oil_payment": "Payment to oil company", "fuel_inward": "Fuel purchase invoice", "expense": "Expense",
    "opening": "Opening balance",
}


def txns(from_date=None, to_date=None, account=None, kind=None):
    q = db().table("money_txns").select("*")
    if kind:
        q = q.eq("kind", kind)
    if from_date:
        q = q.gte("date", from_date)
    if to_date:
        q = q.lte("date", to_date)
    if account:
        q = q.eq("account", account)
    return rows(q.order("date").order("id").execute())


def _key(t):
    if t["account"] == "bank":
        return ("bank", t.get("bank_account_id"))
    if t["account"] == "oil":
        return ("oil", t.get("oil_company_id"))
    return (t["account"], None)


def balances(as_of=None):
    """{(account, ref_id): balance} — as_of tarikh tak (shaamil)."""
    out = {}
    for t in txns(to_date=as_of):
        k = _key(t)
        out[k] = q2(out.get(k, ZERO) + D(t["amount"]))
    return out


def balance(account, ref=None, as_of=None):
    return balances(as_of).get((account, ref), ZERO)


def _transfer(kind, on_date, amount, frm, frm_bank, to, to_bank, oil_co, ref, note, by):
    if q2(amount) <= 0:
        raise AppError("Amount must be greater than 0.")
    try:
        db().rpc("money_transfer_v2", {
            "p_kind": kind, "p_date": on_date, "p_amount": to_json(amount),
            "p_from": frm, "p_from_bank": frm_bank, "p_to": to, "p_to_bank": to_bank,
            "p_oil_company": oil_co, "p_ref": (ref or "").strip() or None, "p_note": (note or "").strip() or None,
            "p_by": by,
        }).execute()
    except Exception as exc:
        raise AppError(getattr(exc, "message", None) or str(exc))
    audit(kind, by, {"amount": str(q2(amount)), "date": on_date, "from": frm, "to": to,
                     "bank": frm_bank or to_bank, "oil_company": oil_co})


def cash_deposit(on_date, amount, bank_id, ref, note, by):
    if not bank_id:
        raise AppError("Please select a bank account.")
    _transfer("cash_deposit", on_date, amount, "cash", None, "bank", bank_id, None, ref, note, by)


def paytm_settlement(on_date, amount, bank_id, ref, note, by):
    if not bank_id:
        raise AppError("Please select a bank account.")
    _transfer("paytm_settlement", on_date, amount, "paytm", None, "bank", bank_id, None, ref, note, by)


def ccms_adjust(on_date, amount, oil_company_id, ref, note, by):
    if not oil_company_id:
        raise AppError("Please select an oil company.")
    _transfer("ccms_adjust", on_date, amount, "ccms", None, "oil", None, oil_company_id, ref, note, by)


def oil_payment(on_date, amount, bank_id, oil_company_id, ref, note, by):
    if not bank_id or not oil_company_id:
        raise AppError("Please select both the bank account and the oil company.")
    _transfer("oil_payment", on_date, amount, "bank", bank_id, "oil", None, oil_company_id, ref, note, by)


def set_opening(account, ref_id, amount, on_date, by):
    """Shuru ka balance (ek account ka ek hi baar). Bank/oil minus ho sakte hain."""
    if account not in ACCOUNTS:
        raise AppError("Invalid account.")
    amount = q2(amount)
    if amount == 0:
        raise AppError("Please enter an amount.")
    if amount < 0 and account in ("cash", "paytm", "ccms"):
        raise AppError("Opening balance for Cash / Paytm / CCMS cannot be negative.")
    if account in ("bank", "oil") and not ref_id:
        raise AppError("Please select the bank account / oil company.")
    done = reversed_groups()
    existing = [t for t in txns(account=account, kind="opening") if t.get("reverses_group") is None and _key(t) == _key(
        {"account": account, "bank_account_id": ref_id, "oil_company_id": ref_id})
        and (t.get("group_id") or t["id"]) not in done]
    if existing:
        raise AppError("Opening balance for this account has already been entered.")
    db().table("money_txns").insert({
        "date": on_date or today_ist(), "account": account,
        "bank_account_id": ref_id if account == "bank" else None,
        "oil_company_id": ref_id if account == "oil" else None,
        "amount": to_json(amount), "kind": "opening", "note": "Opening balance", "created_by": by,
    }).execute()
    audit("money_opening", by, {"account": account, "ref": ref_id, "amount": str(amount)})


def _rpc(name, params):
    try:
        return getattr(db().rpc(name, params).execute(), "data", None)
    except Exception as exc:
        raise AppError(getattr(exc, "message", None) or str(exc))


REVERSIBLE = ("cash_deposit", "paytm_settlement", "ccms_adjust", "oil_payment", "opening")


def reversed_groups() -> set:
    """Groups that have been reversed (and the reversal groups themselves)."""
    out = set()
    for t in rows(db().table("money_txns").select("group_id, reverses_group").not_.is_("reverses_group", "null").execute()):
        out.add(t["reverses_group"])
        out.add(t["group_id"])
    return out


def reverse(txn_id, by):
    _rpc("reverse_money_v2", {"p_id": txn_id, "p_by": by})
    audit("money_reversed", by, {"txn": txn_id})
