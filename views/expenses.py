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
    st.header("🧾 Kharcha")
    flash()
    banks = accounts.banks()
    bank_name = {b["id"]: b["name"] for b in accounts.banks(False)}
    with st.form("exp", clear_on_submit=True):
        d = st.date_input("Tarikh", value=date.fromisoformat(today_ist())).isoformat()
        cat = st.selectbox("Category", expenses.CATEGORIES)
        desc = st.text_input("Detail")
        amt = num("Amount", "ex_a")
        mode = st.selectbox("Kaise diya", ["cash", "bank"], format_func={"cash": "Cash (galla)", "bank": "Bank"}.get)
        b = st.selectbox("Bank (agar bank se)", [x["id"] for x in banks], format_func=bank_name.get) if banks else None
        ref = st.text_input("Bill / reference")
        ok = st.form_submit_button("Save (approve ke liye)", type="primary")
    if ok:
        run(expenses.add, d, cat, desc, amt, mode, b, ref, me["id"], success="Kharcha darj. Ab approve karein.")

    pending = expenses.list_("pending")
    if pending:
        st.subheader("Approve baaki")
        for e in pending:
            c1, c2, c3 = st.columns([5, 1, 1])
            c1.write(f"{e['date']} · {e['category']} · {rs(e['amount'])} · "
                     f"{'Cash' if e['payment_mode'] == 'cash' else bank_name.get(e.get('bank_account_id'))} · "
                     f"{e.get('description') or ''}")
            if c2.button("✅", key=f"ea_{e['id']}", help="Approve"):
                run(expenses.approve, e["id"], me["id"], success="Kharcha approve. Paisa minus ho gaya.")
            if c3.button("❌", key=f"er_{e['id']}", help="Reject"):
                run(expenses.reject, e["id"], me["id"], success="Reject kar diya.")

    recent = expenses.list_(limit=50)
    if recent:
        st.subheader("Haal ke kharche")
        st.dataframe(pd.DataFrame([{
            "Tarikh": e["date"], "Category": e["category"], "Amount": rs(e["amount"]),
            "Kaise": "Cash" if e["payment_mode"] == "cash" else bank_name.get(e.get("bank_account_id")),
            "Detail": e.get("description") or "", "Status": status_label(e["status"]),
        } for e in recent]), hide_index=True, use_container_width=True)
