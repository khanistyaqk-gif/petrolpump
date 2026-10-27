"""Money Control: balances, cash deposit, Paytm/CCMS settlement, oil company payment, ledger."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.db import today_ist
from core.ui import correction_box, flash, num, rs, run
from repo import accounts, money

MGR = ("owner", "manager")


def _date(key):
    return st.date_input("Date", value=date.fromisoformat(today_ist()), key=key).isoformat()


def balance_cards():
    bal = money.balances()
    banks, oils = accounts.name_maps()
    c = st.columns(3)
    for col, acc in zip(c, ["cash", "paytm", "ccms"]):
        col.metric(money.ACCOUNT_LABELS[acc], rs(bal.get((acc, None), 0)))
    bank_rows = [(banks.get(k[1], "?"), v) for k, v in bal.items() if k[0] == "bank"]
    if bank_rows:
        cols = st.columns(len(bank_rows))
        for col, (n, v) in zip(cols, bank_rows):
            col.metric(f"🏦 {n}", rs(v))
    oil_rows = [(oils.get(k[1], "?"), v) for k, v in bal.items() if k[0] == "oil"]
    if oil_rows:
        cols = st.columns(len(oil_rows))
        for col, (n, v) in zip(cols, oil_rows):
            col.metric(f"🛢️ Payable to {n}", rs(v))


def page():
    me = auth.require(*MGR)
    st.header("💵 Money Control")
    flash()
    balance_cards()

    banks = accounts.banks()
    oils = accounts.oil_companies()
    bank_ids = [b["id"] for b in banks]
    bank_name = {b["id"]: b["name"] for b in banks}
    oil_ids = [o["id"] for o in oils]
    oil_name = {o["id"]: o["name"] for o in oils}
    if not banks or not oils:
        st.warning("Please add bank accounts and oil companies in Owner > Settings.")

    tabs = st.tabs(["Cash deposit", "Paytm settlement", "CCMS adjustment", "Oil company payment", "Ledger",
                    "🛢️ Oil company ledger"])
    with tabs[0]:
        with st.form("dep", clear_on_submit=True):
            d = _date("dep_d")
            amt = num("Amount", "dep_a")
            b = st.selectbox("Bank", bank_ids, format_func=bank_name.get) if banks else None
            ref = st.text_input("Slip / reference", key="dep_r")
            ok = st.form_submit_button("Save", type="primary", disabled=not banks)
        if ok:
            run(money.cash_deposit, d, amt, b, ref, "", me["id"], success="Cash deposit recorded.")
    with tabs[1]:
        st.caption("Paytm / UPI amount credited to the bank.")
        with st.form("ptm", clear_on_submit=True):
            d = _date("ptm_d")
            amt = num("Amount", "ptm_a")
            b = st.selectbox("Bank", bank_ids, format_func=bank_name.get, key="ptm_b") if banks else None
            ref = st.text_input("UTR / reference", key="ptm_r")
            ok = st.form_submit_button("Save", type="primary", disabled=not banks)
        if ok:
            run(money.paytm_settlement, d, amt, b, ref, "", me["id"], success="Paytm settlement recorded.")
    with tabs[2]:
        st.caption("CCMS is not credited to the bank — it is adjusted against the amount payable to the oil company.")
        with st.form("ccms", clear_on_submit=True):
            d = _date("cc_d")
            amt = num("Amount", "cc_a")
            o = st.selectbox("Oil company", oil_ids, format_func=oil_name.get, key="cc_o") if oils else None
            ref = st.text_input("Reference", key="cc_r")
            ok = st.form_submit_button("Save", type="primary", disabled=not oils)
        if ok:
            run(money.ccms_adjust, d, amt, o, ref, "", me["id"], success="CCMS adjustment recorded.")
    with tabs[3]:
        with st.form("oilpay", clear_on_submit=True):
            d = _date("op_d")
            amt = num("Amount", "op_a")
            o = st.selectbox("Oil company", oil_ids, format_func=oil_name.get, key="op_o") if oils else None
            b = st.selectbox("Paid from bank", bank_ids, format_func=bank_name.get, key="op_b") if banks else None
            ref = st.text_input("UTR / reference", key="op_r")
            ok = st.form_submit_button("Save", type="primary", disabled=not (banks and oils))
        if ok:
            run(money.oil_payment, d, amt, b, o, ref, "", me["id"], success="Oil company payment recorded.")
    with tabs[4]:
        c1, c2 = st.columns(2)
        f = c1.date_input("From", value=date.fromisoformat(today_ist()), key="led_f").isoformat()
        t = c2.date_input("To", value=date.fromisoformat(today_ist()), key="led_t").isoformat()
        acc = st.selectbox("Account", ["all"] + money.ACCOUNTS,
                           format_func=lambda a: "All accounts" if a == "all" else money.ACCOUNT_LABELS[a])
        data = money.txns(f, t, None if acc == "all" else acc)
        done = money.reversed_groups()
        banks_all, oils_all = accounts.name_maps()
        if data:
            st.dataframe(pd.DataFrame([{
                "Date": x["date"],
                "Account": money.ACCOUNT_LABELS[x["account"]] + (
                    f" · {banks_all.get(x['bank_account_id'])}" if x.get("bank_account_id") else "") + (
                    f" · {oils_all.get(x['oil_company_id'])}" if x.get("oil_company_id") else ""),
                "Transaction": money.KIND_LABELS.get(x["kind"], x["kind"]),
                "In (+)": rs(x["amount"]) if float(x["amount"]) > 0 else "",
                "Out (−)": rs(-float(x["amount"])) if float(x["amount"]) < 0 else "",
                "Reference": x.get("ref_id") or "", "Remarks": x.get("note") or "",
                "Status": "↩️ Reversed" if (x.get("group_id") or x["id"]) in done
                          else "↩️ Reversal" if x.get("reverses_group") else "",
            } for x in data]), hide_index=True, use_container_width=True)
            if me["role"] == "owner":
                seen, can = set(), []
                for x in data:
                    g = x.get("group_id") or x["id"]
                    if (x["kind"] in money.REVERSIBLE and x["kind"] != "opening" and not x.get("reverses_group")
                            and g not in done and g not in seen):
                        seen.add(g)
                        can.append(x)
                correction_box("rev_money", can, lambda x: (
                    f"#{x.get('group_id') or x['id']} · {x['date']} · {money.KIND_LABELS.get(x['kind'])} · "
                    f"{rs(abs(float(x['amount'])))} · {x.get('ref_id') or ''}"), money.reverse, me["id"],
                    title="↩️ Reverse a wrong transfer",
                    note="Both sides of the transfer are reversed with today's date. Opening balances are "
                         "reversed in Owner > Settings; party payments in Credit Parties; purchases in Stock; "
                         "expenses in Expenses.", success="Transfer reversed.")
        else:
            st.info("No transactions in this period.")
    with tabs[5]:
        oil_ledger_tab(oils)


def oil_ledger_tab(oils):
    """IOCL jaisi company ka khata: invoice (+), CCMS adjust (−), bank payment (−), baaki due."""
    from datetime import timedelta
    from core import printout
    from repo import reports
    all_oils = accounts.oil_companies(False)
    if not all_oils:
        st.info("Add an oil company in Owner > Settings.")
        return
    names = {o["id"]: o["name"] for o in all_oils}
    c1, c2, c3 = st.columns(3)
    oid = c1.selectbox("Oil company", list(names), format_func=names.get, key="ol_o")
    t = date.fromisoformat(today_ist())
    f = c2.date_input("From", value=t.replace(day=1), key="ol_f").isoformat()
    to = c3.date_input("To", value=t, key="ol_t").isoformat()
    led = money.oil_ledger(oid, f, to)
    tot = led["totals"]
    m = st.columns(4)
    m[0].metric("Opening due", rs(led["opening"]))
    m[1].metric("Invoices (+)", rs(tot["invoice"]))
    m[2].metric("CCMS + payments (−)", rs(-(tot["ccms"] + tot["payment"])))
    m[3].metric("Closing due", rs(led["closing"]))
    ccms_left = money.balance("ccms")
    if ccms_left > 0:
        st.info(f"CCMS collected but not yet adjusted: {rs(ccms_left)}. When it shows in the {names[oid]} account "
                "statement, record it in the CCMS adjustment tab — the due will reduce.")
    if led["lines"]:
        st.dataframe(pd.DataFrame([{
            "Date": x["date"], "Particulars": x["label"] + (" (reversal)" if x["reversal"] else ""),
            "Invoice / note": x["note"], "Reference": x["ref"] or "",
            "Invoice (+)": rs(x["debit"]) if x["debit"] else "", "Paid / CCMS (−)": rs(x["credit"]) if x["credit"] else "",
            "Balance due": rs(x["balance"]),
        } for x in led["lines"]]), hide_index=True, use_container_width=True)
    else:
        st.info("No entries in this period.")
    html = printout.oil_ledger_html({"company": names[oid], "from": f, "to": to, **led}, reports.pump_info())
    st.download_button("🖨️ Print ledger", html.encode("utf-8"), file_name=f"oil_ledger_{names[oid]}_{f}_{to}.html",
                       mime="text/html", key=f"olp_{oid}_{f}_{to}", use_container_width=True)
