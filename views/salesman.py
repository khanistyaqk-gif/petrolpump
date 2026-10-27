"""Salesman: My Shift (sale entry + settlement) and My Entries — designed for phones first."""
import streamlit as st

from core import auth, theme
from core.calc import ZERO, D, q2
from core.ui import flash, fuel, lt, num, rs, run, status_label
from repo import credit, duties, rates, sales, settlements

CR_KEY = "_credit_lines"     # list of line ids for the credit-sale form


def _status_chip(s, submitted):
    if not s or (not submitted and s.get("status") not in ("hold", "approved")):
        if s and s.get("status") == "reopened":
            return theme.chip("Returned", "bad")
        return theme.chip("In progress")
    text = status_label(s.get("status")).split(" ", 1)[-1]
    return theme.chip(text, theme.STATUS_TONE.get(s.get("status"), ""))


def duty_page():
    me = auth.require("salesman")
    duty = duties.active_duty_for(me["id"])
    if not duty:
        theme.hero(f"Hi, {me['name']}", "No active shift")
        st.warning("You do not have an active shift. Please ask the Manager to start your shift.")
        return

    s = settlements.for_shift(duty["id"])
    submitted = bool(s and s.get("breakup_submitted_at"))
    editable = not submitted and not (s and s.get("status") in ("hold", "approved"))
    theme.hero(f"Hi, {me['name']}", f"Shift date {duty.get('date')}", _status_chip(s, submitted))
    flash()
    if s and s.get("status") == "reopened":
        st.error(f"The Manager returned your settlement: {s.get('manager_note') or ''}. "
                 "Please correct it and submit again.")

    nozzles = sales.duty_nozzles(duty["id"], me["id"])
    if not nozzles:
        st.info("No nozzle has been assigned yet. Please ask the Manager to assign one.")
        return

    entries = sales.live_entries(duty["id"], me["id"])
    by_nozzle = {e["nozzle_id"]: e for e in entries}
    total = sales.entries_total(duty["id"], me["id"])
    all_entered = all(a["nozzle_id"] in by_nozzle for a in nozzles)
    theme.steps(["Sales", "Payments", "Submitted"], 3 if not editable else (1 if all_entered else 0))

    # ------------------------------------------------------------ 1. Sales
    st.subheader("1 · Sale entry")
    for a in nozzles:
        n = a.get("nozzles") or {}
        nid = a["nozzle_id"]
        rate = rates.rate_for(n.get("fuel_type"), duty.get("date"))
        e = by_nozzle.get(nid)
        sub = f"{fuel(n.get('fuel_type'))} · {rs(rate) + '/L' if rate else 'rate not set'} · opening {lt(a.get('opening_reading'))}"
        with st.container(border=True):
            theme.nozzle_head(n.get("nozzle_name") or f"Nozzle {nid}", sub,
                              theme.chip("🔒 Entered", "ok") if e else theme.chip("Pending", "warn"))
            if e:
                theme.big(rs(e.get("amount")), f"{lt(e.get('liters'))} × {rs(e.get('rate'))}")
                can_change = editable and (e.get("status") or "pending") == "pending"
                if can_change and st.session_state.get("_editing") == e["id"]:
                    new_l = num("New litres", f"edl_{e['id']}", value=float(e.get("liters") or 0))
                    c1, c2 = st.columns(2)
                    if c1.button("Save", key=f"eds_{e['id']}", type="primary", use_container_width=True):
                        st.session_state.pop("_editing", None)
                        run(sales.edit_entry, e["id"], me["id"], new_l, success="Entry updated.")
                    if c2.button("Discard", key=f"edc_{e['id']}", use_container_width=True):
                        st.session_state.pop("_editing", None)
                        st.rerun()
                elif can_change:
                    c1, c2 = st.columns(2)
                    if c1.button("✏️ Edit", key=f"ed_{e['id']}", use_container_width=True):
                        st.session_state["_editing"] = e["id"]
                        st.rerun()
                    if c2.button("❌ Cancel", key=f"x_{e['id']}", use_container_width=True):
                        run(sales.cancel_entry, e["id"], me["id"], success="Entry cancelled. Nozzle unlocked.")
            elif editable:
                with st.form(f"sale_{nid}", clear_on_submit=True):
                    liters = num("Litres sold", f"sale_l_{nid}", value=0.0)
                    ok = st.form_submit_button("Save entry", type="primary", use_container_width=True)
                if ok:
                    run(sales.add_entry, me["id"], nid, liters, success="Entry saved. Nozzle locked.")
            else:
                st.caption("No entry for this nozzle.")

    theme.rows_card([("Nozzles entered", f"{len(by_nozzle)} of {len(nozzles)}"), ("Total sale", rs(total))],
                    tone="brand", bold_last=True)

    # ------------------------------------------------------------ Submitted view
    if not editable:
        st.subheader("Settlement")
        theme.rows_card([
            ("Cash", rs(s.get("cash_amount"))), ("Paytm / UPI", rs(s.get("paytm_amount"))),
            ("CCMS / Card", rs(s.get("ccms_amount"))), ("Credit sales", rs(s.get("credit_amount"))),
            ("Cash advance to parties", rs(s.get("cash_given_to_creditor_amount"))),
            ("Cash to hand over to Manager", rs(s.get("cash_transfer_expected"))),
        ], bold_last=True)
        st.caption("Waiting for the Manager. You will be able to edit only if the Manager returns the settlement.")
        return

    # ------------------------------------------------------------ 2. Payments
    st.subheader("2 · Payments")
    c1, c2, c3 = st.columns(3)
    with c1:
        cash = num("Cash", "b_cash")
    with c2:
        paytm = num("Paytm / UPI", "b_paytm")
    with c3:
        ccms = num("CCMS / Card", "b_ccms")

    st.markdown("**Credit sales**")
    parties = credit.list_parties(active_only=True)
    items = []
    if not parties:
        st.caption("No credit parties have been created. Ask the Manager to add them on the Credit Parties page.")
    else:
        lines = st.session_state.setdefault(CR_KEY, [])
        by_id = {p["id"]: p for p in parties}
        for lid in list(lines):
            with st.container(border=True):
                pid = st.selectbox("Party", list(by_id), key=f"b_p_{lid}", format_func=lambda x: by_id[x]["name"])
                allowed = credit.vehicles_of(by_id[pid])
                if allowed:
                    vehicle = st.selectbox("Vehicle", allowed, key=f"b_v_{lid}")
                else:
                    vehicle = st.text_input("Vehicle number", key=f"b_vt_{lid}")
                c1, c2 = st.columns(2)
                with c1:
                    amt = num("Fuel on credit (₹)", f"b_a_{lid}")
                with c2:
                    given = num("Cash advance (₹)", f"b_g_{lid}",
                                help="Cash given to the party from the cash drawer. Not part of the sale.")
                comment = st.text_input("Remarks / slip no.", key=f"b_c_{lid}")
                if st.button("🗑 Remove this credit sale", key=f"b_rm_{lid}", use_container_width=True):
                    lines.remove(lid)
                    st.rerun()
                items.append({"party_id": pid, "amount": amt, "cash_given": given,
                              "vehicle": vehicle, "comment": comment})
        if st.button("➕ Add credit sale", use_container_width=True):
            lines.append(max(lines, default=0) + 1)
            st.rerun()

    # ------------------------------------------------------------ 3. Check & submit
    credit_sum = q2(sum((D(i["amount"]) for i in items), ZERO))
    given_sum = q2(sum((D(i["cash_given"]) for i in items), ZERO))
    pay = q2(cash + paytm + ccms + credit_sum)
    diff = q2(total - pay)
    st.subheader("3 · Check & submit")
    if diff == 0 and total > 0:
        verdict, tone = "✅ Matched", "ok"
    elif diff > 0:
        verdict, tone = f"Short by {rs(diff)}", "bad"
    elif diff < 0:
        verdict, tone = f"Excess by {rs(-diff)}", "bad"
    else:
        verdict, tone = "Enter sales and payments", "warn"
    theme.rows_card([("Total sale (entries)", rs(total)), ("Total payments", rs(pay)), ("Status", verdict)],
                    tone=tone, bold_last=True)
    if given_sum > 0:
        theme.rows_card([("Cash", rs(cash)), ("Cash advance to parties", f"− {rs(given_sum)}"),
                         ("Cash to hand over", rs(cash - given_sum))], bold_last=True)

    missing = [(a.get("nozzles") or {}).get("nozzle_name") for a in nozzles if a["nozzle_id"] not in by_nozzle]
    if missing:
        st.warning("⚠️ No entry for: " + ", ".join(missing) +
                   ". If there was a sale, add the entry first — otherwise the Manager will see a shortage.")
    if st.button("Submit settlement to Manager", type="primary", use_container_width=True, disabled=diff != 0):
        warnings = run(settlements.submit_breakup, me["id"], cash, paytm, ccms, items, rerun=False)
        if warnings is not False:
            st.session_state.pop(CR_KEY, None)
            msg = "Settlement submitted. The Manager will review and approve it."
            if isinstance(warnings, list) and warnings:
                msg += " ⚠️ " + " ".join(warnings)
            st.session_state["_flash"] = msg
            st.rerun()


def entries_page():
    me = auth.require("salesman")
    theme.hero("My Entries", me["name"])
    data = sales.history(me["id"])
    if not data:
        st.info("No entries yet.")
        return
    by_date = {}
    for e in data:
        by_date.setdefault(e.get("date"), []).append(e)
    for day, items in by_date.items():
        live = [e for e in items if (e.get("status") or "pending") not in ("cancelled", "rejected")]
        pairs = []
        for e in items:
            name = (e.get("nozzles") or {}).get("nozzle_name")
            tag = "" if e in live else " (cancelled)"
            pairs.append((f"{name} · {lt(e.get('liters'))} × {rs(e.get('rate'))}{tag}", rs(e.get("amount"))))
        pairs.append(("Total", rs(sum((D(e.get("amount")) for e in live), ZERO))))
        st.markdown(f"**{day}**")
        theme.rows_card(pairs, bold_last=True)
