"""Owner pages: Users, Nozzles, Fuel Rates, Tanks, Settings, System."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth
from core.db import FUEL_TYPES, ROLE_LABELS, ROLES, AppError, today_ist
from core.ui import correction_box, flash, fuel, lt, num, rs, run
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
        new_name = st.text_input("Full name", value=u.get("name") or "")
        new_phone = st.text_input("Mobile", value=u.get("phone") or "")
        role = st.selectbox("Role", ROLES, index=ROLES.index(u["role"]) if u["role"] in ROLES else 0,
                            format_func=ROLE_LABELS.get)
        active = st.checkbox("Active", value=bool(u.get("is_active")))
        pw = st.text_input("New password (leave empty to keep current)", type="password")
        save = st.form_submit_button("Save")
    if save:
        def _save():
            if not new_name.strip():
                raise AppError("Please enter the name.")
            users.update_user(uid, me["id"], role=role, is_active=active,
                              name=new_name.strip(), phone=new_phone.strip())
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

    with st.expander("✏️ Rename nozzle"):
        with st.form(f"ren_{nid}"):
            new_n = st.text_input("New name", value=n["nozzle_name"])
            ok = st.form_submit_button("Save name")
        if ok:
            run(nozzles.rename, nid, new_n, me["id"], success="Nozzle renamed.")

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
        future = [h for h in hist if str(h["effective_from"]) > today]
        if future:
            with st.expander("🗑 Delete a future rate"):
                st.caption("Only rates that start after today can be deleted. "
                           "To fix today's or a past rate, enter the correct rate again.")
                fid = st.selectbox("Rate", [h["id"] for h in future], key="del_rate",
                                   format_func=lambda i: next(f"{fuel(h['fuel_type'])} · {rs(h['price_per_liter'])} "
                                                              f"from {h['effective_from']}" for h in future if h["id"] == i))
                if st.button("Delete rate", key="del_rate_btn"):
                    run(rates.delete_future_rate, fid, me["id"], success="Future rate deleted.")


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
        with st.expander("✏️ Edit tank name / capacity"):
            act = [t for t in data if t.get("is_active")]
            ft_e = st.selectbox("Tank", [t["fuel_type"] for t in act], key="edit_tank",
                                format_func=lambda f: next(f"{t.get('tank_name')} ({fuel(f)})" for t in act if t["fuel_type"] == f))
            t_e = next(t for t in act if t["fuel_type"] == ft_e)
            with st.form(f"edit_tank_{ft_e}"):
                nm = st.text_input("Name", value=t_e.get("tank_name") or "")
                cap = num("Capacity (L)", f"edit_cap_{ft_e}", value=float(t_e.get("capacity_liters") or 0))
                ok = st.form_submit_button("Save")
            if ok:
                run(tanks.update, ft_e, nm, cap, me["id"], success="Tank updated.")
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

    _edit_accounts(me)

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
    done = money.reversed_groups()
    openings = [t for t in money.txns(kind="opening") if t.get("reverses_group") is None
                and (t.get("group_id") or t["id"]) not in done]
    banks_all, oils_all = accounts.name_maps()
    correction_box("rev_open", openings, lambda t: (
        f"{money.ACCOUNT_LABELS[t['account']]}"
        + (f" · {banks_all.get(t['bank_account_id'])}" if t.get("bank_account_id") else "")
        + (f" · {oils_all.get(t['oil_company_id'])}" if t.get("oil_company_id") else "")
        + f" · {rs(t['amount'])} · {t['date']}"), money.reverse, me["id"],
        title="↩️ Wrong opening balance? Reverse it", success="Opening balance reversed. You can now enter it again.")

    parties = credit_repo.list_parties()
    if parties:
        with st.form("party_open"):
            pid = st.selectbox("Party opening balance (amount receivable)", [p["id"] for p in parties],
                               format_func=lambda i: next(p["name"] for p in parties if p["id"] == i))
            amt = num("Amount", "pop_amt")
            ok = st.form_submit_button("Save")
        if ok:
            run(credit_repo.set_opening, pid, amt, today_ist(), me["id"], success="Party opening balance saved.")


def _edit_accounts(me):
    from repo import accounts
    items = [("bank_accounts", b) for b in accounts.banks(False)] + [("oil_companies", o) for o in accounts.oil_companies(False)]
    if not items:
        return
    with st.expander("✏️ Rename / deactivate a bank account or oil company"):
        keys = list(range(len(items)))
        k = st.selectbox("Select", keys, key="acc_edit", format_func=lambda i: (
            ("🏦 " if items[i][0] == "bank_accounts" else "🛢️ ") + items[i][1]["name"]
            + ("" if items[i][1]["is_active"] else " (inactive)")))
        table, row = items[k]
        with st.form(f"acc_ren_{table}_{row['id']}"):
            nm = st.text_input("Name", value=row["name"])
            ok = st.form_submit_button("Save name")
        if ok:
            run(accounts.rename, table, row["id"], nm, me["id"], success="Name updated.")
        if row["is_active"]:
            if st.button("⛔ Deactivate", key=f"acc_off_{table}_{row['id']}"):
                run(accounts.set_active, table, row["id"], False, me["id"], success="Deactivated. Old entries are kept.")
        elif st.button("✅ Activate", key=f"acc_on_{table}_{row['id']}"):
            run(accounts.set_active, table, row["id"], True, me["id"], success="Activated.")


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
