"""Money Control: balances, cash deposit, Paytm/CCMS settlement, oil company payment, ledger."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.db import today_ist
from core.ui import flash, num, rs, run
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

    tabs = st.tabs(["Cash deposit", "Paytm settlement", "CCMS adjustment", "Oil company payment", "Ledger"])
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
            } for x in data]), hide_index=True, use_container_width=True)
        else:
            st.info("No transactions in this period.")
