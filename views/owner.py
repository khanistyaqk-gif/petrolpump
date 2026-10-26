"""Owner pages: Users, Nozzles, Fuel Rates, Tanks."""
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

    with st.expander("➕ Naya user", expanded=False):
        with st.form("new_user", clear_on_submit=True):
            name = st.text_input("Pura naam")
            login = st.text_input("Login ID", help="Jaise: ramesh  (ya poora email)")
            phone = st.text_input("Mobile (optional)")
            role = st.selectbox("Role", ["salesman", "manager", "owner"], format_func=ROLE_LABELS.get)
            pw = st.text_input("Password (kam se kam 6)", type="password")
            ok = st.form_submit_button("User banayein", type="primary")
        if ok:
            run(users.create_user, name, login, pw, role, phone, me["id"],
                success=f"{ROLE_LABELS[role]} ban gaya. Login ID: {login.strip().lower()}")

    people = users.list_profiles()
    if not people:
        st.info("Koi user nahi.")
        return
    st.dataframe(pd.DataFrame([{
        "Naam": p.get("name"), "Login": p.get("login") or "—", "Role": ROLE_LABELS.get(p.get("role")),
        "Mobile": p.get("phone") or "", "Status": "✅ Active" if p.get("is_active") else "⛔ Band",
    } for p in people]), hide_index=True, use_container_width=True)

    st.subheader("User badlein")
    by_id = {p["id"]: p for p in people}
    uid = st.selectbox("User", list(by_id), format_func=lambda i: f"{by_id[i]['name']} — {ROLE_LABELS.get(by_id[i]['role'])}")
    u = by_id[uid]
    with st.form(f"edit_{uid}"):
        role = st.selectbox("Role", ROLES, index=ROLES.index(u["role"]) if u["role"] in ROLES else 0,
                            format_func=ROLE_LABELS.get)
        active = st.checkbox("Active", value=bool(u.get("is_active")))
        pw = st.text_input("Naya password (khali = nahi badlega)", type="password")
        save = st.form_submit_button("Save")
    if save:
        def _save():
            users.update_user(uid, me["id"], role=role, is_active=active)
            if pw:
                users.reset_password(uid, pw, me["id"])
        run(_save, success="Save ho gaya.")


# ------------------------------------------------------------------ Nozzles
def nozzles_page():
    me = auth.require("owner")
    st.header("⛽ Nozzles")
    flash()

    with st.expander("➕ Naya nozzle"):
        with st.form("new_nozzle", clear_on_submit=True):
            name = st.text_input("Naam", placeholder="N1 Petrol")
            ft = st.selectbox("Fuel", FUEL_TYPES, format_func=fuel)
            reading = num("Abhi ki meter reading", "nz_reading")
            ok = st.form_submit_button("Banayein", type="primary")
        if ok:
            run(nozzles.create, name, ft, reading, me["id"], success="Nozzle ban gaya.")

    data = nozzles.list_nozzles()
    if not data:
        st.info("Abhi koi nozzle nahi.")
        return
    st.dataframe(pd.DataFrame([{
        "Nozzle": n["nozzle_name"], "Fuel": fuel(n["fuel_type"]), "Meter": lt(n.get("current_reading")),
        "Duty mein": "Haan" if nozzles.active_assignment(n["id"]) else "—",
        "Status": "✅ Chalu" if n.get("is_active") else "⛔ Band",
    } for n in data]), hide_index=True, use_container_width=True)

    by_id = {n["id"]: n for n in data}
    nid = st.selectbox("Nozzle chunein", list(by_id), format_func=lambda i: by_id[i]["nozzle_name"])
    n = by_id[nid]
    c1, c2 = st.columns(2)
    if n.get("is_active"):
        if c1.button("⛔ Band karein", use_container_width=True):
            run(nozzles.set_active, nid, False, me["id"], success="Nozzle band.")
    elif c1.button("✅ Chalu karein", use_container_width=True):
        run(nozzles.set_active, nid, True, me["id"], success="Nozzle chalu.")

    with st.expander("🔧 Meter reading sudhaar (repair/reset)"):
        st.caption("Sirf tab jab meter repair/reset hua ho. Duty mein nozzle ho to nahi hoga. Har badlav log hota hai.")
        with st.form(f"fix_{nid}"):
            new = num("Nayi reading", f"fix_r_{nid}", value=float(n.get("current_reading") or 0))
            reason = st.text_input("Kaaran")
            ok = st.form_submit_button("Sudhaarein")
        if ok:
            run(nozzles.correct_reading, nid, new, reason, me["id"], success="Reading sudhar gayi.")


