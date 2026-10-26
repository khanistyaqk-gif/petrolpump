"""
Money Control (LOGIC.md 10). Saari aawak/jaawak money_txns mein; balance = sum(amount).
- cash, paytm, ccms minus mein nahi ja sakte (database function rokta hai). Bank (OD/CC) ja sakta hai.
- 'oil' account = oil company ko kitna dena hai (+ bill, − payment/CCMS adjust).
"""
from core.calc import ZERO, D, q2, to_json
from core.db import AppError, audit, db, rows, today_ist

ACCOUNTS = ["cash", "bank", "paytm", "ccms", "oil"]
ACCOUNT_LABELS = {"cash": "Cash (galla)", "bank": "Bank", "paytm": "Paytm / UPI", "ccms": "CCMS / Card",
                  "oil": "Oil company ko dena"}
KIND_LABELS = {
    "sale": "Sale (settlement)", "party_payment": "Party se payment", "cash_deposit": "Cash bank mein jama",
    "paytm_settlement": "Paytm bank mein aaya", "ccms_adjust": "CCMS oil company mein adjust",
    "oil_payment": "Oil company ko payment", "fuel_inward": "Tanker bill", "expense": "Kharcha",
    "opening": "Opening balance",
}


def txns(from_date=None, to_date=None, account=None):
    q = db().table("money_txns").select("*")
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
        raise AppError("Amount 0 se zyada ho.")
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
        raise AppError("Bank chunein.")
    _transfer("cash_deposit", on_date, amount, "cash", None, "bank", bank_id, None, ref, note, by)


def paytm_settlement(on_date, amount, bank_id, ref, note, by):
    if not bank_id:
        raise AppError("Bank chunein.")
    _transfer("paytm_settlement", on_date, amount, "paytm", None, "bank", bank_id, None, ref, note, by)


def ccms_adjust(on_date, amount, oil_company_id, ref, note, by):
    if not oil_company_id:
        raise AppError("Oil company chunein.")
    _transfer("ccms_adjust", on_date, amount, "ccms", None, "oil", None, oil_company_id, ref, note, by)


def oil_payment(on_date, amount, bank_id, oil_company_id, ref, note, by):
    if not bank_id or not oil_company_id:
        raise AppError("Bank aur oil company dono chunein.")
    _transfer("oil_payment", on_date, amount, "bank", bank_id, "oil", None, oil_company_id, ref, note, by)


def set_opening(account, ref_id, amount, on_date, by):
    """Shuru ka balance (ek account ka ek hi baar). Bank/oil minus ho sakte hain."""
    if account not in ACCOUNTS:
        raise AppError("Galat account.")
    amount = q2(amount)
    if amount == 0:
        raise AppError("Amount daalein.")
    if amount < 0 and account in ("cash", "paytm", "ccms"):
        raise AppError("Cash/Paytm/CCMS ka opening minus nahi ho sakta.")
    if account in ("bank", "oil") and not ref_id:
        raise AppError("Bank / oil company chunein.")
    existing = [t for t in txns(account=account) if t["kind"] == "opening" and _key(t) == _key(
        {"account": account, "bank_account_id": ref_id, "oil_company_id": ref_id})]
    if existing:
        raise AppError("Is account ka opening balance pehle hi daala ja chuka hai.")
    db().table("money_txns").insert({
        "date": on_date or today_ist(), "account": account,
        "bank_account_id": ref_id if account == "bank" else None,
        "oil_company_id": ref_id if account == "oil" else None,
        "amount": to_json(amount), "kind": "opening", "note": "Opening balance", "created_by": by,
    }).execute()
    audit("money_opening", by, {"account": account, "ref": ref_id, "amount": str(amount)})
