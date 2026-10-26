import streamlit as st

from core.auth import current_user
from core.perms import require
from core.ui import liters, money, show_error
from views.common import flash, names_by_id, show_flash, table
from repo import assignments, nozzles, profiles, sales, settlements, shifts
from services import settlement as st_svc


@require("owner", "manager")
def duty():
    show_flash()
    me = current_user()
    names = names_by_id()

    st.subheader("Active duties")
    act = shifts.list_active()
    if not act.ok:
        return show_error(act, "Could not load duties.")
    if not act.rows:
        st.info("No active duty.")
    for d in act.rows:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{names.get(d['salesman_id'], d['salesman_id'])}** · duty #{d['id']} · started {str(d.get('started_at'))[:16]}")
        if c2.button("End duty", key=f"end_{d['id']}"):
            _end_duty(d)

    st.subheader("Start a duty")
    men = profiles.list_active_salesmen()
    if not men.ok:
        return show_error(men)
    on_duty = {d["salesman_id"] for d in act.rows}
    free = [m for m in men.rows if m["id"] not in on_duty]
    if not free:
        st.caption("Every active salesman is already on duty (or no salesman profile exists).")
        return
    with st.form("start_duty"):
        pick = st.selectbox("Salesman", free, format_func=lambda m: m["name"])
        go = st.form_submit_button("Start duty", type="primary")
    if go:
        r = shifts.start(pick["id"], me["id"])
        if r.ok:
            flash("success", f"Duty started for {pick['name']}.")
            st.rerun()
        else:
            show_error(r, "Could not start duty.")


def _end_duty(d):
    sres = settlements.for_shift(d["id"])
    if not sres.ok:
        return show_error(sres)
    status = (sres.first or {}).get("status")
    if status in ("pending", "hold"):
        return st.error("Sale is waiting for approval. Approve or reject it in 'Approvals' first.")
    live = sales.live_for_shift(d["id"])
    if not live.ok:
        return show_error(live)
    if live.rows and status != "approved":
        return st.error("This duty has sale entries that were never approved. Submit and approve them, or reject them, before ending the duty.")
    r = shifts.end(d["id"])
    if r.ok:
        flash("success", "Duty ended.")
        st.rerun()
    else:
        show_error(r, "Could not end duty.")


@require("owner", "manager")
def assign():
    show_flash()
    me = current_user()
    names = names_by_id()
    act = shifts.list_active()
    if not act.ok:
        return show_error(act)
    if not act.rows:
        return st.info("Start a duty first (Duty page).")

    duty_row = st.selectbox("Duty", act.rows, format_func=lambda d: f"{names.get(d['salesman_id'], '?')} · duty #{d['id']}")
    cur = assignments.for_shift(duty_row["id"])
    if not cur.ok:
        return show_error(cur)
    st.subheader("Assigned nozzles")
    if not cur.rows:
        st.caption("None yet.")
    for a in cur.rows:
        c1, c2 = st.columns([4, 1])
        c1.write(f"**{a['nozzle_name']}** ({a['fuel_type']}) · opening {a['opening_reading']}")
        if c2.button("Remove", key=f"rm_{a['id']}"):
            r = assignments.end(a["id"])
            if r.ok:
                flash("success", "Removed.")
                st.rerun()
            else:
                show_error(r)

    allz = nozzles.list_all()
    if not allz.ok:
        return show_error(allz)
    free = []
    for n in allz.rows:
        if not n.get("is_active", True):
            continue
        busy = assignments.active_for_nozzle(n["id"])
        if not busy.ok:
            return show_error(busy)
        if not busy.first:
            free.append(n)
    st.subheader("Assign a nozzle")
    if not free:
        return st.caption("No free nozzle.")
    with st.form("assign_form"):
        n = st.selectbox("Nozzle", free, format_func=lambda n: f"{n['nozzle_name']} ({n['fuel_type']}) · reading {n['current_reading']}")
        go = st.form_submit_button("Assign", type="primary")
    if go:
        r = assignments.assign(duty_row["id"], n["id"], me["id"])
        if r.ok:
            flash("success", "Nozzle assigned.")
            st.rerun()
        else:
            show_error(r, "Could not assign nozzle.")


