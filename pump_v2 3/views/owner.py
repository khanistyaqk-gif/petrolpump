from datetime import date

import pandas as pd
import streamlit as st

from core.auth import current_user
from core.perms import require
from core.schema import FUEL_TYPES, ROLES
from core.ui import money, show_error
from views.common import flash, show_flash, table
from repo import assignments, nozzles, profiles, rates


@require("owner")
def users():
    show_flash()
    me = current_user()
    res = profiles.list_all()
    if not res.ok:
        return show_error(res, "Could not load users.")
    if res.rows:
        df = table(res.rows, ["name", "role", "phone", "is_active", "id"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No profiles yet.")

    st.subheader("Add / update a profile")
    st.caption("First create the user in Supabase → Authentication → Users, then paste that user's UUID here.")
    with st.form("profile_form", clear_on_submit=True):
        uid = st.text_input("Auth user UUID")
        name = st.text_input("Name")
        role = st.selectbox("Role", ROLES, index=2)
        phone = st.text_input("Phone (optional)")
        save = st.form_submit_button("Save profile", type="primary")
    if save:
        uid = uid.strip()
        if not uid or not name.strip():
            st.error("UUID and name are required.")
        elif uid == me["id"] and role != "owner":
            st.error("You cannot remove your own owner role.")
        else:
            r = profiles.upsert(uid, name.strip(), role, phone.strip())
            if r.ok:
                flash("success", "Profile saved.")
                st.rerun()
            else:
                show_error(r, "Could not save profile.")

    st.subheader("Switch a user on / off")
    others = [p for p in res.rows if p["id"] != me["id"]]
    if others:
        pick = st.selectbox("User", others, format_func=lambda p: f"{p['name']} ({p['role']}) – {'active' if p['is_active'] else 'inactive'}")
        label = "Deactivate" if pick["is_active"] else "Activate"
        if st.button(label, key="toggle_user"):
            r = profiles.set_active(pick["id"], not pick["is_active"])
            if r.ok:
                flash("success", f"{pick['name']}: done.")
                st.rerun()
            else:
                show_error(r)


@require("owner")
def nozzles_page():
    show_flash()
    me = current_user()
    res = nozzles.list_all()
    if not res.ok:
        return show_error(res, "Could not load nozzles.")
    if res.rows:
        st.dataframe(table(res.rows, ["id", "nozzle_name", "fuel_type", "current_reading", "is_active"]),
                     use_container_width=True, hide_index=True)

    st.subheader("Add nozzle")
    with st.form("nozzle_form", clear_on_submit=True):
        name = st.text_input("Nozzle name (e.g. P1)")
        fuel = st.selectbox("Fuel type", FUEL_TYPES)
        reading = st.number_input("Current meter reading", min_value=0.0, step=0.01, format="%.2f")
        add = st.form_submit_button("Add nozzle", type="primary")
    if add:
        r = nozzles.create(name, fuel, reading, me["id"])
        if r.ok:
            flash("success", "Nozzle added.")
            st.rerun()
        else:
            show_error(r, "Could not add nozzle.")

    if res.rows:
        st.subheader("Switch a nozzle on / off")
        pick = st.selectbox("Nozzle", res.rows, format_func=lambda n: f"{n['nozzle_name']} – {n['fuel_type']} – {'active' if n['is_active'] else 'inactive'}")
        if st.button("Deactivate" if pick["is_active"] else "Activate", key="toggle_nozzle"):
            if pick["is_active"]:
                busy = assignments.active_for_nozzle(pick["id"])
                if not busy.ok:
                    return show_error(busy)
                if busy.first:
                    return st.error("This nozzle is assigned on an active duty. End that assignment first.")
            r = nozzles.set_active(pick["id"], not pick["is_active"])
            if r.ok:
                flash("success", "Done.")
                st.rerun()
            else:
                show_error(r)


@require("owner")
def rates_page():
    show_flash()
    me = current_user()
    st.subheader("Current rates")
    rows = []
    for fuel in FUEL_TYPES:
        r = rates.current(fuel)
        if not r.ok:
            return show_error(r, "Could not load rates.")
        row = r.first
        rows.append({"fuel": fuel, "rate / L": money(row["price_per_liter"]) if row else "NOT SET",
                     "effective from": row["effective_from"] if row else "-"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if any(r["rate / L"] == "NOT SET" for r in rows):
        st.warning("Sales cannot be entered for a fuel type with no rate.")

    st.subheader("Set a rate")
    with st.form("rate_form", clear_on_submit=True):
        fuel = st.selectbox("Fuel type", FUEL_TYPES)
        price = st.number_input("Price per litre", min_value=0.0, step=0.01, format="%.2f")
        eff = st.date_input("Effective from", value=date.today())
        save = st.form_submit_button("Save rate", type="primary")
    if save:
        r = rates.set_rate(fuel, price, eff.isoformat(), me["id"])
        if r.ok:
            flash("success", "Rate saved.")
            st.rerun()
        else:
            show_error(r, "Could not save rate.")

    hist = rates.history(50)
    if hist.ok and hist.rows:
        st.subheader("History")
        st.dataframe(table(hist.rows, ["effective_from", "fuel_type", "price_per_liter", "created_at"]),
                     use_container_width=True, hide_index=True)
