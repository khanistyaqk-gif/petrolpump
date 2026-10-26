import pandas as pd
import streamlit as st

from core.auth import current_user
from core.perms import require
from core.ui import liters, money, show_error
from views.common import flash, show_flash, table
from services import calc, sales as sales_svc, settlement as st_svc


def _context():
    res = sales_svc.my_context(current_user())
    if not res.ok:
        st.warning(res.error or "Could not load your duty.")
        if res.where and res.error and "No active duty" not in res.error:
            st.caption(f"Where: {res.where}")
        return None
    return res.data


@require("salesman")
def home():
    ctx = _context()
    if not ctx:
        return
    st.metric("Total sale so far", money(ctx["total_sale"]))
    st.caption(f"Duty #{ctx['shift']['id']} · sale status: {ctx['settlement_status'] or 'not submitted'}")
    if ctx["settlement"] and ctx["settlement_status"] in ("rejected", "hold"):
        st.warning(f"Manager note: {ctx['settlement'].get('manager_note') or '-'}")
    st.subheader("My nozzles")
    if not ctx["assignments"]:
        st.info("No nozzle is assigned to you yet. Ask the manager.")
    else:
        st.dataframe(table(ctx["assignments"], ["nozzle_name", "fuel_type", "opening_reading"]),
                     use_container_width=True, hide_index=True)


@require("salesman")
def sale_entry():
    show_flash()
    me = current_user()
    ctx = _context()
    if not ctx:
        return
    locked = ctx["settlement_status"] in sales_svc.LOCKED
    if locked:
        st.info(f"Sale already sent to manager ({ctx['settlement_status']}). New entries are closed.")
    elif not ctx["assignments"]:
        st.info("No nozzle is assigned to you yet. Ask the manager.")
    else:
        with st.form("sale_form", clear_on_submit=True):
            a = st.selectbox("Nozzle", ctx["assignments"], format_func=lambda x: f"{x['nozzle_name']} ({x['fuel_type']})")
            lit = st.number_input("Liters sold", min_value=0.0, step=0.01, format="%.2f")
            add = st.form_submit_button("Add sale", type="primary")
        if add:
            r = sales_svc.add_sale(me, ctx["shift"], a, lit)
            if r.ok:
                flash("success", "Sale added.")
                st.rerun()
            else:
                show_error(r)

    st.subheader("My entries")
    st.metric("Total", money(ctx["total_sale"]))
    names = {a["nozzle_id"]: a["nozzle_name"] for a in ctx["assignments"]}
    for e in reversed(ctx["entries"]):
        c1, c2 = st.columns([5, 1])
        c1.write(f"{str(e['entry_time'])[11:16]} · {names.get(e['nozzle_id'], e['nozzle_id'])} · {liters(e['liters'])} × {money(e['rate'])} = **{money(e['amount'])}** · {e['status']}")
        if not locked and e["status"] == "pending":
            if c2.button("Cancel", key=f"cancel_{e['id']}"):
                r = sales_svc.cancel_sale(me, e["id"])
                if r.ok:
                    flash("success", "Entry cancelled.")
                    st.rerun()
                else:
                    show_error(r)


@require("salesman")
def breakup():
    show_flash()
    me = current_user()
    ctx = _context()
    if not ctx:
        return
    total = ctx["total_sale"]
    st.metric("Total sale", money(total))
    status = ctx["settlement_status"]
    if status in sales_svc.LOCKED:
        return st.info(f"Already submitted (status: {status}). Waiting for manager.")
    if total <= 0:
        return st.info("Add your sale entries first.")

    cash = st.number_input("Cash", min_value=0.0, step=1.0, format="%.2f", key="bk_cash")
    paytm = st.number_input("Paytm", min_value=0.0, step=1.0, format="%.2f", key="bk_paytm")
    ccms = st.number_input("CCMS", min_value=0.0, step=1.0, format="%.2f", key="bk_ccms")
    m = calc.payment_match(total, cash, paytm, ccms)
    st.metric("Still to enter", money(m["difference"]))
    if m["is_matched"]:
        st.success("Matches total sale.")
    if st.button("Submit to manager", type="primary", disabled=not m["is_matched"]):
        r = st_svc.submit_breakup(me, ctx["shift"], cash, paytm, ccms)
        if r.ok:
            for k in ("bk_cash", "bk_paytm", "bk_ccms"):
                st.session_state.pop(k, None)
            flash("success", "Submitted to manager.")
            st.rerun()
        else:
            show_error(r)
