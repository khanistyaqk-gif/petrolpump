"""Owner pages: Users, Nozzles, Fuel Rates, Tanks, Settings, System."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.db import FUEL_TYPES, ROLE_LABELS, ROLES, today_ist
from core.ui import flash, fuel, lt, num, rs, run
from repo import nozzles, rates, tanks, users


# ------------------------------------------------------------------ Users
def users_page():
    me = auth.require("owner")
    st.header("👥 Users")
    flash()

    with st.expander("➕ New user", expanded=False):
        with st.form("new_user", clear_on_submit=True):
            name = st.text_input("Full name")
            login = st.text_input("Login ID", help="For example: ramesh (or a full email address)")
            phone = st.text_input("Mobile (optional)")
            role = st.selectbox("Role", ["salesman", "manager", "owner"], format_func=ROLE_LABELS.get)
            pw = st.text_input("Password (minimum 6 characters)", type="password")
            ok = st.form_submit_button("Create user", type="primary")
        if ok:
            run(users.create_user, name, login, pw, role, phone, me["id"],
                success=f"{ROLE_LABELS[role]} created. Login ID: {login.strip().lower()}")

    people = users.list_profiles()
    if not people:
        st.info("No users yet.")
        return
    st.dataframe(pd.DataFrame([{
        "Name": p.get("name"), "Login": p.get("login") or "—", "Role": ROLE_LABELS.get(p.get("role")),
        "Mobile": p.get("phone") or "", "Status": "✅ Active" if p.get("is_active") else "⛔ Inactive",
    } for p in people]), hide_index=True, use_container_width=True)

    st.subheader("Edit user")
    by_id = {p["id"]: p for p in people}
    uid = st.selectbox("User", list(by_id), format_func=lambda i: f"{by_id[i]['name']} — {ROLE_LABELS.get(by_id[i]['role'])}")
    u = by_id[uid]
    with st.form(f"edit_{uid}"):
        role = st.selectbox("Role", ROLES, index=ROLES.index(u["role"]) if u["role"] in ROLES else 0,
                            format_func=ROLE_LABELS.get)
        active = st.checkbox("Active", value=bool(u.get("is_active")))
        pw = st.text_input("New password (leave empty to keep current)", type="password")
        save = st.form_submit_button("Save")
    if save:
        def _save():
            users.update_user(uid, me["id"], role=role, is_active=active)
            if pw:
                users.reset_password(uid, pw, me["id"])
        run(_save, success="Changes saved.")


# ------------------------------------------------------------------ Nozzles
def nozzles_page():
    me = auth.require("owner")
    st.header("⛽ Nozzles")
    flash()

    with st.expander("➕ New nozzle"):
        with st.form("new_nozzle", clear_on_submit=True):
            name = st.text_input("Name", placeholder="N1 Petrol")
            ft = st.selectbox("Fuel", FUEL_TYPES, format_func=fuel)
            reading = num("Current meter reading", "nz_reading")
            ok = st.form_submit_button("Create", type="primary")
        if ok:
            run(nozzles.create, name, ft, reading, me["id"], success="Nozzle created.")

    data = nozzles.list_nozzles()
    if not data:
        st.info("No nozzles yet.")
        return
    st.dataframe(pd.DataFrame([{
        "Nozzle": n["nozzle_name"], "Fuel": fuel(n["fuel_type"]), "Meter": lt(n.get("current_reading")),
        "On shift": "Yes" if nozzles.active_assignment(n["id"]) else "—",
        "Status": "✅ Active" if n.get("is_active") else "⛔ Inactive",
    } for n in data]), hide_index=True, use_container_width=True)

    by_id = {n["id"]: n for n in data}
    nid = st.selectbox("Select nozzle", list(by_id), format_func=lambda i: by_id[i]["nozzle_name"])
    n = by_id[nid]
    c1, c2 = st.columns(2)
    if n.get("is_active"):
        if c1.button("⛔ Deactivate", use_container_width=True):
            run(nozzles.set_active, nid, False, me["id"], success="Nozzle deactivated.")
    elif c1.button("✅ Activate", use_container_width=True):
        run(nozzles.set_active, nid, True, me["id"], success="Nozzle activated.")

    with st.expander("🔧 Correct meter reading (repair / reset)"):
        st.caption("Use only after a meter repair or reset. Not allowed while the nozzle is on a shift. "
                   "Every change is logged.")
        with st.form(f"fix_{nid}"):
            new = num("Correct reading", f"fix_r_{nid}", value=float(n.get("current_reading") or 0))
            reason = st.text_input("Reason")
            ok = st.form_submit_button("Update reading")
        if ok:
            run(nozzles.correct_reading, nid, new, reason, me["id"], success="Meter reading updated.")


# ------------------------------------------------------------------ Rates
def rates_page():
    me = auth.require("owner")
    st.header("💰 Fuel Rates")
    flash()
    today = today_ist()
    cur = rates.current_rates(today)
    cols = st.columns(2)
    for i, ft in enumerate(FUEL_TYPES):
        cols[i % 2].metric(fuel(ft), rs(cur[ft]) if cur[ft] else "Not set")

    with st.form("set_rate"):
        ft = st.selectbox("Fuel", FUEL_TYPES, format_func=fuel)
        price = num("Rate (₹ per litre)", "rate_price", value=float(cur.get(ft) or 0))
        eff = st.date_input("Effective from", value=date.fromisoformat(today))
        ok = st.form_submit_button("Save rate", type="primary")
    if ok:
        eff_s = eff.isoformat()
        msg = "Rate saved."
        if rates.activity_on_or_after(eff_s):
            msg += (f" Note: sales already exist on or after {eff_s} — existing entries keep their rate; "
                    "new entries and closings will use the new rate.")
        run(rates.set_rate, ft, price, eff_s, me["id"], success=msg)

    st.subheader("Rate history")
    hist = rates.history()
    if hist:
        st.dataframe(pd.DataFrame([{"Effective from": h["effective_from"], "Fuel": fuel(h["fuel_type"]),
                                    "Rate": rs(h["price_per_liter"])} for h in hist]),
                     hide_index=True, use_container_width=True)


# ------------------------------------------------------------------ Tanks
def tanks_page():
    me = auth.require("owner")
    st.header("🛢️ Tanks")
    flash()
    data = tanks.list_tanks()
    if data:
        st.dataframe(pd.DataFrame([{
            "Tank": t.get("tank_name"), "Fuel": fuel(t["fuel_type"]), "Stock": lt(t.get("current_stock")),
            "Capacity": lt(t.get("capacity_liters")),
        } for t in data if t.get("is_active")]), hide_index=True, use_container_width=True)
    else:
        st.info("No tanks yet. Every fuel that is sold needs a tank, otherwise settlements cannot be approved.")

    with st.expander("➕ New tank"):
        with st.form("new_tank", clear_on_submit=True):
            ft = st.selectbox("Fuel", FUEL_TYPES, format_func=fuel)
            name = st.text_input("Name", placeholder="Petrol Tank 1")
            cap = num("Capacity (L)", "tank_cap")
            opening = num("Current stock (L)", "tank_open")
            ok = st.form_submit_button("Create", type="primary")
        if ok:
            run(tanks.create, ft, name, cap, opening, me["id"], success="Tank created.")

    if data:
        with st.expander("🔧 Correct stock"):
            st.caption("Only for correcting mistakes. For daily dip readings use the Stock page. Every change is logged.")
            with st.form("fix_stock"):
                ft = st.selectbox("Fuel", [t["fuel_type"] for t in data if t.get("is_active")], format_func=fuel)
                new = num("Correct stock (L)", "fix_stock_v")
                reason = st.text_input("Reason")
                ok = st.form_submit_button("Update stock")
            if ok:
                run(tanks.correct_stock, ft, new, reason, me["id"], success="Stock updated.")


# ------------------------------------------------------------------ Settings
def settings_page():
    me = auth.require("owner")
    st.header("⚙️ Settings")
    flash()
    from repo import accounts, credit as credit_repo, money

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Bank accounts")
        for b in accounts.banks(False):
            st.write(("✅ " if b["is_active"] else "⛔ ") + b["name"])
        with st.form("bank", clear_on_submit=True):
            n = st.text_input("New bank account", placeholder="Canara Bank OD")
            if st.form_submit_button("Add"):
                run(accounts.add_bank, n, me["id"], success="Bank account added.")
    with c2:
        st.subheader("Oil companies")
        for o in accounts.oil_companies(False):
            st.write(("✅ " if o["is_active"] else "⛔ ") + o["name"])
        with st.form("oil", clear_on_submit=True):
            n = st.text_input("New oil company", placeholder="IOCL")
            if st.form_submit_button("Add"):
                run(accounts.add_oil_company, n, me["id"], success="Oil company added.")

    st.subheader("Opening balances (one-time setup)")
    st.caption("Balances at the time you start using the software. Each account can be set only once. "
               "Nozzle readings → Nozzles, tank stock → Tanks, party balances → below.")
    banks = accounts.banks()
    oils = accounts.oil_companies()
    with st.form("opening"):
        acc = st.selectbox("Account", money.ACCOUNTS, format_func=money.ACCOUNT_LABELS.get)
        if banks:
            ref_b = st.selectbox("Bank account (if Bank)", [b["id"] for b in banks],
                                 format_func=lambda i: next(b["name"] for b in banks if b["id"] == i))
        else:
            ref_b = None
        if oils:
            ref_o = st.selectbox("Oil company (if oil company payable)", [o["id"] for o in oils],
                                 format_func=lambda i: next(o["name"] for o in oils if o["id"] == i))
        else:
            ref_o = None
        amt = num("Amount (enter a negative value for an overdrawn OD account)", "op_amt", min_value=-1e12)
        d = st.date_input("Date", value=date.fromisoformat(today_ist()), key="op_date")
        ok = st.form_submit_button("Save")
    if ok:
        ref = ref_b if acc == "bank" else ref_o if acc == "oil" else None
        run(money.set_opening, acc, ref, amt, d.isoformat(), me["id"], success="Opening balance saved.")

    parties = credit_repo.list_parties()
    if parties:
        with st.form("party_open"):
            pid = st.selectbox("Party opening balance (amount receivable)", [p["id"] for p in parties],
                               format_func=lambda i: next(p["name"] for p in parties if p["id"] == i))
            amt = num("Amount", "pop_amt")
            ok = st.form_submit_button("Save")
        if ok:
            run(credit_repo.set_opening, pid, amt, today_ist(), me["id"], success="Party opening balance saved.")


# ------------------------------------------------------------------ System
def system_page():
    auth.require("owner")
    st.header("🛡️ System")
    from repo import reports
    import json

    st.subheader("Data integrity check")
    if st.button("Run check", type="primary"):
        problems, pending = reports.consistency_check()
        if problems:
            for p in problems:
                st.error(p)
        else:
            st.success("All good: tank stock matches the register, party balances match the ledger, "
                       "and cash is not negative.")
        st.caption(f"Settlements pending approval: {pending}")

    st.subheader("Backup")
    st.caption("Download all data as a JSON file. We recommend doing this once a week and storing it safely.")
    if st.button("Create backup"):
        data = reports.backup()
        st.download_button("⬇️ Download backup", json.dumps(data, default=str, ensure_ascii=False).encode("utf-8"),
                           file_name=f"pump_backup_{today_ist()}.json", mime="application/json")

    st.subheader("Audit log (last 200)")
    from core.db import db, rows
    log = rows(db().table("audit_log").select("*").order("id", desc=True).limit(200).execute())
    names = {p["id"]: p["name"] for p in users.list_profiles()}
    if log:
        st.dataframe(pd.DataFrame([{"When": str(r["created_at"])[:19].replace("T", " "),
                                    "User": names.get(r.get("user_id"), r.get("user_id") or ""),
                                    "Action": r["action"], "Details": json.dumps(r.get("details") or {}, ensure_ascii=False)}
                                   for r in log]), hide_index=True, use_container_width=True)