@require("owner", "manager")
def approvals():
    show_flash()
    me = current_user()
    names = names_by_id()
    tab_open, tab_done = st.tabs(["Waiting for approval", "History"])

    with tab_done:
        done = settlements.by_status(["approved", "rejected"])
        if not done.ok:
            show_error(done)
        elif done.rows:
            rows = [{**r, "salesman": names.get(r["salesman_id"], r["salesman_id"])} for r in done.rows[:50]]
            st.dataframe(table(rows, ["id", "date", "salesman", "status", "entries_total", "meter_total", "cash_amount",
                                      "paytm_amount", "ccms_amount", "manager_note"]), use_container_width=True, hide_index=True)
        else:
            st.caption("Nothing yet.")

    with tab_open:
        res = settlements.by_status(["pending", "hold"])
        if not res.ok:
            return show_error(res, "Could not load approvals.")
        if not res.rows:
            return st.info("Nothing is waiting for approval.")
        s = st.selectbox("Select", res.rows, format_func=lambda r: f"#{r['id']} · {names.get(r['salesman_id'], '?')} · {r['date']} · {r['status']}")
        _review(s, me)


def _review(s, me):
    rev = st_svc.review_data(s)
    if not rev.ok:
        return show_error(rev, "Could not load details.")
    d = rev.data

    c = st.columns(4)
    c[0].metric("Cash", money(s["cash_amount"]))
    c[1].metric("Paytm", money(s["paytm_amount"]))
    c[2].metric("CCMS", money(s["ccms_amount"]))
    c[3].metric("Payment total", money(d["payment_total"]))
    st.caption(f"Status: **{s['status']}** · Note: {s.get('manager_note') or '-'}")

    st.markdown("**Closing meter readings**")
    inputs = {}
    for a in d["assignments"]:
        saved = d["saved_inputs"].get(a["id"])
        default = float(saved if saved is not None else a["opening_reading"] or 0)
        entered = sum(float(e["liters"]) for e in d["entries"] if e["nozzle_id"] == a["nozzle_id"])
        inputs[a["id"]] = st.number_input(
            f"{a['nozzle_name']} ({a['fuel_type']}) · opening {a['opening_reading']} · salesman entered {entered:.2f} L",
            min_value=0.0, value=default, step=0.01, format="%.2f", key=f"close_{s['id']}_{a['id']}")

    live = st_svc.review_data(s, inputs)
    if not live.ok:
        return show_error(live)
    ld = live.data
    if ld["rows"]:
        df = table(ld["rows"], ["nozzle", "opening", "closing", "meter_liters", "entered_liters", "liters_difference", "meter_amount"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    for e in ld["errors"]:
        st.error(e)
    m = st.columns(3)
    m[0].metric("Meter sale", money(ld["meter_total"]))
    m[1].metric("Payment total", money(ld["payment_total"]))
    m[2].metric("Difference", money(ld["difference"]))
    if ld["matched"]:
        st.success("Meter sale matches the payment breakup.")
    else:
        st.warning("Meter sale and payment breakup do not match. You can hold or reject, or fix the readings.")

    with st.expander("Sale entries"):
        if d["entries"]:
            st.dataframe(table(d["entries"], ["entry_time", "nozzle_id", "fuel_type", "liters", "rate", "amount", "status"]),
                         use_container_width=True, hide_index=True)

    note = st.text_input("Note (for hold / reject)", key=f"note_{s['id']}")
    b = st.columns(4)
    if b[0].button("1. Save closing", key=f"save_{s['id']}"):
        r = st_svc.save_closing(me, s["id"], inputs)
        _after(r, "Closing saved.")
    if b[1].button("2. Approve", type="primary", key=f"appr_{s['id']}"):
        r = st_svc.approve(me, s["id"])
        _after(r, "Approved.")
    if s["status"] == "pending":
        if b[2].button("Hold", key=f"hold_{s['id']}"):
            _after(st_svc.hold(me, s["id"], note), "Put on hold.")
    else:
        if b[2].button("Reopen", key=f"reopen_{s['id']}"):
            _after(st_svc.reopen(me, s["id"]), "Reopened.")
    if b[3].button("Reject", key=f"rej_{s['id']}"):
        _after(st_svc.reject(me, s["id"], note), "Rejected. Salesman can enter fresh sale.")


def _after(result, ok_text):
    if result.ok:
        flash("success", ok_text)
        st.rerun()
    else:
        show_error(result)
