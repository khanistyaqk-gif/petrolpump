"""Salesman: My Shift (sale entry + settlement) and My Entries."""
import pandas as pd
import streamlit as st

from core import auth
from core.calc import ZERO, D, q2
from core.ui import flash, fuel, lt, num, rs, run, status_label
from repo import credit, duties, rates, sales, settlements


def duty_page():
    me = auth.require("salesman")
    duty = duties.active_duty_for(me["id"])
    st.header("⛽ My Shift")
    flash()
    if not duty:
        st.warning("You do not have an active shift.")
        return

    s = settlements.for_shift(duty["id"])
    submitted = bool(s and s.get("breakup_submitted_at"))
    editable = not submitted and not (s and s.get("status") in ("hold", "approved"))
    st.caption(f"{me['name']} · Shift date {duty.get('date')}")
    if s and s.get("status") == "reopened":
        st.warning(f"The Manager has returned your settlement: {s.get('manager_note') or ''}. "
                   "Please correct it and submit again.")

    nozzles = sales.duty_nozzles(duty["id"], me["id"])
    if not nozzles:
        st.info("No nozzle has been assigned yet. Please ask the Manager to assign one.")
        return
    for a in nozzles:
        n = a.get("nozzles") or {}
        r = rates.rate_for(n.get("fuel_type"), duty.get("date"))
        st.write(f"**{n.get('nozzle_name')}** · {fuel(n.get('fuel_type'))} · rate {rs(r) if r else '❗ not set'} · "
                 f"opening {lt(a.get('opening_reading'))}")

    # ---- Sale entry ----
    st.subheader("Sale entry")
    st.caption("One entry per nozzle. The nozzle is locked after entry — use ✏️ Edit or ❌ Cancel to change it.")
    entries = sales.live_entries(duty["id"], me["id"])
    done_ids = {e["nozzle_id"] for e in entries}
    open_nozzles = [a for a in nozzles if a["nozzle_id"] not in done_ids]
    if editable:
        if open_nozzles:
            with st.form("sale", clear_on_submit=True):
                ids = [a["nozzle_id"] for a in open_nozzles]
                nid = st.selectbox("Nozzle", ids, format_func=lambda i: next(
                    (a.get("nozzles") or {}).get("nozzle_name") for a in open_nozzles if a["nozzle_id"] == i))
                liters = num("Litres", "sale_l", value=0.0)
                ok = st.form_submit_button("Add entry", type="primary", use_container_width=True)
            if ok:
                run(sales.add_entry, me["id"], nid, liters, success="Entry added. Nozzle locked.")
        else:
            st.success("Entries completed for all nozzles.")

    total = sales.entries_total(duty["id"], me["id"])
    st.metric("Total of my entries", rs(total))
    for e in entries:
        name = (e.get("nozzles") or {}).get("nozzle_name")
        can_change = editable and (e.get("status") or "pending") == "pending"
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 1, 1])
            c1.write(f"🔒 **{name}** · {lt(e.get('liters'))} × {rs(e.get('rate'))} = **{rs(e.get('amount'))}**")
            if can_change:
                if c2.button("✏️ Edit", key=f"ed_{e['id']}", use_container_width=True):
                    st.session_state["_editing"] = e["id"]
                if c3.button("❌ Cancel", key=f"x_{e['id']}", use_container_width=True):
                    run(sales.cancel_entry, e["id"], me["id"], success=f"Entry for {name} cancelled. Nozzle unlocked.")
            if can_change and st.session_state.get("_editing") == e["id"]:
                new_l = num("New litres", f"edl_{e['id']}", value=float(e.get("liters") or 0))
                s1, s2 = st.columns(2)
                if s1.button("Save", key=f"eds_{e['id']}", type="primary", use_container_width=True):
                    st.session_state.pop("_editing", None)
                    run(sales.edit_entry, e["id"], me["id"], new_l, success=f"Entry for {name} updated.")
                if s2.button("Discard", key=f"edc_{e['id']}", use_container_width=True):
                    st.session_state.pop("_editing", None)
                    st.rerun()

    # ---- Settlement ----
    st.subheader("Shift settlement")
    if submitted or (s and s.get("status") in ("hold", "approved")):
        st.info(status_label(s.get("status")))
        c = st.columns(2)
        c[0].metric("Cash", rs(s.get("cash_amount")))
        c[1].metric("Paytm", rs(s.get("paytm_amount")))
        c = st.columns(2)
        c[0].metric("CCMS", rs(s.get("ccms_amount")))
        c[1].metric("Credit", rs(s.get("credit_amount")))
        st.write(f"Cash to hand over to Manager: **{rs(s.get('cash_transfer_expected'))}**")
        return

    cash = num("Cash", "b_cash")
    paytm = num("Paytm / UPI", "b_paytm")
    ccms = num("CCMS / Card", "b_ccms")

    parties = credit.list_parties(active_only=True)
    items = []
    st.markdown("**Credit sales**")
    if not parties:
        st.info("No credit parties have been created. Please ask the Manager to add them on the **Credit Parties** page.")
    else:
        count = st.number_input("Number of credit parties served (one form opens for each)",
                                min_value=0, max_value=20, value=0, step=1, key="b_cnt")
        if count == 0:
            st.caption("If you made a credit sale, press + above.")
        by_id = {p["id"]: p for p in parties}
        for i in range(int(count)):
            with st.container(border=True):
                pid = st.selectbox("Party", list(by_id), key=f"b_p_{i}", format_func=lambda x: by_id[x]["name"])
                allowed = credit.vehicles_of(by_id[pid])
                if allowed:
                    vehicle = st.selectbox("Vehicle", allowed, key=f"b_v_{i}")
                else:
                    vehicle = st.text_input("Vehicle number", key=f"b_vt_{i}")
                amt = num("Fuel on credit (₹)", f"b_a_{i}")
                given = num("Cash advance to party (₹)", f"b_g_{i}",
                            help="Cash given to the party from the cash drawer. Not part of the sale.")
                comment = st.text_input("Remarks / slip no.", key=f"b_c_{i}")
                items.append({"party_id": pid, "amount": amt, "cash_given": given,
                              "vehicle": vehicle, "comment": comment})

    credit_sum = q2(sum((D(i["amount"]) for i in items), ZERO))
    given_sum = q2(sum((D(i["cash_given"]) for i in items), ZERO))
    pay = q2(cash + paytm + ccms + credit_sum)
    diff = q2(total - pay)
    st.write(f"Entries **{rs(total)}** · Payments **{rs(pay)}** · "
             + ("✅ matched" if diff == 0 else f"❗ difference {rs(diff)}"))
    if given_sum > 0:
        st.caption(f"Cash to hand over to Manager: {rs(cash - given_sum)}")

    missing = [(a.get("nozzles") or {}).get("nozzle_name") for a in nozzles if a["nozzle_id"] not in done_ids]
    if missing:
        st.warning("⚠️ No entry for: " + ", ".join(missing) +
                   ". If there was a sale, add the entry first — otherwise the Manager will see a shortage.")
    if st.button("Submit settlement to Manager", type="primary", use_container_width=True, disabled=diff != 0):
        warnings = run(settlements.submit_breakup, me["id"], cash, paytm, ccms, items, rerun=False)
        if warnings is not False:
            msg = "Settlement submitted. The Manager will review and approve it."
            if isinstance(warnings, list) and warnings:
                msg += " ⚠️ " + " ".join(warnings)
            st.session_state["_flash"] = msg
            st.rerun()


def entries_page():
    me = auth.require("salesman")
    st.header("📋 My Entries")
    data = sales.history(me["id"])
    if not data:
        st.info("No entries yet.")
        return
    st.dataframe(pd.DataFrame([{
        "Date": e.get("date"), "Nozzle": (e.get("nozzles") or {}).get("nozzle_name"),
        "Litres": lt(e.get("liters")), "Rate": rs(e.get("rate")), "Amount": rs(e.get("amount")),
        "Status": status_label(e.get("status")) if e.get("status") != "cancelled" else "Cancelled",
    } for e in data]), hide_index=True, use_container_width=True)
