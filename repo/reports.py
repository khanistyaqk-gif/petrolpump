"""
Reports. Sale hamesha approved settlement ke SAVED snapshot se (T3: baad ka rate badlav purana amount nahi badalta).
"""
from core.calc import ZERO, D, cost_of_sales, profit_loss, q2
from core.db import db, one, rows
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


# ---------------- Print reports ----------------
def pump_info():
    from core.db import setting
    return {"name": setting("PUMP_NAME", "Petrol Pump"), "address": setting("PUMP_ADDRESS", "")}


def settlement_print_data(settlement_id):
    s = one(db().table("settlements").select("*").eq("id", settlement_id).limit(1).execute())
    if not s:
        return None
    names = {p["id"]: p["name"] for p in rows(db().table("profiles").select("id, name").execute())}
    shift = one(db().table("shifts").select("started_at, ended_at").eq("id", s["shift_id"]).limit(1).execute()) or {}
    tx = rows(db().table("credit_transactions").select("*, credit_parties:party_id(name)")
              .eq("reference_id", str(s["id"])).in_("type", ["sale", "cash_given"])
              .in_("status", ["approved", "pending", "hold"]).order("id").execute())
    credit = [{"party": (t.get("credit_parties") or {}).get("name"), "type": t["type"], "amount": D(t["amount"]),
               "note": t.get("note")} for t in tx]
    return {"settlement": s, "salesman": names.get(s["salesman_id"], "—"), "approver": names.get(s.get("approved_by")),
            "started_at": shift.get("started_at"), "credit": credit}


def day_summary_data(on_date):
    from core.db import FUEL_TYPES
    all_s = rows(db().table("settlements").select("*").eq("date", on_date).order("id").execute())
    names = {p["id"]: p["name"] for p in rows(db().table("profiles").select("id, name").execute())}
    keys = ("sale", "cash", "paytm", "ccms", "credit", "cash_given", "cash_jama", "difference")
    total = {k: ZERO for k in keys} | {"liters": {}}
    out, pending, used_fuels = [], [], set()
    for s in all_s:
        if s.get("status") != "approved":
            pending.append({"salesman": names.get(s["salesman_id"], "—"), "status": s.get("status")})
            continue
        liters = {}
        for r in s.get("nozzle_readings") or []:
            ft = r.get("fuel_type")
            liters[ft] = q2(liters.get(ft, ZERO) + D(r.get("net_sale_liters")))
            used_fuels.add(ft)
        row = {"salesman": names.get(s["salesman_id"], "—"), "liters": liters,
               "sale": q2(s["meter_total"]), "cash": q2(s["cash_amount"]), "paytm": q2(s["paytm_amount"]),
               "ccms": q2(s["ccms_amount"]), "credit": q2(s["credit_amount"]),
               "cash_given": q2(s["cash_given_to_creditor_amount"]), "cash_jama": q2(s["cash_transfer_expected"]),
               "difference": q2(s["difference"])}
        out.append(row)
        for k in keys:
            total[k] = q2(total[k] + row[k])
        for ft, v in liters.items():
            total["liters"][ft] = q2(total["liters"].get(ft, ZERO) + v)
    fuels = [f for f in FUEL_TYPES if f in used_fuels]

    # Creditor list: sirf approved duty ki approved credit entries
    approved = {str(s["id"]): names.get(s["salesman_id"], "—") for s in all_s if s.get("status") == "approved"}
    credit_lines = {}
    if approved:
        tx = rows(db().table("credit_transactions").select("*, credit_parties:party_id(name)")
                  .in_("reference_id", list(approved)).in_("type", ["sale", "cash_given"])
                  .eq("status", "approved").order("id").execute())
        for t in tx:
            party = (t.get("credit_parties") or {}).get("name") or "—"
            key = (t["reference_id"], t["party_id"], t.get("note") or "")
            line = credit_lines.setdefault(key, {"party": party, "salesman": approved.get(t["reference_id"], "—"),
                                                 "note": t.get("note") or "", "fuel": ZERO, "cash": ZERO})
            line["fuel" if t["type"] == "sale" else "cash"] = q2(line["fuel" if t["type"] == "sale" else "cash"]
                                                                 + D(t["amount"]))
    credit_list = sorted(credit_lines.values(), key=lambda x: (x["party"], x["salesman"]))
    by_party = {}
    for c in credit_list:
        p = by_party.setdefault(c["party"], {"party": c["party"], "fuel": ZERO, "cash": ZERO})
        p["fuel"] = q2(p["fuel"] + c["fuel"])
        p["cash"] = q2(p["cash"] + c["cash"])
    # Creditor se aaj mila paisa (Manager ne Credit Party page par darj kiya)
    banks = {b["id"]: b["name"] for b in rows(db().table("bank_accounts").select("id, name").execute())}
    pay = rows(db().table("credit_transactions").select("*, credit_parties:party_id(name)")
               .eq("type", "payment_received").eq("status", "approved").eq("date", on_date).order("id").execute())
    received, by_mode = [], {"cash": ZERO, "bank": ZERO, "paytm": ZERO, "ccms": ZERO}
    for p in pay:
        mode = p.get("payment_mode") or "cash"
        amt = q2(p["amount"])
        received.append({"party": (p.get("credit_parties") or {}).get("name") or "—", "mode": mode,
                         "bank": banks.get(p.get("bank_account_id")) if mode == "bank" else "",
                         "ref": p.get("reference_id") or "", "note": p.get("note") or "", "amount": amt})
        by_mode[mode] = q2(by_mode.get(mode, ZERO) + amt)

    # Din ki kul aawak (mode-wise): salesman se + creditor se
    inflow = {
        "cash": q2(total["cash_jama"] + by_mode["cash"]),
        "paytm": q2(total["paytm"] + by_mode["paytm"]),
        "ccms": q2(total["ccms"] + by_mode["ccms"]),
        "bank": by_mode["bank"],
    }
    return {"date": on_date, "rows": out, "total": total, "pending": pending, "fuels": fuels,
            "credit": credit_list, "credit_by_party": sorted(by_party.values(), key=lambda x: x["party"]),
            "received": received, "received_by_mode": by_mode, "inflow": inflow}
