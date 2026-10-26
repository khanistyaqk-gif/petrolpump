"""
Reports. Sale hamesha approved settlement ke SAVED snapshot se (T3: baad ka rate badlav purana amount nahi badalta).
"""
from core.calc import ZERO, D, cost_of_sales, profit_loss, q2
from core.db import db, rows
from repo import money, stock


def approved_settlements(from_date, to_date):
    return rows(db().table("settlements").select("*, profiles:salesman_id(name)").eq("status", "approved")
                .gte("date", from_date).lte("date", to_date).order("date").order("id").execute())


def fuel_lines(settlements):
    """[{date, fuel_type, liters, amount}] nozzle snapshot se."""
    out = []
    for s in settlements:
        for r in s.get("nozzle_readings") or []:
            out.append({"date": s["date"], "fuel_type": r.get("fuel_type"),
                        "liters": D(r.get("net_sale_liters")), "amount": D(r.get("sale_amount")),
                        "testing": D(r.get("testing_liters"))})
    return out


def sales_by_fuel(settlements):
    out = {}
    for line in fuel_lines(settlements):
        ft = line["fuel_type"]
        cur = out.setdefault(ft, {"liters": ZERO, "amount": ZERO, "testing": ZERO})
        for k in ("liters", "amount", "testing"):
            cur[k] = q2(cur[k] + line[k])
    return out


def period_sales(from_date, to_date):
    """Din × fuel."""
    table = {}
    for line in fuel_lines(approved_settlements(from_date, to_date)):
        key = (line["date"], line["fuel_type"])
        cur = table.setdefault(key, {"date": line["date"], "fuel_type": line["fuel_type"],
                                     "liters": ZERO, "amount": ZERO})
        cur["liters"] = q2(cur["liters"] + line["liters"])
        cur["amount"] = q2(cur["amount"] + line["amount"])
    return [table[k] for k in sorted(table)]


def payment_totals(settlements):
    keys = ["meter_total", "cash_amount", "paytm_amount", "ccms_amount", "credit_amount",
            "cash_given_to_creditor_amount", "difference"]
    return {k: q2(sum((D(s.get(k)) for s in settlements), ZERO)) for k in keys}


def salesman_rows(from_date, to_date):
    out = []
    for s in approved_settlements(from_date, to_date):
        out.append({"date": s["date"], "salesman": (s.get("profiles") or {}).get("name"),
                    "meter": D(s["meter_total"]), "cash": D(s["cash_amount"]), "paytm": D(s["paytm_amount"]),
                    "ccms": D(s["ccms_amount"]), "credit": D(s["credit_amount"]),
                    "difference": D(s["difference"])})
    return out


def daily_summary(on_date):
    sett = approved_settlements(on_date, on_date)
    t = money.txns(on_date, on_date)
    flows = {}
    for x in t:
        k = (x["account"], x["kind"])
        flows[k] = q2(flows.get(k, ZERO) + D(x["amount"]))
    return {
        "settlements": sett, "fuel": sales_by_fuel(sett), "payments": payment_totals(sett),
        "flows": flows, "balances": money.balances(on_date),
    }


def pnl(from_date, to_date):
    sett = approved_settlements(from_date, to_date)
    fuel = sales_by_fuel(sett)
    sales_amt = q2(sum((v["amount"] for v in fuel.values()), ZERO))
    cost, missing = cost_of_sales({ft: v["liters"] for ft, v in fuel.items()}, stock.last_purchase_rates(to_date))
    exp = rows(db().table("expenses").select("amount, category").eq("status", "approved")
               .gte("date", from_date).lte("date", to_date).execute())
    exp_total = q2(sum((D(e["amount"]) for e in exp), ZERO))
    by_cat = {}
    for e in exp:
        by_cat[e["category"]] = q2(by_cat.get(e["category"], ZERO) + D(e["amount"]))
    return {**profit_loss(sales_amt, cost, exp_total), "missing_cost": missing, "by_category": by_cat,
            "fuel": fuel}


# ---------------- Owner: audit check ----------------
def consistency_check():
    """Tank stock = stock_moves ka jod? Party balance = approved entries ka jod?"""
    problems = []
    for tk in rows(db().table("stock_tanks").select("*").eq("is_active", True).execute()):
        total = q2(sum((D(m["delta"]) for m in stock.moves(tk["fuel_type"])), ZERO))
        if total != q2(tk["current_stock"]):
            problems.append(f"{tk['fuel_type']} tank: stock {q2(tk['current_stock'])} L, register {total} L")
    from core.calc import CREDIT_SIGN
    for p in rows(db().table("credit_parties").select("*").execute()):
        tx = rows(db().table("credit_transactions").select("type, amount").eq("party_id", p["id"])
                  .eq("status", "approved").execute())
        total = q2(sum((D(t["amount"]) * CREDIT_SIGN.get(t["type"], 0) for t in tx), ZERO))
        if total != q2(p["current_balance"]):
            problems.append(f"Party {p['name']}: balance {q2(p['current_balance'])}, khata {total}")
    for k, v in money.balances().items():
        if k[0] in ("cash", "paytm", "ccms") and v < 0:
            problems.append(f"{k[0]} balance minus: {v}")
    pend = len(rows(db().table("settlements").select("id").neq("status", "approved").execute()))
    return problems, pend


BACKUP_TABLES = ["profiles", "bank_accounts", "oil_companies", "nozzles", "fuel_rates", "stock_tanks", "shifts",
                 "shift_assignments", "daily_testing", "sale_entries", "settlements", "credit_parties",
                 "credit_transactions", "money_txns", "stock_moves", "fuel_inward", "stock_dips", "expenses",
                 "audit_log"]


def backup():
    out = {}
    for t in BACKUP_TABLES:
        data, start = [], 0
        while True:
            chunk = rows(db().table(t).select("*").order("id").range(start, start + 999).execute())
            data += chunk
            if len(chunk) < 1000:
                break
            start += 1000
        out[t] = data
    return out
