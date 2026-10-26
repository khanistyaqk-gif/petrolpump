"""Stock: tanker inward, dip, stock register."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core import auth
from core.db import today_ist
from core.ui import flash, fuel, lt, num, rs, run, status_label
from repo import accounts, stock, tanks

MGR = ("owner", "manager")


def page():
    me = auth.require(*MGR)
    st.header("🛢️ Stock")
    flash()
    tk = tanks.list_tanks()
    if not tk:
        st.warning("Koi tank nahi. Owner > Tanks.")
        return
    cols = st.columns(len(tk))
    for col, t in zip(cols, tk):
        col.metric(fuel(t["fuel_type"]), lt(t["current_stock"]), help=f"Capacity {lt(t['capacity_liters'])}")
    fuels = [t["fuel_type"] for t in tk]
    oils = accounts.oil_companies()
    oil_name = {o["id"]: o["name"] for o in accounts.oil_companies(False)}

    tabs = st.tabs(["Tanker inward", "Dip (physical stock)", "Stock register"])
    with tabs[0]:
        with st.form("inward", clear_on_submit=True):
            d = st.date_input("Tarikh", value=date.fromisoformat(today_ist()), key="in_d").isoformat()
            ft = st.selectbox("Fuel", fuels, format_func=fuel, key="in_f")
            o = st.selectbox("Oil company", [x["id"] for x in oils], format_func=oil_name.get) if oils else None
            inv = st.text_input("Bill number")
            liters = num("Litre (jo tank mein utra)", "in_l")
            amount = num("Bill amount (₹)", "in_a")
            note = st.text_input("Note", key="in_n")
            ok = st.form_submit_button("Save (approve ke liye)", type="primary", disabled=not oils)
        if not oils:
            st.caption("Owner > Settings mein oil company jodein.")
        if ok:
            run(stock.add_inward, d, ft, o, inv, liters, amount, note, me["id"], success="Inward darj. Ab approve karein.")
        _approval_list("fuel_inward", stock.inwards("pending"), me, lambda r: (
            f"{r['date']} · {fuel(r['fuel_type'])} · {lt(r['liters'])} · {rs(r['amount'])} · "
            f"{oil_name.get(r['oil_company_id'])} · bill {r.get('invoice_no') or '-'}"), stock.approve_inward)
        hist = stock.inwards("approved", 30)
        if hist:
            st.caption("Approved inward")
            st.dataframe(pd.DataFrame([{"Tarikh": r["date"], "Fuel": fuel(r["fuel_type"]), "Litre": lt(r["liters"]),
                                        "Bill": rs(r["amount"]), "Company": oil_name.get(r["oil_company_id"]),
                                        "Bill no.": r.get("invoice_no") or ""} for r in hist]),
                         hide_index=True, use_container_width=True)

    with tabs[1]:
        st.caption("Dip se napa asli stock. Approve par farak (asli − book) tank mein adjust hoga.")
        with st.form("dip", clear_on_submit=True):
            d = st.date_input("Tarikh", value=date.fromisoformat(today_ist()), key="dp_d").isoformat()
            ft = st.selectbox("Fuel", fuels, format_func=fuel, key="dp_f")
            cm = num("Dip (cm) — optional", "dp_cm")
            phys = num("Asli stock (L)", "dp_p")
            note = st.text_input("Note", key="dp_n")
            ok = st.form_submit_button("Save (approve ke liye)", type="primary")
        if ok:
            run(stock.add_dip, d, ft, phys, cm, note, me["id"], success="Dip darj. Ab approve karein.")
        _approval_list("stock_dips", stock.dips("pending"), me, lambda r: (
            f"{r['date']} · {fuel(r['fuel_type'])} · asli {lt(r['physical_liters'])} · book {lt(r['book_liters'])} · "
            f"farak {lt(r['variance'])}"), stock.approve_dip)

    with tabs[2]:
        c1, c2, c3 = st.columns(3)
        ft = c1.selectbox("Fuel", fuels, format_func=fuel, key="rg_f")
        t = date.fromisoformat(today_ist())
        f = c2.date_input("Se", value=t - timedelta(days=6), key="rg_s").isoformat()
        to = c3.date_input("Tak", value=t, key="rg_t").isoformat()
        reg = stock.register(ft, f, to)
        if reg:
            st.dataframe(pd.DataFrame([{
                "Tarikh": r["date"], "Opening": lt(r["opening_balance"] + r["new_tank"]), "Inward": lt(r["inward"]),
                "Sale": lt(-r["sale"]), "Dip farak": lt(r["dip_adjust"]), "Sudhaar": lt(r["correction"]),
                "Closing": lt(r["closing"]),
            } for r in reg]), hide_index=True, use_container_width=True)
        else:
            st.info("Is samay mein koi badlav nahi.")


def _approval_list(table, items, me, label, approve_fn):
    if not items:
        return
    st.subheader("Approve baaki")
    for r in items:
        c1, c2, c3 = st.columns([5, 1, 1])
        c1.write(label(r) + f" · {status_label(r['status'])}")
        if c2.button("✅", key=f"ap_{table}_{r['id']}", help="Approve"):
            run(approve_fn, r["id"], me["id"], success="Approve ho gaya.")
        if c3.button("❌", key=f"rj_{table}_{r['id']}", help="Reject"):
            run(stock.reject, table, r["id"], me["id"], success="Reject kar diya.")
