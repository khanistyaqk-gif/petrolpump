"""Manager pages (also visible to Owner): Dashboard, Shifts, Testing, Settlement, Credit Parties."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.calc import ZERO, D, is_matched, q2, short_excess_label
from core.db import FUEL_TYPES, today_ist
from core.ui import flash, fuel, lt, num, rs, run, status_label
from repo import accounts, credit, duties, expenses, money, rates, sales, settlements, stock, tanks, testing, users

MGR = ("owner", "manager")


# ------------------------------------------------------------------ Dashboard
def dashboard():
    user = auth.require(*MGR)
    st.header("🏠 Dashboard")
    st.caption(f"Welcome, {user['name']} · {today_ist()}")
    flash()

    active = duties.active_duties()
    review = settlements.to_review()
    approved = settlements.approved_on(today_ist())
    c1, c2, c3 = st.columns(3)
    c1.metric("Active shifts", len(active))
    c2.metric("Settlements pending", len(review))
    c3.metric("Approved sales today", rs(sum((D(s.get("meter_total")) for s in approved), ZERO)))

    pend = {"Fuel purchases": len(stock.inwards("pending")), "Dip entries": len(stock.dips("pending")),
            "Expenses": len(expenses.list_("pending"))}
    if any(pend.values()):
        st.info("Pending approval — " + " · ".join(f"{k}: {v}" for k, v in pend.items() if v))
    bal = money.balances()
    c = st.columns(3)
    c[0].metric("Cash in hand", rs(bal.get(("cash", None), 0)))
    c[1].metric("Paytm (awaiting bank settlement)", rs(bal.get(("paytm", None), 0)))
    c[2].metric("CCMS (awaiting adjustment)", rs(bal.get(("ccms", None), 0)))

    st.subheader("Today's fuel rates")
    cur = rates.current_rates(today_ist())
    missing = [fuel(ft) for ft in FUEL_TYPES if not cur[ft]]
    st.write(" · ".join(f"**{fuel(ft)}** {rs(cur[ft])}" for ft in FUEL_TYPES if cur[ft]) or "No rates set")
    if missing and len(missing) < len(FUEL_TYPES):
        st.caption("Rate not set: " + ", ".join(missing))

    st.subheader("Tank stock")
    t = [x for x in tanks.list_tanks() if x.get("is_active")]
    if t:
        cols = st.columns(len(t))
        for col, x in zip(cols, t):
            col.metric(fuel(x["fuel_type"]), lt(x.get("current_stock")))
    else:
        st.warning("No tanks set up. Go to Owner > Tanks.")


# ------------------------------------------------------------------ Shifts
def duty_page():
    me = auth.require(*MGR)
    st.header("🧑‍🔧 Shifts & Nozzles")
    flash()

    busy = {d["salesman_id"] for d in duties.active_duties()}
    free_salesmen = [p for p in users.list_profiles(role="salesman", active_only=True) if p["id"] not in busy]
    with st.form("start_duty"):
        st.markdown("**Start a new shift**")
        if free_salesmen:
            sid = st.selectbox("Salesman", [p["id"] for p in free_salesmen],
                               format_func=lambda i: next(p["name"] for p in free_salesmen if p["id"] == i))
        else:
            sid = None
            st.caption("All salesmen already have an active shift (or no salesmen exist).")
        ok = st.form_submit_button("Start shift", type="primary", disabled=not free_salesmen)
    if ok and sid:
        run(duties.start_duty, sid, me["id"], success="Shift started. Now assign nozzles.")

    active = duties.active_duties()
    if not active:
        st.info("No active shifts.")
        return

    free = duties.free_nozzles()
    for d in active:
        name = (d.get("profiles") or {}).get("name") or "—"
        s = settlements.for_shift(d["id"])
        tag = status_label(s.get("status")) if s and s.get("breakup_submitted_at") else "🟢 Shift active"
        with st.expander(f"{name} · {d.get('date')} · {tag}", expanded=True):
            assigned = duties.assignments(d["id"])
            live = [a for a in assigned if a.get("is_active")]
            done = [a for a in assigned if not a.get("is_active") and a.get("closing_reading") is not None]
            for a in live:
                n = a.get("nozzles") or {}
                c1, c2 = st.columns([3, 1])
                c1.write(f"⛽ **{n.get('nozzle_name')}** ({fuel(n.get('fuel_type'))}) · opening {lt(a.get('opening_reading'))}")
                if c2.button("Remove", key=f"rm_{a['id']}", help="Only if assigned by mistake"):
                    run(duties.remove_assignment, a["id"], me["id"], success="Nozzle removed.")
            for a in done:
                n = a.get("nozzles") or {}
                st.write(f"✔️ {n.get('nozzle_name')} — closing {lt(a.get('closing_reading'))} (released)")

            if free:
                c1, c2 = st.columns([3, 1])
                nid = c1.selectbox("Add nozzle", [n["id"] for n in free], key=f"add_{d['id']}",
                                   format_func=lambda i: next(f"{n['nozzle_name']} ({fuel(n['fuel_type'])}) · "
                                                              f"meter {lt(n.get('current_reading'))}"
                                                              for n in free if n["id"] == i))
                if c2.button("Assign", key=f"allot_{d['id']}", type="primary"):
                    run(duties.assign_nozzle, d["id"], nid, me["id"], success="Nozzle assigned.")
            else:
                st.caption("No free nozzles.")

            if not live and not done:
                if st.button("End shift (started by mistake)", key=f"end_{d['id']}"):
                    run(duties.end_empty_duty, d["id"], me["id"], success="Shift ended.")


# ------------------------------------------------------------------ Testing
def testing_page():
    me = auth.require(*MGR)
    st.header("🧪 Testing")
    flash()
    st.caption("Testing fuel is returned to the tank — no effect on stock. It is not counted as a sale.")
    ns = [n for n in duties.free_nozzles()] + [a.get("nozzles") for d in duties.active_duties()
                                               for a in duties.assignments(d["id"], active_only=True)]
    ns = sorted({n["id"]: n for n in ns if n}.values(), key=lambda n: n["nozzle_name"])
    if not ns:
        st.info("No active nozzles.")
        return
    with st.form("testing", clear_on_submit=True):
        nid = st.selectbox("Nozzle", [n["id"] for n in ns],
                           format_func=lambda i: next(f"{n['nozzle_name']} · meter {lt(n.get('current_reading'))}"
                                                      for n in ns if n["id"] == i))
        liters = num("Testing litres", "test_l", value=5.0)
        remark = st.text_input("Remarks (optional)")
        ok = st.form_submit_button("Save", type="primary")
    if ok:
        run(testing.create, nid, liters, remark, me["id"],
            success=f"Testing of {lt(liters)} saved. Meter reading advanced.")

    rows_ = testing.list_for_date(today_ist())
    if rows_:
        st.subheader("Today's testing")
        st.dataframe(pd.DataFrame([{
            "Nozzle": (r.get("nozzles") or {}).get("nozzle_name"), "Litres": lt(r.get("testing_liters")),
            "Meter": f"{q2(r.get('reading_before'))} → {q2(r.get('reading_after'))}",
            "Linked to shift": "Yes" if r.get("assignment_id") else "—", "Remarks": r.get("remark") or "",
        } for r in rows_]), hide_index=True, use_container_width=True)


# ------------------------------------------------------------------ Settlement
def settlement_page():
    me = auth.require(*MGR)
    st.header("🧾 Settlement")
    flash()
    last = st.session_state.get("_last_approved")
    if last:
        from views.reports import settlement_download
        with st.container(border=True):
            st.write(f"✅ Settlement for **{last.get('name')}** approved. Print the report:")
            c1, c2 = st.columns([3, 1])
            with c1:
                settlement_download(last["id"], key=f"last_{last['id']}")
            if c2.button("✖ Close", key="close_last", use_container_width=True):
                st.session_state.pop("_last_approved", None)
                st.rerun()
        st.caption("Older and daily reports: Reports → 🖨️ Print")
    active = duties.active_duties()
    if not active:
        st.info("No active shifts.")
        return

    def label(d):
        s = settlements.for_shift(d["id"])
        if not s:
            state = "closing pending"
        elif s.get("status") in ("hold", "reopened"):
            state = status_label(s["status"])
        elif s.get("breakup_submitted_at") and settlements.closing_saved(s):
            state = "✅ ready for approval"
        elif s.get("breakup_submitted_at"):
            state = "settlement received, closing pending"
        else:
            state = "closing recorded, salesman settlement pending"
        return f"{(d.get('profiles') or {}).get('name')} · {d.get('date')} · {state}"

    by_id = {d["id"]: d for d in active}
    shift_id = st.selectbox("Shift", list(by_id), format_func=lambda i: label(by_id[i]))
    shift = by_id[shift_id]
    s = settlements.for_shift(shift_id)

    # ---- Closing reading ----
    st.subheader("1. Closing readings")
    assigned = [a for a in duties.assignments(shift_id)
                if a.get("is_active") or a.get("closing_reading") is not None]
    if not assigned:
        st.info("No nozzles are assigned to this shift.")
        return
    locked = bool(s and s.get("status") == "approved")
    with st.form(f"closing_{shift_id}"):
        inputs = {}
        for a in assigned:
            n = a.get("nozzles") or {}
            t = testing.liters_for_assignment(a["id"])
            default = a.get("closing_reading") if a.get("closing_reading") is not None else n.get("current_reading")
            st.markdown(f"**{n.get('nozzle_name')}** ({fuel(n.get('fuel_type'))}) · opening {lt(a.get('opening_reading'))}"
                        + (f" · testing {lt(t)}" if t > 0 else ""))
            inputs[a["id"]] = num("Closing reading", f"cl_{a['id']}", value=float(default or 0))
        c1, c2 = st.columns(2)
        preview = c1.form_submit_button("Preview", use_container_width=True, disabled=locked)
        save = c2.form_submit_button("Save closing", type="primary", use_container_width=True, disabled=locked)

    if preview:
        try:
            rows_ = settlements.closing_preview(shift_id, inputs)
            _closing_table([r["calc"] | {"nozzle_name": r["name"], "fuel_type": r["fuel_type"]} for r in rows_])
        except Exception as exc:
            st.error(str(exc))
    if save:
        run(settlements.save_closing, shift_id, inputs, me["id"], success="Closing saved. Nozzles released.")

    if settlements.closing_saved(s):
        st.caption("Saved closing:")
        _closing_table(s["nozzle_readings"])
        st.metric("Sale as per meter", rs(s.get("meter_total")))

    # ---- Salesman settlement ----
    st.subheader("2. Salesman settlement")
    if not s or not s.get("breakup_submitted_at"):
        st.info("The salesman has not submitted the payment settlement yet.")
        entries = sales.live_entries(shift_id, shift["salesman_id"])
        if entries:
            st.caption(f"Entries so far: {len(entries)} · {rs(sales.entries_total(shift_id, shift['salesman_id']))}")
        if not s:
            return
    else:
        c = st.columns(4)
        c[0].metric("Cash", rs(s.get("cash_amount")))
        c[1].metric("Paytm", rs(s.get("paytm_amount")))
        c[2].metric("CCMS", rs(s.get("ccms_amount")))
        c[3].metric("Credit", rs(s.get("credit_amount")))
        st.write(f"Salesman entries: **{rs(s.get('entries_total'))}** · Cash advanced to credit parties: "
                 f"**{rs(s.get('cash_given_to_creditor_amount'))}** · Cash to be handed over: "
                 f"**{rs(s.get('cash_transfer_expected'))}**")
        tx = credit.txns_for_reference(s["id"])
        open_tx = [t for t in tx if t.get("status") in ("pending", "hold", "reopened")]
        if open_tx:
            st.dataframe(pd.DataFrame([{
                "Party": (t.get("credit_parties") or {}).get("name"),
                "Type": "Fuel on credit" if t["type"] == "sale" else "Cash advance",
                "Amount": rs(t.get("amount")), "Remarks": t.get("note") or "",
            } for t in open_tx]), hide_index=True, use_container_width=True)

    # ---- Decision ----
    st.subheader("3. Decision")
    st.write(f"Status: {status_label(s.get('status'))}")
    diff = settlements.difference_of(s)
    if diff is None:
        st.info("The difference will be shown after the closing is saved.")
    else:
        ok = is_matched(diff)
        (st.success if ok else st.error)(f"Difference: {short_excess_label(diff)} "
                                         f"({'within ±₹2 — can be approved' if ok else 'more than ±₹2'})")
    if s.get("status") == "approved":
        st.success("This settlement has been approved.")
        return

    note = st.text_input("Note (for Hold / Return)", key=f"note_{s['id']}")
    c1, c2, c3 = st.columns(3)
    can_approve = diff is not None and is_matched(diff) and (s.get("breakup_submitted_at") or D(s.get("meter_total")) == 0)
    if c1.button("✅ Approve", type="primary", disabled=not can_approve, use_container_width=True):
        def _approve():
            settlements.approve(s["id"], me["id"])
            st.session_state["_last_approved"] = {"id": s["id"], "name": (shift.get("profiles") or {}).get("name")}
        run(_approve, success="Approved. Stock deducted, credit updated, shift closed.")
    if c2.button("⏸️ Hold", use_container_width=True):
        run(settlements.hold, s["id"], note, me["id"], success="Settlement put on hold.")
    if c3.button("🔄 Return to salesman", use_container_width=True):
        run(settlements.reopen, s["id"], note, me["id"],
            success="Returned to salesman. They will correct and resubmit.")


def _closing_table(rows_):
    st.dataframe(pd.DataFrame([{
        "Nozzle": r.get("nozzle_name"), "Opening": f"{q2(r.get('opening'))}", "Closing": f"{q2(r.get('closing'))}",
        "Testing": lt(r.get("testing_liters")), "Sale litres": lt(r.get("net_sale_liters")),
        "Rate": rs(r.get("rate")), "Amount": rs(r.get("sale_amount")),
    } for r in rows_]), hide_index=True, use_container_width=True)


# ------------------------------------------------------------------ Credit parties
def credit_page():
    me = auth.require(*MGR)
    st.header("📒 Credit Parties")
    flash()
    parties = credit.list_parties()

    if parties:
        st.dataframe(pd.DataFrame([{
            "Party": p["name"], "Balance receivable": rs(p.get("current_balance")),
            "Credit limit": rs(p.get("credit_limit")) if D(p.get("credit_limit")) > 0 else "—",
            "Vehicles": len(credit.vehicles_of(p)), "Status": "✅" if p.get("is_active") else "⛔",
        } for p in parties]), hide_index=True, use_container_width=True)

    options = [None] + [p["id"] for p in parties]
    pid = st.selectbox("Party", options, format_func=lambda i: "➕ New party" if i is None
                       else next(p["name"] for p in parties if p["id"] == i))
    p = next((x for x in parties if x["id"] == pid), {}) if pid else {}
    with st.form(f"party_{pid}"):
        name = st.text_input("Name", value=p.get("name", ""))
        phone = st.text_input("Mobile", value=p.get("phone") or "")
        limit = num("Credit limit (0 = no limit)", f"lim_{pid}", value=float(p.get("credit_limit") or 0))
        veh = st.text_area("Vehicle numbers (one per line). Leave empty to allow any vehicle.",
                           value="\n".join(credit.vehicles_of(p)) if p else "")
        active = st.checkbox("Active", value=p.get("is_active", True))
        ok = st.form_submit_button("Save", type="primary")
    if ok:
        run(credit.save_party, pid, name, phone, limit, veh, active, me["id"], success="Party saved.")

    if pid:
        st.subheader("Record payment received")
        banks = accounts.banks()
        with st.form(f"pay_{pid}", clear_on_submit=True):
            amt = num("Amount", f"pay_a_{pid}")
            mode = st.selectbox("Payment mode", ["cash", "bank", "paytm", "ccms"],
                                format_func={"cash": "Cash", "bank": "Bank", "paytm": "Paytm / UPI", "ccms": "CCMS"}.get)
            bank = st.selectbox("Bank account (if bank)", [b["id"] for b in banks],
                                format_func=lambda i: next(b["name"] for b in banks if b["id"] == i)) if banks else None
            d = st.date_input("Date", value=date.fromisoformat(today_ist()), key=f"pay_d_{pid}")
            ref = st.text_input("Reference / UTR", key=f"pay_r_{pid}")
            ok = st.form_submit_button("Save payment", type="primary")
        if ok:
            run(credit.record_payment, pid, amt, mode, bank, d.isoformat(), ref, "", me["id"],
                success="Payment recorded. Party balance reduced.")

        st.subheader("Ledger")
        led = credit.ledger(pid)
        if led:
            sign = {"opening": "+", "sale": "+", "cash_given": "+", "payment_received": "−"}
            type_label = {"opening": "Opening balance", "sale": "Fuel on credit", "cash_given": "Cash advance",
                          "payment_received": "Payment received"}
            st.dataframe(pd.DataFrame([{
                "Date": r.get("date"), "Type": type_label.get(r.get("type"), r.get("type")),
                "Amount": f"{sign.get(r.get('type'), '')}{rs(r.get('amount'))}",
                "Status": status_label(r.get("status")), "Remarks": r.get("note") or "",
            } for r in led]), hide_index=True, use_container_width=True)
            st.caption("The balance includes approved entries only.")
