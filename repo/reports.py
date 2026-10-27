"""
Reports. Sale hamesha approved settlement ke SAVED snapshot se (T3: baad ka rate badlav purana amount nahi badalta).
"""
from core.calc import ZERO, D, cost_of_sales, profit_loss, q2, short_excess_label
from core.db import db, fetch_all, one, rows
from repo import money, stock


def approved_settlements(from_date, to_date):
    return fetch_all(lambda: db().table("settlements").select("*, profiles:salesman_id(name)").eq("status", "approved")
                     .gte("date", from_date).lte("date", to_date).order("date").order("id"))


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
    exp = fetch_all(lambda: db().table("expenses").select("id, amount, category").eq("status", "approved")
                    .gte("date", from_date).lte("date", to_date).order("id"))
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
        tx = fetch_all(lambda: db().table("credit_transactions").select("type, amount, id").eq("party_id", p["id"])
                       .eq("status", "approved").order("id"))
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


# ------------------------------------------------------------------ Owner: din ki closing position
def _prev_day(d):
    from datetime import date, timedelta
    return (date.fromisoformat(d) - timedelta(days=1)).isoformat()


def owner_closing_data(on_date):
    """Din ke ant ki poori position: sale, stock, cash/bank/Paytm/CCMS, oil company, credit parties, alerts."""
    from core.calc import CREDIT_SIGN
    from core.db import FUEL_LABELS, FUEL_TYPES
    from repo import accounts, rates

    prev = _prev_day(on_date)
    day = day_summary_data(on_date)
    sett = approved_settlements(on_date, on_date)
    fuel = sales_by_fuel(sett)
    pay = payment_totals(sett)
    rate_today = rates.current_rates(on_date)

    # Sale (fuel-wise)
    # Rate = saved sale amount / litres (din mein rate badla ho to bhi sahi average)
    sale_rows = [{"fuel": ft, "rate": q2(v["amount"] / v["liters"]) if v["liters"] else rate_today.get(ft),
                  "liters": v["liters"], "testing": v["testing"],
                  "amount": v["amount"]} for ft, v in fuel.items()]
    sale_rows.sort(key=lambda r: FUEL_TYPES.index(r["fuel"]) if r["fuel"] in FUEL_TYPES else 99)

    # Stock: ek hi baar saari moves (tarikh tak)
    tanks_ = rows(db().table("stock_tanks").select("*").eq("is_active", True).execute())
    mv = stock.moves(to_date=on_date)
    dips = rows(db().table("stock_dips").select("*").eq("status", "approved").eq("date", on_date).order("id").execute())
    stock_rows = []
    for t in tanks_:
        ft = t["fuel_type"]
        mine = [m for m in mv if m["fuel_type"] == ft]
        closing = q2(sum((D(m["delta"]) for m in mine), ZERO))
        today = [m for m in mine if str(m["date"]) == on_date]
        k = lambda kind: q2(sum((D(m["delta"]) for m in today if m["kind"] == kind), ZERO))  # noqa: E731
        # naya tank aaj bana ho to uska shuru ka stock "opening" mein dikhao, correction mein nahi
        opening = q2(closing - sum((D(m["delta"]) for m in today if m["kind"] != "opening"), ZERO))
        dip = next((x for x in reversed(dips) if x["fuel_type"] == ft), None)
        cap = D(t.get("capacity_liters"))
        stock_rows.append({"fuel": ft, "tank": t.get("tank_name"), "opening": opening, "inward": k("inward"),
                           "sale": -k("sale"), "dip_adjust": k("dip_adjust"), "correction": k("correction"),
                           "closing": closing, "capacity": cap,
                           "dip_physical": D(dip["physical_liters"]) if dip else None,
                           "low": cap > 0 and closing < cap * D("0.10")})

    # Paisa: kal ka closing = aaj ka opening
    banks, oils = accounts.name_maps()
    b_open, b_close = money.balances(prev), money.balances(on_date)
    keys = sorted(set(b_open) | set(b_close),
                  key=lambda k: (money.ACCOUNTS.index(k[0]), str(k[1] or "")))
    money_rows = []
    for k in keys:
        acc, ref = k
        name = money.ACCOUNT_LABELS[acc]
        if acc == "bank":
            name = f"Bank · {banks.get(ref, '?')}"
        elif acc == "oil":
            name = f"Payable to {oils.get(ref, '?')}"
        money_rows.append({"account": acc, "name": name, "opening": b_open.get(k, ZERO), "closing": b_close.get(k, ZERO)})
    for acc in ("cash", "paytm", "ccms"):
        if not any(r["account"] == acc for r in money_rows):
            money_rows.insert(0, {"account": acc, "name": money.ACCOUNT_LABELS[acc], "opening": ZERO, "closing": ZERO})
    money_rows.sort(key=lambda r: (money.ACCOUNTS.index(r["account"]), r["name"]))

    # Credit parties: tarikh tak approved entries se balance
    parties = rows(db().table("credit_parties").select("*").order("name").execute())
    tx = fetch_all(lambda: db().table("credit_transactions").select("id, party_id, date, type, amount")
                   .eq("status", "approved").lte("date", on_date).order("id"))
    party_rows = []
    for p in parties:
        mine = [t for t in tx if t["party_id"] == p["id"]]
        closing = q2(sum((D(t["amount"]) * CREDIT_SIGN.get(t["type"], 0) for t in mine), ZERO))
        today = [t for t in mine if str(t["date"]) == on_date]
        given = q2(sum((D(t["amount"]) for t in today if t["type"] in ("sale", "cash_given")), ZERO))
        received = q2(sum((D(t["amount"]) for t in today if t["type"] == "payment_received"), ZERO))
        opening = q2(closing - given + received)
        lim = D(p.get("credit_limit"))
        if closing == 0 and given == 0 and received == 0:
            continue
        party_rows.append({"party": p["name"], "phone": p.get("phone") or "", "opening": opening, "given": given,
                           "received": received, "closing": closing, "limit": lim,
                           "over": lim > 0 and closing > lim})

    # Kharcha
    exp = rows(db().table("expenses").select("*").eq("status", "approved").eq("date", on_date).order("id").execute())
    exp_rows = [{"category": e["category"], "description": e.get("description") or "",
                 "mode": "Cash" if e["payment_mode"] == "cash" else f"Bank · {banks.get(e.get('bank_account_id'), '')}",
                 "amount": q2(e["amount"])} for e in exp]

    # Dhyan dene wali baatein
    alerts = []
    if day["pending"]:
        alerts.append("Settlements not yet approved (not counted in sale): "
                      + ", ".join(f"{p['salesman']}" for p in day["pending"]))
    live = rows(db().table("shifts").select("id").eq("is_active", True).execute())
    if live:
        alerts.append(f"{len(live)} shift(s) still running.")
    for tbl, label in (("fuel_inward", "fuel purchase(s)"), ("stock_dips", "dip entr(ies)"), ("expenses", "expense(s)")):
        n = len(rows(db().table(tbl).select("id").eq("status", "pending").execute()))
        if n:
            alerts.append(f"{n} {label} waiting for approval.")
    if q2(pay["difference"]) != 0:
        alerts.append(f"Salesman short / excess for the day: {short_excess_label(pay['difference'])}.")
    for r in party_rows:
        if r["over"]:
            alerts.append(f"{r['party']} is over the credit limit (₹{r['closing']} against limit ₹{q2(r['limit'])}).")
    for r in stock_rows:
        if r["low"]:
            alerts.append(f"{r['tank'] or FUEL_LABELS.get(r['fuel'])}: stock below 10% of capacity.")
        if r["closing"] < 0:
            alerts.append(f"{r['tank'] or FUEL_LABELS.get(r['fuel'])}: stock is negative — check purchases / dip.")
    if not dips:
        alerts.append("No dip reading approved for this date (physical stock not verified).")
    for ft in fuel:
        if not rate_today.get(ft):
            alerts.append(f"No fuel rate set for {FUEL_LABELS.get(ft, ft)}.")

    return {"date": on_date, "sale": sale_rows, "payments": pay, "testing_total": q2(sum((r["testing"] for r in sale_rows), ZERO)),
            "shifts": len(sett), "stock": stock_rows, "money": money_rows, "parties": party_rows,
            "party_total": q2(sum((r["closing"] for r in party_rows), ZERO)),
            "credit_given": q2(sum((r["given"] for r in party_rows), ZERO)),
            "credit_received": q2(sum((r["received"] for r in party_rows), ZERO)),
            "expenses": exp_rows, "expense_total": q2(sum((e["amount"] for e in exp_rows), ZERO)),
            "inflow": day["inflow"], "alerts": alerts}
