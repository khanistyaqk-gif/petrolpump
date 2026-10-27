"""Expenses: entry, approval and recent list."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.db import today_ist
from core.ui import flash, num, rs, run, status_label
from repo import accounts, expenses

MGR = ("owner", "manager")


def page():
    me = auth.require(*MGR)
    st.header("🧾 Expenses")
    flash()
    banks = accounts.banks()
    bank_name = {b["id"]: b["name"] for b in accounts.banks(False)}
    with st.form("exp", clear_on_submit=True):
        d = st.date_input("Date", value=date.fromisoformat(today_ist())).isoformat()
        cat = st.selectbox("Category", expenses.CATEGORIES)
        desc = st.text_input("Description")
        amt = num("Amount", "ex_a")
        mode = st.selectbox("Paid by", ["cash", "bank"], format_func={"cash": "Cash in hand", "bank": "Bank"}.get)
        b = st.selectbox("Bank account (if paid by bank)", [x["id"] for x in banks], format_func=bank_name.get) if banks else None
        ref = st.text_input("Bill / reference no.")
        ok = st.form_submit_button("Save for approval", type="primary")
    if ok:
        run(expenses.add, d, cat, desc, amt, mode, b, ref, me["id"], success="Expense recorded. Please approve it.")

    pending = expenses.list_("pending")
    if pending:
        st.subheader("Pending approval")
        for e in pending:
            c1, c2, c3 = st.columns([5, 1, 1])
            c1.write(f"{e['date']} · {e['category']} · {rs(e['amount'])} · "
                     f"{'Cash' if e['payment_mode'] == 'cash' else bank_name.get(e.get('bank_account_id'))} · "
                     f"{e.get('description') or ''}")
            if c2.button("✅", key=f"ea_{e['id']}", help="Approve"):
                run(expenses.approve, e["id"], me["id"], success="Expense approved. Amount deducted.")
            if c3.button("❌", key=f"er_{e['id']}", help="Reject"):
                run(expenses.reject, e["id"], me["id"], success="Rejected.")

    recent = expenses.list_(limit=50)
    if recent:
        st.subheader("Recent expenses")
        st.dataframe(pd.DataFrame([{
            "Date": e["date"], "Category": e["category"], "Amount": rs(e["amount"]),
            "Paid by": "Cash" if e["payment_mode"] == "cash" else bank_name.get(e.get("bank_account_id")),
            "Description": e.get("description") or "", "Status": status_label(e["status"]),
        } for e in recent]), hide_index=True, use_container_width=True)