# ------------------------------------------------------------------ Rates
def rates_page():
    me = auth.require("owner")
    st.header("💰 Fuel Rate")
    flash()
    today = today_ist()
    cur = rates.current_rates(today)
    cols = st.columns(2)
    for i, ft in enumerate(FUEL_TYPES):
        cols[i % 2].metric(fuel(ft), rs(cur[ft]) if cur[ft] else "Set nahi")

    with st.form("set_rate"):
        ft = st.selectbox("Fuel", FUEL_TYPES, format_func=fuel)
        price = num("Rate (₹ / litre)", "rate_price", value=float(cur.get(ft) or 0))
        eff = st.date_input("Kis tarikh se", value=date.fromisoformat(today))
        ok = st.form_submit_button("Rate save karein", type="primary")
    if ok:
        eff_s = eff.isoformat()
        msg = "Rate save ho gaya."
        if rates.activity_on_or_after(eff_s):
            msg += (f" Dhyan dein: {eff_s} ya uske baad ki sale pehle se hai — ho chuki entries ka rate nahi badlega, "
                    "nayi entries aur closing naye rate se hongi.")
        run(rates.set_rate, ft, price, eff_s, me["id"], success=msg)

    st.subheader("Rate history")
    hist = rates.history()
    if hist:
        st.dataframe(pd.DataFrame([{"Tarikh": h["effective_from"], "Fuel": fuel(h["fuel_type"]),
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
        st.info("Abhi koi tank nahi. Har bikne wale fuel ka tank banana zaroori hai, warna settlement approve nahi hoga.")

    with st.expander("➕ Naya tank"):
        with st.form("new_tank", clear_on_submit=True):
            ft = st.selectbox("Fuel", FUEL_TYPES, format_func=fuel)
            name = st.text_input("Naam", placeholder="Petrol Tank 1")
            cap = num("Capacity (L)", "tank_cap")
            opening = num("Abhi ka stock (L)", "tank_open")
            ok = st.form_submit_button("Banayein", type="primary")
        if ok:
            run(tanks.create, ft, name, cap, opening, me["id"], success="Tank ban gaya.")

    if data:
        with st.expander("🔧 Stock sudhaar (dip ke hisaab se)"):
            st.caption("Sirf galti sudhaarne ke liye. Roz ka dip → Stock page. Har badlav log hota hai.")
            with st.form("fix_stock"):
                ft = st.selectbox("Fuel", [t["fuel_type"] for t in data if t.get("is_active")], format_func=fuel)
                new = num("Sahi stock (L)", "fix_stock_v")
                reason = st.text_input("Kaaran")
                ok = st.form_submit_button("Sudhaarein")
            if ok:
                run(tanks.correct_stock, ft, new, reason, me["id"], success="Stock sudhar gaya.")


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
            n = st.text_input("Naya bank account", placeholder="Canara Bank OD")
            if st.form_submit_button("Jodein"):
                run(accounts.add_bank, n, me["id"], success="Bank jud gaya.")
    with c2:
        st.subheader("Oil companies")
        for o in accounts.oil_companies(False):
            st.write(("✅ " if o["is_active"] else "⛔ ") + o["name"])
        with st.form("oil", clear_on_submit=True):
            n = st.text_input("Nayi oil company", placeholder="IOCL")
            if st.form_submit_button("Jodein"):
                run(accounts.add_oil_company, n, me["id"], success="Oil company jud gayi.")

    st.subheader("Opening balance (shuruaat mein ek baar)")
    st.caption("Software shuru karte waqt ka paisa. Har account ka ek hi baar. Nozzle reading → Nozzles, "
               "tank stock → Tanks, party ka udhaar → neeche.")
    banks = accounts.banks()
    oils = accounts.oil_companies()
    with st.form("opening"):
        acc = st.selectbox("Account", money.ACCOUNTS, format_func=money.ACCOUNT_LABELS.get)
        ref = None
        if banks:
            ref_b = st.selectbox("Bank (agar Bank)", [b["id"] for b in banks],
                                 format_func=lambda i: next(b["name"] for b in banks if b["id"] == i))
        else:
            ref_b = None
        if oils:
            ref_o = st.selectbox("Oil company (agar Oil)", [o["id"] for o in oils],
                                 format_func=lambda i: next(o["name"] for o in oils if o["id"] == i))
        else:
            ref_o = None
        amt = num("Amount (bank OD minus ho to minus daalein)", "op_amt", min_value=-1e12)
        d = st.date_input("Tarikh", value=date.fromisoformat(today_ist()), key="op_date")
        ok = st.form_submit_button("Save")
    if ok:
        ref = ref_b if acc == "bank" else ref_o if acc == "oil" else None
        run(money.set_opening, acc, ref, amt, d.isoformat(), me["id"], success="Opening balance save.")

    parties = credit_repo.list_parties()
    if parties:
        with st.form("party_open"):
            pid = st.selectbox("Party ka purana udhaar", [p["id"] for p in parties],
                               format_func=lambda i: next(p["name"] for p in parties if p["id"] == i))
            amt = num("Udhaar amount", "pop_amt")
            ok = st.form_submit_button("Save")
        if ok:
            run(credit_repo.set_opening, pid, amt, today_ist(), me["id"], success="Party opening save.")


# ------------------------------------------------------------------ System
def system_page():
    auth.require("owner")
    st.header("🛡️ System")
    from repo import reports
    import json

    st.subheader("Hisaab check")
    if st.button("Check chalayein", type="primary"):
        problems, pending = reports.consistency_check()
        if problems:
            for p in problems:
                st.error(p)
        else:
            st.success("Sab theek: tank stock = register, party balance = khata, cash minus nahi.")
        st.caption(f"Approve baaki settlement: {pending}")

    st.subheader("Backup")
    st.caption("Poora data ek JSON file mein. Hafte mein ek baar download karke safe jagah rakhein.")
    if st.button("Backup banayein"):
        data = reports.backup()
        st.download_button("⬇️ Backup download", json.dumps(data, default=str, ensure_ascii=False).encode("utf-8"),
                           file_name=f"pump_backup_{today_ist()}.json", mime="application/json")

    st.subheader("Audit log (aakhri 200)")
    from core.db import db, rows
    log = rows(db().table("audit_log").select("*").order("id", desc=True).limit(200).execute())
    names = {p["id"]: p["name"] for p in users.list_profiles()}
    if log:
        st.dataframe(pd.DataFrame([{"Kab": str(r["created_at"])[:19].replace("T", " "),
                                    "Kisne": names.get(r.get("user_id"), r.get("user_id") or ""),
                                    "Kya": r["action"], "Detail": json.dumps(r.get("details") or {}, ensure_ascii=False)}
                                   for r in log]), hide_index=True, use_container_width=True)
