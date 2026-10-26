"""Salesman: Meri Duty (sale entry + hisaab) aur Meri Entries."""
import pandas as pd
import streamlit as st

from core import auth
from core.calc import ZERO, D, q2
from core.ui import flash, fuel, lt, num, rs, run, status_label
from repo import credit, duties, rates, sales, settlements


def duty_page():
    me = auth.require("salesman")
    duty = duties.active_duty_for(me["id"])
    st.header("⛽ Meri Duty")
    flash()
    if not duty:
        st.warning("Aapki duty chalu nahi hai.")
        return

    s = settlements.for_shift(duty["id"])
    submitted = bool(s and s.get("breakup_submitted_at"))
    editable = not submitted and not (s and s.get("status") in ("hold", "approved"))
    st.caption(f"{me['name']} · Duty {duty.get('date')}")
    if s and s.get("status") == "reopened":
        st.warning(f"Manager ne hisaab wapas bheja: {s.get('manager_note') or ''}. Sudhaar ke dobara bhejein.")

    nozzles = sales.duty_nozzles(duty["id"], me["id"])
    if not nozzles:
        st.info("Abhi koi nozzle allot nahi hua. Manager se allot karwayein.")
        return
    for a in nozzles:
        n = a.get("nozzles") or {}
        r = rates.rate_for(n.get("fuel_type"), duty.get("date"))
        st.write(f"**{n.get('nozzle_name')}** · {fuel(n.get('fuel_type'))} · rate {rs(r) if r else '❗ set nahi'} · "
                 f"opening {lt(a.get('opening_reading'))}")

    # ---- Sale entry ----
    st.subheader("Sale entry")
    if editable:
        with st.form("sale", clear_on_submit=True):
            ids = [a["nozzle_id"] for a in nozzles]
            nid = st.selectbox("Nozzle", ids, format_func=lambda i: next(
                (a.get("nozzles") or {}).get("nozzle_name") for a in nozzles if a["nozzle_id"] == i))
            liters = num("Litre", "sale_l", value=0.0)
            ok = st.form_submit_button("Entry jodein", type="primary", use_container_width=True)
        if ok:
            run(sales.add_entry, me["id"], nid, liters, success="Entry jud gayi.")

    entries = sales.live_entries(duty["id"], me["id"])
    total = sales.entries_total(duty["id"], me["id"])
    st.metric("Meri entries ka total", rs(total))
    for e in entries[:30]:
        c1, c2 = st.columns([4, 1])
        c1.write(f"{(e.get('nozzles') or {}).get('nozzle_name')} · {lt(e.get('liters'))} × {rs(e.get('rate'))} = "
                 f"**{rs(e.get('amount'))}**")
        if editable and (e.get("status") or "pending") == "pending":
            if c2.button("Kaatein", key=f"x_{e['id']}"):
                run(sales.cancel_entry, e["id"], me["id"], success="Entry kat gayi.")

    # ---- Hisaab ----
    st.subheader("Duty ka hisaab")
    if submitted or (s and s.get("status") in ("hold", "approved")):
        st.info(status_label(s.get("status")))
        c = st.columns(2)
        c[0].metric("Cash", rs(s.get("cash_amount")))
        c[1].metric("Paytm", rs(s.get("paytm_amount")))
        c = st.columns(2)
        c[0].metric("CCMS", rs(s.get("ccms_amount")))
        c[1].metric("Credit", rs(s.get("credit_amount")))
        st.write(f"Manager ko cash jama: **{rs(s.get('cash_transfer_expected'))}**")
        return

    cash = num("Cash", "b_cash")
    paytm = num("Paytm / UPI", "b_paytm")
    ccms = num("CCMS / Card", "b_ccms")

    parties = credit.list_parties(active_only=True)
    items = []
    if parties:
        count = st.number_input("Kitni credit party?", min_value=0, max_value=20, value=0, step=1, key="b_cnt")
        by_id = {p["id"]: p for p in parties}
        for i in range(int(count)):
            with st.container(border=True):
                pid = st.selectbox("Party", list(by_id), key=f"b_p_{i}", format_func=lambda x: by_id[x]["name"])
                allowed = credit.vehicles_of(by_id[pid])
                if allowed:
                    vehicle = st.selectbox("Gaadi", allowed, key=f"b_v_{i}")
                else:
                    vehicle = st.text_input("Gaadi number", key=f"b_vt_{i}")
                amt = num("Fuel udhaar (₹)", f"b_a_{i}")
                given = num("Party ko cash diya (₹)", f"b_g_{i}", help="Galle se party ko diya cash. Sale mein nahi judta.")
                comment = st.text_input("Comment / slip no.", key=f"b_c_{i}")
                items.append({"party_id": pid, "amount": amt, "cash_given": given,
                              "vehicle": vehicle, "comment": comment})

    credit_sum = q2(sum((D(i["amount"]) for i in items), ZERO))
    given_sum = q2(sum((D(i["cash_given"]) for i in items), ZERO))
    pay = q2(cash + paytm + ccms + credit_sum)
    diff = q2(total - pay)
    st.write(f"Entries **{rs(total)}** · Payment **{rs(pay)}** · "
             + ("✅ barabar" if diff == 0 else f"❗ farak {rs(diff)}"))
    if given_sum > 0:
        st.caption(f"Manager ko cash jama hoga: {rs(cash - given_sum)}")

    if st.button("Hisaab Manager ko bhejein", type="primary", use_container_width=True, disabled=diff != 0):
        warnings = run(settlements.submit_breakup, me["id"], cash, paytm, ccms, items, rerun=False)
        if warnings is not False:
            msg = "Hisaab bhej diya. Manager approve karega."
            if isinstance(warnings, list) and warnings:
                msg += " ⚠️ " + " ".join(warnings)
            st.session_state["_flash"] = msg
            st.rerun()


def entries_page():
    me = auth.require("salesman")
    st.header("📋 Meri Entries")
    data = sales.history(me["id"])
    if not data:
        st.info("Abhi koi entry nahi.")
        return
    st.dataframe(pd.DataFrame([{
        "Tarikh": e.get("date"), "Nozzle": (e.get("nozzles") or {}).get("nozzle_name"),
        "Litre": lt(e.get("liters")), "Rate": rs(e.get("rate")), "Amount": rs(e.get("amount")),
        "Status": status_label(e.get("status")) if e.get("status") != "cancelled" else "Kata",
    } for e in data]), hide_index=True, use_container_width=True)
